"""Switch the robot's FSM state (LocoClient.SetFsmId), one confirmed step at a time. GANTRY ONLY.

    uv run python motion_tests/set_fsm.py eth10        # on the Jetson, from bridge/
    uv run python motion_tests/set_fsm.py --dry-run    # no robot: try the menu with a pretend robot
    uv run python motion_tests/set_fsm.py eth10 --allow-mimic   # also offer 502 HumanMimic, 503 HumanMimic2

    ┌──────────────────────────────────────────────────────────────────────────┐
    │  This COMMANDS the robot: a new FSM state can make it stand, sit, step,  │
    │  or go limp. Robot on the gantry, feet clear, remote in your hand: the   │
    │  remote's own damp/stop always works and wins.                           │
    │  Ctrl-C quits WITHOUT sending anything: the robot stays in whatever      │
    │  state it's in (Unitree's controller keeps holding it).                  │
    └──────────────────────────────────────────────────────────────────────────┘

WHAT IT DOES:
- Shows the current state (GetFsmId) and a menu of the robot's CORE states only
  (ids 0-5, 601, 701, 703, from GetAvailableFsmIds). Motion clips (BeyondMimic,
  HumanMimic: dances, kicks, runs) are never offered.
- Each switch needs you to type the target id a second time. `d` is the shortcut
  to Damp (1 Passive), with one confirmation.
- With --allow-mimic it also offers the two HumanMimic players, 502 and 503 (never
  BeyondMimic 100, never a clip id): only from Ready (4), confirmed by typing the
  state's NAME, and then it watches for 15 s and prints every state change (a player
  may hop into one of its clips, 502xxx/503xxx, or back to another state).
- After sending, it reads GetFsmId for up to 3 s and says whether the robot got there.
  The robot's own controller decides whether a switch is allowed; a refused one
  shows as an error code, or as the state not changing.
- Sends nothing else: no velocity, no arm commands, no SelectMode/ReleaseMode.
  In a walk state no Move is ever sent, so it should only stand or step in place.
- Refuses to start if Unitree's motion control is released (e.g. after
  head_lowcmd.py): restore it from the remote/app first.

Why Ctrl-C doesn't damp here (head_lowcmd.py does): that script streams motor
commands, so stopping the stream must leave the motors safe. This one sends single
requests; between them Unitree's controller is in charge, and an unasked-for switch
to damp would drop a robot that isn't hanging from the gantry.

Test script, not part of the read-only h2_bridge diagnostics. Never import it from h2_bridge.
"""

import argparse
import sys
import time

from h2_bridge.robot.fsm import GEARS, MOTION_CLIP_IDS

# The core states this script will switch to: everything the robot lists below the motion-clip
# range, except the mimic "players" (100 BeyondMimic, 502 HumanMimic, 503 HumanMimic2), which
# replay recorded motions.
EXCLUDED = {100, 502, 503}

# --allow-mimic: these two players only. What entering one bare (no clip chosen) does is unknown
# (2026-11-27): hold still, wait for input, or play a clip. Hence: only from Ready, typed by name,
# and watched afterwards. BeyondMimic (100) and every clip id stay off limits.
MIMIC = {502, 503}
MIMIC_FROM = 4  # Ready (FixStand)
MIMIC_WATCH_S = 15.0

# What's known about each core state (2026-11-27). "tried": set with the remote and read back by
# `discovery modes --map`. The rest have never been switched to: go slowly.
_TRIED = {fsm_id: gear for gear, (fsm_id, _) in GEARS.items()}
NOTES = {
    0: "Zero torque: every motor limp. The robot hangs on the gantry.",
    1: "Damp: motors resist motion but hold nothing. The usual safe state.",
    2: "Protection: untried. Unknown behaviour; probably a fault/fall-protection state.",
    3: "Sit: untried. The robot will try to sit; on the gantry its legs may fold up.",
    4: "Ready (stand): the robot stiffens and stands. Feet should be just touching or clear.",
    5: "HybridPassive: untried. Probably a mixed passive/damping state.",
    601: "Walk 1 (HybridWalk): balance controller on. No Move is sent: it should stand or step in place.",
    701: "WalkNew: untried walk controller. No Move is sent: it should stand or step in place.",
    703: "Walk 2 (PhaseWalk): balance controller on. No Move is sent: it should stand or step in place.",
    502: "HumanMimic player: UNTRIED, may play a motion. From Ready only; typed by name.",
    503: "HumanMimic2 player: UNTRIED, may play a motion. From Ready only; typed by name.",
}

