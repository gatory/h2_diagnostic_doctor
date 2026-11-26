"""One-line summaries of a message, for the Summary column of `telemetry watch`.

Only fields whose meaning is checked (h2_bridge.robot, docs/robot_findings.md, the
MVP's field map) are shown, named after the field. A "?" marks a unit that is
likely but unconfirmed. Covers the core 6 topics' types; anything else gets a
generic summary of its plain fields.

    summarize(CORE_TOPICS["rt/lf/bmsstate"], message.data)
    # "soc 57% · 67.25 V · current -2812 (mA?) · cells 3733-3738 mV"
"""

from h2_bridge.robot import joints, sensors

# Hand slots that report a temperature: the fingers, not the position-only thumb.
_HAND_HEATED = [i for i, (_, _, _, position_only) in enumerate(joints.HAND_JOINTS) if not position_only]


def summarize(spec, data):
    """Short text describing one message's data (a dict from msg_to_dict)."""
    summarizer = _BY_TYPE.get(spec.type_name, _generic)
    try:
        return summarizer(data)
    except (KeyError, IndexError, TypeError, ValueError):
        return "[dim](unexpected message shape)[/]"  # one odd message must never crash the display


def _low_state(d):
    motors = d["motor_state"][: joints.NUM_BODY_JOINTS]  # slots 31..34 are unused
    slot = max(range(len(motors)), key=lambda i: motors[i]["temperature"][0])
    name = joints.BODY_JOINTS[slot][0]
    return f"hottest joint {motors[slot]['temperature'][0]} °C? ({name}) · mode_machine {d['mode_machine']} · tick {d['tick']}"


def _imu(d):
    roll, pitch, yaw = d["rpy"]
    return f"rpy {roll:+.3f} {pitch:+.3f} {yaw:+.3f} rad"


def _bms(d):
    volts = d["bmsvoltage"][0] / 1000  # mV -> V; equals the sum of the cells
    cells = d["cell_vol"][: sensors.NUM_BMS_CELLS]
    return f"soc {d['soc']}% · {volts:.2f} V · current {d['current']} (mA?) · cells {min(cells)}-{max(cells)} mV"


def _main_board(d):
    temps = " ".join(str(t) for t in d["temperature"][: sensors.NUM_MAINBOARD_TEMPS])
    return f"temps {temps} °C?"


def _hand(d):
    motors = d["motor_state"]
    slot = max(_HAND_HEATED, key=lambda i: motors[i]["temperature"][0])
    name = joints.HAND_JOINTS[slot][0]
    return f"hottest {motors[slot]['temperature'][0]} °C? ({name}) · error {d['error']}"


def _generic(d):
    return ", ".join(f"{k}={v}" for k, v in d.items() if isinstance(v, (int, float, str)))[:80]


_BY_TYPE = {
    "unitree_hg::msg::dds_::LowState_": _low_state,
    "unitree_hg::msg::dds_::IMUState_": _imu,
    "unitree_hg::msg::dds_::BmsState_": _bms,
    "unitree_hg::msg::dds_::MainBoardState_": _main_board,
    "unitree_hg::msg::dds_::HandState_": _hand,
}
