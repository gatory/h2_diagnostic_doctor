"""Move ONLY the head, slowly, with low-level commands (rt/lowcmd). Ctrl-C stops it at once.

    uv run python motion_tests/head_lowcmd.py eth10              # on the Jetson, from bridge/
    uv run python motion_tests/head_lowcmd.py --dry-run          # no robot: print the planned targets

    ┌──────────────────────────────────────────────────────────────────────────┐
    │  Ctrl-C AT ANY TIME = STOP. The head goes soft (no stiffness) at once,     │
    │  every motor stays in damping, and the script exits. A second Ctrl-C     │
    │  exits immediately.                                                        │
    └──────────────────────────────────────────────────────────────────────────┘

WHAT IT DOES TO THE ROBOT (read this before running):
- It RELEASES Unitree's motion control (MotionSwitcherClient.ReleaseMode), as
  Unitree's own low-level example does: nothing balances the robot afterwards.
  The robot must hang from the gantry with its feet clear, or be fully supported.
- Every motor except the head is held in DAMPING only (stiffness 0): limbs can be
  moved by hand and won't be driven anywhere. Slots 31-34 (unused) stay disabled.
- The head (slots 29 pitch, 30 yaw; the same in every Unitree source) eases in from
  where it is, sweeps slowly around that pose (yaw ±10°, pitch ±5°), comes back,
  and eases out. Targets are clamped 0.15 rad inside the joint limits
  (robot/joints.py) and move at most 0.4 rad/s.
- It stops by itself (head soft, damping) if rt/lowstate goes quiet for 0.1 s, a
  head motor reports an error bit, or the head ends up outside its clamped range.
- It won't start if the head already rests outside that clamped range (e.g. the
  head fully down, on its pitch stop): bring the head near the middle first.
- At the end it asks before giving control back to Unitree's mode; you can also
  leave it released and restore it from the remote/app.

Gains are Unitree's (head kp 30, kd 1.0; damping kd from h2_ankle_swing_example.py).
This is a test script, not part of the read-only h2_bridge diagnostics.
"""

import argparse
import math
import signal
import sys
import time

from h2_bridge.robot.joints import BODY_JOINTS

# ---------------------------------------------------------------- What it does (all in rad, s)

HEAD_PITCH, HEAD_YAW = 29, 30
NUM_MOTORS = 31  # slots 0..30 are real (robot/joints.py); 31..34 stay disabled

HEAD_KP, HEAD_KD = 30.0, 1.0  # Unitree's head gains (both H2 examples)
# Damping for every other motor (kp 0): Unitree's kd values from h2_ankle_swing_example.py.
DAMPING_KD = [2.0, 2.0, 2.0, 2.0, 0.3, 0.1,
              2.0, 2.0, 2.0, 2.0, 0.3, 0.1,
              2.5, 5.0, 5.0,
              2.0, 1.0, 0.4, 1.0, 0.2, 0.2, 0.2,
              2.0, 1.0, 0.4, 1.0, 0.2, 0.2, 0.2,
              1.0, 1.0]

CONTROL_DT = 0.002  # 500 Hz, as Unitree's low-level example
EASE_IN_S = 2.0  # head stiffness 0 -> kp, holding where it is
SWEEP_S = 24.0  # three slow cycles
PERIOD_S = 8.0
YAW_AMPLITUDE = math.radians(10)
PITCH_AMPLITUDE = math.radians(5)
RETURN_S = 3.0  # back to the start pose
EASE_OUT_S = 1.0  # head stiffness kp -> 0
MARGIN = 0.15  # stay this far inside each head joint limit
MAX_SPEED = 0.4  # rad/s, the most the target moves
STATE_TIMEOUT_S = 0.1  # rt/lowstate silent this long -> stop
STOP_DAMPING_S = 1.0  # after a stop, keep sending damping this long before exiting

LIMITS = {slot: (BODY_JOINTS[slot][1] + MARGIN, BODY_JOINTS[slot][2] - MARGIN) for slot in (HEAD_PITCH, HEAD_YAW)}


def planned_target(t, start):
    """Head (pitch, yaw) target at time t after the ease-in, before speed limiting; None once finished."""
    pitch0, yaw0 = start
    if t < 0:
        return start
    if t < SWEEP_S:
        phase = 2 * math.pi * t / PERIOD_S
        # sin starts at 0: the sweep begins exactly at the start pose
        return pitch0 + PITCH_AMPLITUDE * math.sin(2 * phase), yaw0 + YAW_AMPLITUDE * math.sin(phase)
    if t < SWEEP_S + RETURN_S:
        return start
    return None


def clamp(slot, q):
    lo, hi = LIMITS[slot]
    return min(max(q, lo), hi)