DAMP = 1
SETTLE_S = 3.0  # how long to watch GetFsmId after a switch
TIMEOUT_S = 1.0  # per RPC call


class Robot:
    """Just the calls this script uses: the getters, plus SetFsmId."""

    def __init__(self, interface, domain_id=0):
        from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient
        from unitree_sdk2py.core.channel import ChannelFactoryInitialize
        from unitree_sdk2py.h2.loco.h2_loco_client import LocoClient

        ChannelFactoryInitialize(domain_id, interface)
        self._switcher = MotionSwitcherClient()
        self._loco = LocoClient()
        for client in (self._switcher, self._loco):
            client.SetTimeout(TIMEOUT_S)
            client.Init()

    def motion_mode(self):
        code, data = self._switcher.CheckMode()
        return (data or {}).get("name") if code == 0 else None

    def fsm_id(self):
        code, value = self._loco.GetFsmId()
        return value if code == 0 else None

    def available(self):
        code, ids, names = self._loco.GetAvailableFsmIds()
        return dict(zip(ids, names)) if code == 0 else {}

    def set_fsm(self, fsm_id):
        return self._loco.SetFsmId(fsm_id)


class PretendRobot:
    """--dry-run: answers like the H2 did on 2026-11-27 and follows every switch."""

    def __init__(self):
        self.state = 1

    def motion_mode(self):
        return "ai"

    def fsm_id(self):
        return self.state

    def available(self):
        return {0: "Invalid", 1: "Passive", 2: "Protection", 3: "Sit", 4: "FixStand", 5: "HybridPassive",
                100: "BeyondMimic", 502: "HumanMimic", 503: "HumanMimic2", 601: "HybridWalk",
                701: "WalkNew", 703: "PhaseWalk", 100101: "BeyondMimic_..._360DANKOU_002"}

    def set_fsm(self, fsm_id):
        self.state = fsm_id
        return 0


def core_states(available, allow_mimic=False):
    """{id: name} of the states this script offers: below the motion clips, minus the mimic players
    (plus 502/503 with allow_mimic)."""
    allowed = EXCLUDED - MIMIC if allow_mimic else EXCLUDED
    return {i: n for i, n in sorted(available.items()) if i < MOTION_CLIP_IDS and i not in allowed}


def watch_changes(robot, names, seconds):
    """Print every FSM state change for `seconds` (Ctrl-C ends it early); return the last reading."""
    end = time.monotonic() + seconds
    last = object()
    reading = None
    print(f"   watching for {seconds:g} s (Ctrl-C to stop watching; the remote's damp stops the robot)")
    while time.monotonic() < end:
        reading = robot.fsm_id()
        if reading != last:
            last = reading
            print(f"   {time.strftime('%H:%M:%S')}  {name_of(reading, names)}")
        time.sleep(0.2)
    return reading


def name_of(fsm_id, names):
    return "no answer" if fsm_id is None else f"{fsm_id} {names.get(fsm_id, '?')}"


def watch_switch(robot, target, names):
    """Read GetFsmId until it reaches `target` or SETTLE_S passes; return the last reading."""
    end = time.monotonic() + SETTLE_S
    seen = None
    while time.monotonic() < end:
        seen = robot.fsm_id()
        if seen == target:
            return seen
        time.sleep(0.2)
    return seen


