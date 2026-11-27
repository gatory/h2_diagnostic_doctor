"""Finding out which FSM id is which mode: read the robot's state while a person changes it.

    queries = RobotQueries()
    names = fsm_names(queries.ask("available_fsms"))   # {1: "Passive", 4: "FixStand", ...}
    reading = read_fsm(queries)                        # FsmReading(fsm_id=601, stable=True, ...)
    save_fsm_map(steps_done, names, "eth10")           # outputs/discovery/<date>/fsm_map_<time>_eth10.json

The person changes modes with the remote; nothing here changes the robot (only the
allowlisted getters in robot_queries.py). Used by `h2-doctor discovery modes --watch / --map`.
"""

import time
from dataclasses import asdict, dataclass, field
from datetime import datetime

# The modes the dashboard's gear row shows, in the order to step through them with the remote.
# Which FSM id each one is: unknown until a --map run says so.
WALKTHROUGH = [
    ("zero_torque", "Zero torque"),
    ("damp", "Damp"),
    ("ready", "Ready"),
    ("walk1", "Walk 1"),
    ("walk2", "Walk 2"),
]


@dataclass(frozen=True)
class FsmReading:
    """The FSM state, read a few times in a row."""

    fsm_id: int | None  # the last reading; None if the robot didn't answer
    stable: bool  # every reading agreed (False: it was still changing, or some went unanswered)
    seen: list = field(default_factory=list)  # every reading, in order (None = no answer)
    motion_mode: str | None = None  # CheckMode's "name", e.g. "ai"


def fsm_names(answer):
    """{fsm id: name} from an `available_fsms` Answer; {} if it wasn't answered."""
    if not answer.ok or not isinstance(answer.value, tuple) or len(answer.value) != 2:
        return {}
    ids, names = answer.value
    return dict(zip(ids, names))


def read_fsm(queries, samples=3, gap_s=0.5):
    """Read the FSM id `samples` times, `gap_s` apart, so a mode that's still switching shows up."""
    seen = []
    for i in range(samples):
        if i:
            time.sleep(gap_s)
        answer = queries.ask("fsm_id")
        seen.append(answer.value if answer.ok else None)
    mode = queries.ask("motion_mode")
    motion = mode.value.get("name") if mode.ok and isinstance(mode.value, dict) else None
    return FsmReading(seen[-1], len(set(seen)) == 1 and seen[-1] is not None, seen, motion)


def save_fsm_map(steps, names, interface, when=None):
    """Save a --map run as JSON and return the path.

    steps: [(gear id, gear label, FsmReading | None)], None for a skipped step.
    """
    import json

    from h2_bridge.utils.output_paths import output_path

    when = when or datetime.now()
    path = output_path("discovery", "fsm_map", interface, when=when)
    data = {
        "taken_at": when.isoformat(timespec="seconds"),
        "interface": interface,
        "gears": {
            gear: None if reading is None else {
                "label": label,
                "fsm_id": reading.fsm_id,
                "fsm_name": names.get(reading.fsm_id),
                **asdict(reading),
            }
            for gear, label, reading in steps
        },
        "available_fsms": {str(i): n for i, n in names.items()},
    }
    with open(path, "x") as f:
        json.dump(data, f, indent=2)
    return path