def step_toward(current, target, dt):
    """Move `current` toward `target` by at most MAX_SPEED * dt."""
    step = MAX_SPEED * dt
    return current + max(-step, min(step, target - current))


# ---------------------------------------------------------------- Dry run (no robot)


def dry_run():
    start = (0.06, 0.0)  # a typical resting head pose (pitch, yaw)
    target = list(start)
    print(f"limits after the {MARGIN} rad margin: pitch {LIMITS[HEAD_PITCH]}, yaw {LIMITS[HEAD_YAW]}")
    print("   t   pitch    yaw   (rad; targets after clamping and the speed limit)")
    dt, ticks_per_s = CONTROL_DT, round(1 / CONTROL_DT)
    tick = 0
    while True:
        t = tick * dt  # from a tick count, so the once-a-second print never drifts
        planned = planned_target(t - EASE_IN_S, start)
        if planned is None:
            break
        for i, slot in enumerate((HEAD_PITCH, HEAD_YAW)):
            target[i] = step_toward(target[i], clamp(slot, planned[i]), dt)
        if tick % ticks_per_s == 0:
            print(f"{t:5.1f}  {target[0]:+.3f}  {target[1]:+.3f}")
        tick += 1
    print(f"done after {t:.1f} s, then {EASE_OUT_S} s easing the head's stiffness to 0")


# ---------------------------------------------------------------- On the robot


class HeadTest:
    def __init__(self, interface):
        from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher, ChannelSubscriber
        from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_
        from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_, LowState_
        from unitree_sdk2py.utils.crc import CRC

        ChannelFactoryInitialize(0, interface)
        self.crc = CRC()
        self.cmd = unitree_hg_msg_dds__LowCmd_()
        self.state = None
        self.state_at = 0.0
        self.sub = ChannelSubscriber("rt/lowstate", LowState_)
        self.sub.Init(self._on_state, 1)
        self.pub = ChannelPublisher("rt/lowcmd", LowCmd_)
        self.pub.Init()
        self.released_mode = None  # Unitree's mode name, once released

    def _on_state(self, msg):
        self.state = msg
        self.state_at = time.monotonic()

    def wait_for_state(self, timeout=3.0):
        end = time.monotonic() + timeout
        while self.state is None and time.monotonic() < end:
            time.sleep(0.01)
        return self.state is not None

    def release_unitree_control(self):
        from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient

        self.msc = MotionSwitcherClient()
        self.msc.SetTimeout(5.0)
        self.msc.Init()
        _, result = self.msc.CheckMode()
        while result and result.get("name"):
            self.released_mode = self.released_mode or result["name"]
            print(f"Releasing Unitree's motion control (mode '{result['name']}')...")
            code, _ = self.msc.ReleaseMode()
            if code != 0:
                print(f"  ReleaseMode returned {code}; checking again")
            time.sleep(5)
            _, result = self.msc.CheckMode()
        print("Released: nothing is balancing the robot now.")

    def send(self, head_targets, head_kp):
        """One command: the head at `head_targets` (pitch, yaw) with stiffness head_kp; every other motor damping."""
        s = self.state
        self.cmd.mode_pr = s.mode_pr
        self.cmd.mode_machine = s.mode_machine
        for i in range(NUM_MOTORS):
            m = self.cmd.motor_cmd[i]
            m.mode, m.tau, m.dq = 1, 0.0, 0.0
            if i in (HEAD_PITCH, HEAD_YAW):
                m.q = head_targets[0] if i == HEAD_PITCH else head_targets[1]
                m.kp, m.kd = head_kp, HEAD_KD
            else:
                m.q, m.kp, m.kd = s.motor_state[i].q, 0.0, DAMPING_KD[i]
        self.cmd.crc = self.crc.Crc(self.cmd)
        self.pub.Write(self.cmd)

    def problem(self):
        """Why the test must stop right now, or None."""
        if time.monotonic() - self.state_at > STATE_TIMEOUT_S:
            return f"rt/lowstate silent for over {STATE_TIMEOUT_S} s"
        for slot, name in ((HEAD_PITCH, "head_pitch"), (HEAD_YAW, "head_yaw")):
            m = self.state.motor_state[slot]
            if m.motorstate:
                return f"{name} motor error bits 0x{m.motorstate:X}"
            lo, hi = LIMITS[slot]
            if not lo - 0.05 <= m.q <= hi + 0.05:
                return f"{name} at {m.q:+.3f} rad, outside its range {lo:+.3f}..{hi:+.3f}"
        return None


