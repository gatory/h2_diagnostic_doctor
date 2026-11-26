"""Fake robot data for the tests: healthy core-topic messages, and a source that steps its clock.

    source = FakeSource(duration=10)                       # a healthy robot for 10 s
    source = FakeSource(duration=10, tweak=nan_elbow)      # ... with a fault injected

Messages have the same shape msg_to_dict() gives for the real SDK messages
(checked against the 2026-11-26 recordings), with a little noise on every
joint so a healthy robot never looks frozen. `tweak(topic, t, data)` may edit
`data` in place, or return False to drop that message (a topic going quiet).
"""

import math

from h2_bridge.robot import joints, sensors
from h2_bridge.telemetry.core_topics import CORE_TOPICS
from h2_bridge.telemetry.models import Message
from h2_bridge.telemetry.sources.base_source import Source

START = 1_764_000_000.0  # a fixed epoch time, like a recording's


def imu(rpy):
    return {"quaternion": [1.0, 0.0, 0.0, 0.0], "gyroscope": [0.001, 0.002, 0.003],
            "accelerometer": [0.4, 0.2, 9.7], "rpy": list(rpy), "temperature": 80}


def motor(q, temperature):
    return {"mode": 1, "q": q, "dq": 0.001, "ddq": 0.0, "tau_est": 0.5, "temperature": list(temperature),
            "vol": 0.0, "sensor": [0, 0], "motorstate": 0, "reserve": [0, 0, 0, 0]}


def _noise(t, slot):
    return 0.001 * math.sin(t * 7.0 + slot)  # changes every message, like encoder noise


def lowstate(t):
    """A healthy LowState_: every joint mid-range; the pelvis IMU consistent with the waist joints."""
    motors = []
    for slot, (_, lower, upper) in enumerate(joints.BODY_JOINTS):
        motors.append(motor((lower + upper) / 2 + _noise(t, slot), [30, 30]))
    motors += [motor(0.0, [0, 0]) | {"mode": 0, "tau_est": 0.0} for _ in range(35 - len(motors))]
    return {"version": [0, 0], "mode_pr": 0, "mode_machine": 1, "tick": int((t - START) * 1000),
            "imu_state": imu(pelvis_rpy(t)), "motor_state": motors, "wireless_remote": [0] * 40,
            "reserve": [0] * 4, "crc": 0}


def pelvis_rpy(t):
    return (0.01, 0.02, 0.3)


def torso_rpy(t):
    """pelvis - torso = -waist, in roll and pitch (docs/robot_findings.md), using lowstate()'s waist joints."""
    waist_roll = (joints.BODY_JOINTS[13][1] + joints.BODY_JOINTS[13][2]) / 2 + _noise(t, 13)
    waist_pitch = (joints.BODY_JOINTS[14][1] + joints.BODY_JOINTS[14][2]) / 2 + _noise(t, 14)
    roll, pitch, yaw = pelvis_rpy(t)
    return (roll + waist_roll, pitch + waist_pitch, yaw + 0.2)  # yaw drifts: never compared


def secondary_imu(t):
    return imu(torso_rpy(t))


def bmsstate(t):
    cells = [3870 + (i % 3) for i in range(sensors.NUM_BMS_CELLS)] + [0] * (40 - sensors.NUM_BMS_CELLS)
    return {"version_high": 1, "version_low": 12, "fn": 120, "cell_vol": cells,
            "bmsvoltage": [sum(cells), sum(cells) - 30, 0], "current": -3600, "soc": 73, "soh": 100,
            "temperature": [29, 21, 20, 25, 26] + [0] * 7, "cycle": 6, "manufacturer_date": 0,
            "bmsstate": [577, 0, 0, 0, 18], "reserve": [0, 0, 0]}


def mainboardstate(t):
    return {"fan_state": [0] * 6, "temperature": [46, 54, 53, 29, 0, 0], "value": [0.0] * 6, "state": [0] * 6}


def handstate(t):
    motors = []
    for slot, (_, _, _, position_only) in enumerate(joints.HAND_JOINTS):
        m = motor(0.1 + _noise(t, slot), [0, 0] if position_only else [55, 0])
        if position_only:
            m["mode"] = 0
        motors.append(m)
    pads = [{"pressure": [float(i)] * 6 + [0.0] * 6, "temperature": [0.0] * 12, "lost": 0, "reserve": 0}
            for i in range(16)]
    return {"motor_state": motors, "press_sensor_state": pads, "imu_state": imu((0.0, 0.0, 0.0)) | {"temperature": 6500},
            "power_v": 2.39, "power_a": 0.027, "system_v": 2.39, "device_v": 2.39, "error": [0, 0], "reserve": [0, 0]}


HEALTHY = {
    "rt/lf/lowstate": lowstate,
    "rt/lf/secondary_imu": secondary_imu,
    "rt/lf/bmsstate": bmsstate,
    "rt/lf/mainboardstate": mainboardstate,
    "rt/dex5/left/state": handstate,
    "rt/dex5/right/state": handstate,
}


class FakeSource(Source):
    """The core topics at their expected rates, on a clock that moves `step_s` per poll (like a stepped replay).

    Parameters
    ----------
    duration : float
        Seconds of data before the source is done.
    tweak : callable | None
        tweak(topic, t, data) -> None (keep, maybe edited in place) or False (drop the message).
    dropped : dict | None
        Pretend to be a live source with this `dropped` dict (None: like a replay).
    """

    live = False

    def __init__(self, duration=10.0, tweak=None, step_s=0.25, dropped=None):
        super().__init__(CORE_TOPICS)
        self.duration = duration
        self.tweak = tweak
        self.step_s = step_s
        self.dropped = dropped
        self._now = START
        self._next = {name: START for name in CORE_TOPICS}  # when each topic's next message is due

    def poll(self):
        if self.done:
            return []
        self._now += self.step_s
        end = min(self._now, START + self.duration)
        messages = []
        for name, spec in self.topics.items():
            period = 1.0 / spec.expected_hz
            while self._next[name] <= end:
                t = self._next[name]
                self._next[name] += period
                data = HEALTHY[name](t)
                if self.tweak and self.tweak(name, t, data) is False:
                    continue
                messages.append(Message(t, name, data))
        messages.sort(key=lambda m: m.t)
        if self._now >= START + self.duration:
            self.done = True
        return messages

    def now(self):
        return min(self._now, START + self.duration)


def after(seconds):
    """True for times at least `seconds` after the start: for tweaks that start a fault part-way."""
    return lambda t: t - START >= seconds