def switch(robot, target, names):
    code = robot.set_fsm(target)
    if code != 0:
        print(f"   SetFsmId({target}) was refused: code {code}. The robot didn't change state "
              "(the switch may not be allowed from here; go through the usual order).")
        return
    now = watch_switch(robot, target, names)
    if now == target:
        print(f"   -> now in {name_of(now, names)}")
    else:
        print(f"   sent, but after {SETTLE_S:g} s the robot reads {name_of(now, names)}, not {target}.")


def main():
    parser = argparse.ArgumentParser(description="Switch the robot's FSM state, one confirmed step at a time (gantry only).")
    parser.add_argument("interface", nargs="?", default="eth10", help="network interface (default: eth10)")
    parser.add_argument("--domain", type=int, default=0, help="DDS domain (default: 0)")
    parser.add_argument("--dry-run", action="store_true", help="no robot: a pretend robot that follows every switch")
    parser.add_argument("--allow-mimic", action="store_true",
                        help="also offer 502 HumanMimic and 503 HumanMimic2 (from Ready only, typed by name)")
    args = parser.parse_args()

    robot = PretendRobot() if args.dry_run else Robot(args.interface, args.domain)

    mode = robot.motion_mode()
    if not mode:
        print("Unitree's motion control isn't active (released, or the motion switcher didn't answer).\n"
              "Restore it from the remote/app first; this script doesn't touch it. Nothing was sent.")
        return 1
    names = robot.available()
    offered = core_states(names, args.allow_mimic)
    if not offered:
        print("The robot didn't send its FSM list (GetAvailableFsmIds). Check the interface. Nothing was sent.")
        return 1

    print(__doc__.split("WHAT IT DOES:")[0].split("\n\n", 2)[2])  # the boxed warning
    if input("Robot on the gantry, feet clear, remote in hand? Type yes: ").strip().lower() != "yes":
        print("Nothing was sent.")
        return 0

    while True:
        current = robot.fsm_id()
        print(f"\nNow: {name_of(current, names)}   (motion switcher: {mode})")
        for fsm_id, name in offered.items():
            mark = "*" if fsm_id == current else " "
            tried = "" if fsm_id in _TRIED else "  [untried]"
            print(f" {mark} {fsm_id:>4}  {name:<14} {NOTES.get(fsm_id, '')}{tried}")
        choice = input("Switch to which id? (d = Damp, q = quit) ").strip().lower()
        if choice in ("q", ""):
            print("Quit. Nothing more sent; the robot stays as it is.")
            return 0
        if choice == "d":
            if input(f"Damp ({DAMP} {names.get(DAMP)}): press Enter to send, anything else to cancel ") == "":
                switch(robot, DAMP, names)
            continue
        try:
            target = int(choice)
        except ValueError:
            print("   not an id")
            continue
        if target not in offered:
            print(f"   {target} isn't offered here (only the core states above; never motion clips).")
            continue
        if target == current:
            print("   already there")
            continue
        if target in MIMIC:
            if current != MIMIC_FROM:
                print(f"   {names[target]} only from Ready ({MIMIC_FROM} {names.get(MIMIC_FROM)}): switch there first.")
                continue
            print(f"   {names[target]} is UNTRIED and may play a motion. Clear space around the robot, a hand on")
            print("   the remote's damp, nobody within arm's/leg's reach.")
            confirm = input(f"   Type {names[target]} to send SetFsmId({target}): ").strip()
            if confirm != names[target]:
                print("   cancelled, nothing sent")
                continue
            code = robot.set_fsm(target)
            if code != 0:
                print(f"   SetFsmId({target}) was refused: code {code}. Nothing changed.")
                continue
            try:
                watch_changes(robot, names, MIMIC_WATCH_S)
            except KeyboardInterrupt:
                print("   stopped watching (nothing sent)")
            continue
        confirm = input(f"   Send SetFsmId({target}) = {names[target]}? Type {target} again to confirm: ").strip()
        if confirm != str(target):
            print("   cancelled, nothing sent")
            continue
        switch(robot, target, names)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print("\nStopped. Nothing more sent; the robot stays in its current state.")
        sys.exit(130)
