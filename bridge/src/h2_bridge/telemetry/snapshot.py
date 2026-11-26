"""Snapshot: the robot's state at one moment, as plain named values.

    builder = SnapshotBuilder(source.topics, source.dropped)
    run(source, [builder, ...])            # a poll-loop consumer: keeps the newest message per topic
    snap = builder.snapshot(source.now())
    snap.body.joints[18].name              # "L_elbow"
    snap.battery.cell_spread               # 14 (mV)
    snap.topics["rt/lf/lowstate"].hz       # 20.1

A Snapshot turns raw messages (motor_state[18]["temperature"][0]) into named
values once, using the robot facts in h2_bridge.robot, so the dashboard,
checkup and (later) the server never repeat that mapping. It is the newest
message per topic, not history, and it holds facts, not verdicts: "spread
14 mV", never "battery OK" (that's checkup's job).

A part whose topic hasn't sent anything yet is None. A topic whose newest
message has an unexpected shape is listed in `bad` and its part is None too,
so one odd message can never crash a consumer.

Not to be confused with discovery.models.Snapshot (one discovery run).
"""

from dataclasses import dataclass

from h2_bridge.robot import joints, sensors
from h2_bridge.telemetry.rate_meter import RateMeter, latest

# Core topic names, as in telemetry/core_topics.py.
LOWSTATE = "rt/lf/lowstate"
TORSO_IMU = "rt/lf/secondary_imu"
BATTERY = "rt/lf/bmsstate"
MAIN_BOARD = "rt/lf/mainboardstate"
HANDS = {"left": "rt/dex5/left/state", "right": "rt/dex5/right/state"}

# What reading a message of the wrong shape raises (a missing key, a short list, a None).
_SHAPE_ERRORS = (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError)


# ---------------------------------------------------------------- The parts


@dataclass(frozen=True)
class TopicStatus:
    """How one topic is arriving: what checkup's topic rules and the Topics panel read."""

    name: str
    expected_hz: float | None  # None: no expectation (not a core topic)
    hz: float  # over the rate meter's window (2 s); 0.0 if silent
    avg_hz: float | None  # over the whole run; None below 2 messages
    count: int  # messages so far
    age_s: float | None  # since the newest message; None before the first
    dropped: int | None  # lost by the live source; None for a replay (can't drop)


@dataclass(frozen=True)
class Imu:
    rpy: tuple  # rad
    gyro: tuple  # rad/s
    accel: tuple  # m/s²
    temperature: int  # unit unconfirmed (hand IMUs read ~6500, body ones ~80)


@dataclass(frozen=True)
class Joint:
    """One body joint (LowState_.motor_state[slot]) by name, with its limits from robot/joints.py."""

    slot: int
    name: str
    q: float | None  # rad; None if the robot sent NaN/inf
    dq: float | None
    tau: float | None  # tau_est
    temperatures: tuple  # 2 sensors, meaning unconfirmed
    mode: int
    motorstate: int  # error bits; 0 on a healthy robot
    lower: float  # rad
    upper: float  # rad


@dataclass(frozen=True)
class Body:
    joints: tuple  # of Joint, slots 0..30 in order
    imu: Imu  # the pelvis IMU (inside LowState_)
    mode_machine: int
    mode_pr: int
    tick: int


@dataclass(frozen=True)
class HandMotor:
    slot: int
    name: str
    q: float | None
    dq: float | None
    tau: float | None
    temperature: int | None  # None for the position-only thumb slots
    mode: int
    motorstate: int


@dataclass(frozen=True)
class Hand:
    side: str  # "left" / "right"
    motors: tuple  # of HandMotor, slots 0..19 in order
    pad_max: tuple  # the highest reading of each of the 16 pressure pads
    error: tuple  # [0, 0] on a healthy hand
    power_v: float | None
    power_a: float | None
    system_v: float | None
    imu: Imu


@dataclass(frozen=True)
class Battery:
    soc: int  # %
    soh: int  # %
    volts: float  # V
    current: int  # probably mA, negative = discharging (unconfirmed)
    cells: tuple  # mV, the real cells only (robot/sensors.py)
    temperatures: tuple  # unused trailing slots removed; unit unconfirmed
    cycle: int
    state: tuple  # raw bmsstate, meaning unknown
    version: str

    @property
    def cell_min(self):
        return min(self.cells)

    @property
    def cell_max(self):
        return max(self.cells)

    @property
    def cell_spread(self):
        """mV between the highest and lowest cell."""
        return self.cell_max - self.cell_min


@dataclass(frozen=True)
class Board:
    temperatures: tuple  # the real ones (robot/sensors.py); which parts they are: unknown
    fans: tuple  # raw, meaning unknown
    state: tuple  # raw, meaning unknown
    value: tuple  # raw, meaning unknown


@dataclass(frozen=True)
class Snapshot:
    t: float  # the source's clock when it was taken
    topics: dict  # name -> TopicStatus, in the source's order
    body: Body | None
    torso_imu: Imu | None
    hands: dict  # "left"/"right" -> Hand | None
    battery: Battery | None
    board: Board | None
    bad: frozenset  # topics whose newest message has an unexpected shape

    @property
    def any_data(self):
        """True once at least one message has arrived."""
        return any(status.count for status in self.topics.values())


# ---------------------------------------------------------------- Building one


