"""All of checkup's rules, in report order.

Each rule only reads fields whose meaning is confirmed (docs/robot_findings.md);
unknown fields (fan_state, bmsstate, mode, the hand IMU temperature) and
temperatures (no published limits, units unconfirmed) are never judged.
"""

from h2_bridge.checkup.rules.imus import IMU_AGREEMENT
from h2_bridge.checkup.rules.joints import HAND_FROZEN, JOINT_FROZEN, JOINT_LIMITS, JOINT_NAN, MOTOR_ERRORS
from h2_bridge.checkup.rules.power import CELL_SPREAD, CHARGE, HAND_ERRORS
from h2_bridge.checkup.rules.topics import DROPPED, TOPIC_FLOW

RULES = [
    TOPIC_FLOW,
    DROPPED,
    JOINT_NAN,
    JOINT_LIMITS,
    JOINT_FROZEN,
    HAND_FROZEN,
    MOTOR_ERRORS,
    HAND_ERRORS,
    CELL_SPREAD,
    CHARGE,
    IMU_AGREEMENT,
]