def run(interface):
    stop = {"why": None}
    target = [0.0, 0.0]

    def on_ctrl_c(signum, frame):
        if stop["why"]:  # second Ctrl-C: one soft command (head kp 0, all damping), then out at once
            try:
                test.send(target, 0.0)
            finally:
                print("\nSecond Ctrl-C: sent head soft + damping, exiting now.")
                raise SystemExit(2)
        stop["why"] = "Ctrl-C"

    test = HeadTest(interface)
    if not test.wait_for_state():
        print("No rt/lowstate received: check the interface. Nothing was sent.")
        return 1
    if test.problem():
        print(f"Not starting: {test.problem()}. Nothing was sent.")
        return 1

    test.release_unitree_control()
    signal.signal(signal.SIGINT, on_ctrl_c)
    s = test.state
    start = (clamp(HEAD_PITCH, s.motor_state[HEAD_PITCH].q), clamp(HEAD_YAW, s.motor_state[HEAD_YAW].q))
    target[:] = [s.motor_state[HEAD_PITCH].q, s.motor_state[HEAD_YAW].q]  # begin exactly where the head is
    print(f"Head starts at pitch {target[0]:+.3f}, yaw {target[1]:+.3f} rad.  >>> Ctrl-C = STOP <<<")

    t0 = time.monotonic()
    next_tick, last_print = t0, 0.0
    finished_at = None
    while True:
        now = time.monotonic()
        t = now - t0
        why = stop["why"] or test.problem()
        if why:
            break
        planned = planned_target(t - EASE_IN_S, start)
        if planned is None:  # sweep and return done: ease the stiffness out, then finish
            finished_at = finished_at or now
            fade = max(0.0, 1.0 - (now - finished_at) / EASE_OUT_S)
            test.send(target, HEAD_KP * fade)
            if fade == 0.0:
                why = "finished"
                break
        else:
            for i, slot in enumerate((HEAD_PITCH, HEAD_YAW)):
                target[i] = step_toward(target[i], clamp(slot, planned[i]), CONTROL_DT)
            kp = HEAD_KP * min(1.0, t / EASE_IN_S)  # stiffness eases in, so the head never jumps
            test.send(target, kp)
        if t - last_print >= 0.5:
            last_print = t
            q = test.state.motor_state
            print(f"  {t:5.1f} s  target pitch {target[0]:+.3f} yaw {target[1]:+.3f}  |  "
                  f"actual pitch {q[HEAD_PITCH].q:+.3f} yaw {q[HEAD_YAW].q:+.3f}   (Ctrl-C = stop)")
        next_tick += CONTROL_DT
        time.sleep(max(0.0, next_tick - time.monotonic()))

    # Stopped (Ctrl-C, a problem, or finished): head soft, everything in damping, for STOP_DAMPING_S.
    print(f"\nSTOP ({why}): head soft, all motors in damping.")
    end = time.monotonic() + STOP_DAMPING_S
    while time.monotonic() < end:
        if test.state is not None:
            test.send(target, 0.0)
        time.sleep(CONTROL_DT)
    signal.signal(signal.SIGINT, signal.default_int_handler)

    print(f"Unitree's motion control is still RELEASED (it was '{test.released_mode}').")
    print("The robot must stay supported until it's restored.")
    try:
        answer = input(f"Type 'restore' + Enter to give control back to '{test.released_mode}' now, "
                       "or just Enter to leave it released: ")
    except (KeyboardInterrupt, EOFError):
        answer = ""
    if answer.strip() == "restore" and test.released_mode:
        code, _ = test.msc.SelectMode(test.released_mode)
        print("Restored." if code == 0 else f"SelectMode returned {code}: restore it from the remote/app.")
    else:
        print("Left released: restore it from the remote/app when the robot is ready.")
    return 0 if why == "finished" else 2


def main():
    parser = argparse.ArgumentParser(description="Move only the head with rt/lowcmd. Ctrl-C stops it at once. "
                                                 "Releases Unitree's motion control: robot on the gantry only.")
    parser.add_argument("interface", nargs="?", help="network interface to the robot, e.g. eth10")
    parser.add_argument("--dry-run", action="store_true", help="no robot: print the planned head targets")
    args = parser.parse_args()
    if args.dry_run:
        dry_run()
        return 0
    if not args.interface:
        parser.error("give the network interface (e.g. eth10), or --dry-run")

    print(__doc__.split("WHAT IT DOES")[0].split("\n\n", 1)[1])
    print("This RELEASES Unitree's motion control: the robot will NOT balance.")
    print("  - The robot hangs from the gantry with its feet clear (or is fully supported).")
    print("  - Someone is at the e-stop.")
    try:
        if input("Type 'head' + Enter to start (anything else quits): ").strip() != "head":
            print("Not started. Nothing was sent.")
            return 0
    except (KeyboardInterrupt, EOFError):
        print("\nNot started. Nothing was sent.")
        return 0
    return run(args.interface)


if __name__ == "__main__":
    sys.exit(main())