class SnapshotBuilder:
    """Poll-loop consumer: keeps the newest message per topic and every topic's rates.

    Attributes
    ----------
    meter : RateMeter
        Fed with every message; its `total` is the message count per topic.
    newest : dict[str, Message]
        The newest message per topic so far.
    """

    def __init__(self, topics, dropped=None):
        """topics: {name: TopicSpec} the source delivers; dropped: the source's `dropped` (None for a replay)."""
        self.topics = dict(topics)
        self.dropped = dropped  # the live source's own dict, so it stays current
        self.meter = RateMeter()
        self.newest = {}
        self._cached = None  # (now, Snapshot): consumers in one poll share one build

    def add(self, messages, now):
        self.meter.add(messages)  # every message, so rates are true
        self.newest.update(latest(messages))  # only the newest, for the snapshot
        self._cached = None

    def snapshot(self, now):
        """The Snapshot at `now` (the source's clock)."""
        if self._cached and self._cached[0] == now:
            return self._cached[1]
        data = {topic: message.data for topic, message in self.newest.items()}
        bad = set()

        def part(topic, read, *args):
            """read(data, *args) for `topic`'s newest message; None if none yet or a bad shape."""
            if topic not in data:
                return None
            try:
                return read(data[topic], *args)
            except _SHAPE_ERRORS:
                bad.add(topic)
                return None

        snap = Snapshot(
            t=now,
            topics={name: self._topic_status(name, spec, now) for name, spec in self.topics.items()},
            body=part(LOWSTATE, read_body),
            torso_imu=part(TORSO_IMU, read_imu),
            hands={side: part(topic, read_hand, side) for side, topic in HANDS.items()},
            battery=part(BATTERY, read_battery),
            board=part(MAIN_BOARD, read_board),
            bad=frozenset(bad),
        )
        self._cached = (now, snap)
        return snap

    def _topic_status(self, name, spec, now):
        message = self.newest.get(name)
        return TopicStatus(
            name=name,
            expected_hz=spec.expected_hz,
            hz=self.meter.hz(name, now),
            avg_hz=self.meter.average_hz(name),
            count=self.meter.total.get(name, 0),
            age_s=None if message is None else now - message.t,
            dropped=None if self.dropped is None else self.dropped.get(name, 0),
        )


# ---------------------------------------------------------------- Raw message data -> parts
# Each takes one message's data (a dict from msg_to_dict) and raises on a wrong shape.


def read_imu(imu):
    """An IMUState_ dict (secondary_imu, or the imu_state inside LowState_ / HandState_)."""
    return Imu(tuple(imu["rpy"]), tuple(imu["gyroscope"]), tuple(imu["accelerometer"]), imu["temperature"])


def read_body(lowstate):
    """A LowState_ dict -> Body: the 31 used slots by name (slots 31..34 are unused)."""
    body = []
    for slot, (name, lower, upper) in enumerate(joints.BODY_JOINTS):
        m = lowstate["motor_state"][slot]
        body.append(Joint(slot, name, m["q"], m["dq"], m["tau_est"], tuple(m["temperature"]),
                          m["mode"], m["motorstate"], lower, upper))
    return Body(tuple(body), read_imu(lowstate["imu_state"]),
                lowstate["mode_machine"], lowstate["mode_pr"], lowstate["tick"])


def read_hand(hand, side):
    """A HandState_ dict -> Hand: the 20 motor slots by name, and each pressure pad's highest reading."""
    motors = []
    for slot, (name, _, _, position_only) in enumerate(joints.HAND_JOINTS):
        m = hand["motor_state"][slot]
        temperature = None if position_only else m["temperature"][0]
        motors.append(HandMotor(slot, name, m["q"], m["dq"], m["tau_est"], temperature, m["mode"], m["motorstate"]))
    pad_max = tuple(max(pad["pressure"]) for pad in hand["press_sensor_state"])
    return Hand(side, tuple(motors), pad_max, tuple(hand["error"]), hand["power_v"], hand["power_a"],
                hand["system_v"], read_imu(hand["imu_state"]))


def read_battery(bms):
    """A BmsState_ dict -> Battery, cells trimmed to the real ones (robot/sensors.py)."""
    cells = tuple(bms["cell_vol"][: sensors.NUM_BMS_CELLS])
    min(cells)  # an empty cell list is a bad shape: raise here, not in a consumer
    return Battery(
        soc=bms["soc"],
        soh=bms["soh"],
        volts=bms["bmsvoltage"][0] / 1000,  # mV -> V; equals the sum of the cells
        current=bms["current"],
        cells=cells,
        temperatures=_trim_zeros(bms["temperature"]),
        cycle=bms["cycle"],
        state=tuple(bms["bmsstate"]),
        version=f"{bms['version_high']}.{bms['version_low']}",
    )


def read_board(board):
    """A MainBoardState_ dict -> Board, temperatures trimmed to the real ones (robot/sensors.py)."""
    return Board(tuple(board["temperature"][: sensors.NUM_MAINBOARD_TEMPS]), tuple(board["fan_state"]),
                 tuple(board["state"]), tuple(board["value"]))


def _trim_zeros(values):
    """`values` without its trailing zeros (unused slots), as a tuple."""
    end = len(values)
    while end and values[end - 1] == 0:
        end -= 1
    return tuple(values[:end])
