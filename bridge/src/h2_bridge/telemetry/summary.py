"""One-line summaries of a message, for the Summary column of `telemetry watch`.

Only fields whose meaning the MVP checked (its docs/field_map.md) are shown,
named after the field so nothing pretends to be more certain than it is.
A "?" marks a unit that is likely but unconfirmed. Slot counts come from layout.py.

    summarize(CORE_TOPICS["rt/lf/bmsstate"], message.data)   # "soc 87% · 52.0 V · current -2100 (mA?)"
"""

from h2_bridge.telemetry import layout


def summarize(spec, data):
    """Short text describing one message's data (a dict from to_dict)."""
    summarizer = _BY_TYPE.get(spec.msg_type.__name__, _generic)
    try:
        return summarizer(data)
    except (KeyError, IndexError, TypeError, ValueError):
        return "(unexpected message shape)"  # never let one odd message crash the display


def _low_state(d):
    joints = d["motor_state"][:layout.NUM_BODY_JOINTS]  # slots 31..34 are unused
    hottest = max(m["temperature"][0] for m in joints)
    return f"tick {d['tick']} · hottest joint {hottest} °C? · mode_machine {d['mode_machine']}"


def _imu(d):
    roll, pitch, yaw = d["rpy"]
    return f"rpy {roll:+.3f} {pitch:+.3f} {yaw:+.3f} rad"


def _bms(d):
    volts = d["bmsvoltage"][0] / 1000  # mV -> V
    return f"soc {d['soc']}% · {volts:.1f} V · current {d['current']} (mA?)"


def _main_board(d):
    temps = " ".join(str(t) for t in d["temperature"][:layout.NUM_MAINBOARD_TEMPS])
    return f"temps {temps} °C?"


def _hand(d):
    motors = d["motor_state"][:layout.NUM_HAND_ACTIVE_MOTORS]  # the thumb reports no temperature
    hottest = max(m["temperature"][0] for m in motors) if motors else "-"
    return f"{len(d['motor_state'])} motors · hottest {hottest} °C? · error {d['error']}"


def _string(d):
    return d["data"]


def _generic(d):
    return ", ".join(f"{k}={v}" for k, v in d.items() if isinstance(v, (int, float, str)))[:80]


_BY_TYPE = {
    "LowState_": _low_state,
    "IMUState_": _imu,
    "BmsState_": _bms,
    "MainBoardState_": _main_board,
    "HandState_": _hand,
    "String_": _string,
}
