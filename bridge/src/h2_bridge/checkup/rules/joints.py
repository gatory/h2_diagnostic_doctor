"""Rules about joints and motors: NaN readings, past a limit, frozen, motor error bits."""

from h2_bridge.checkup import limits
from h2_bridge.checkup.models import Observation, Rule, Status
from h2_bridge.checkup.rules.bands import band
from h2_bridge.robot.joints import MODE_PR, PR_LINKAGE_JOINTS
from h2_bridge.robot.motors import decode_motorstate
from h2_bridge.telemetry.snapshot import HANDS


def _motors(snap):
    """Every motor present: (subject, motor) for the body joints, then each hand's motors."""
    if snap.body:
        yield from ((j.name, j) for j in snap.body.joints)
    for side, hand in snap.hands.items():
        if hand:
            yield from ((f"{side}:{m.name}", m) for m in hand.motors)


def check_nan(snap, memory):
    """Per motor: fail if q, dq or tau is NaN/inf (None after msg_to_dict)."""
    observations = []
    for subject, m in _motors(snap):
        bad = [name for name in ("q", "dq", "tau") if getattr(m, name) is None]
        observations.append(Observation(subject, Status.FAIL, f"{', '.join(bad)} is NaN/inf")
                            if bad else Observation(subject, Status.PASS))
    return observations or None


def check_limits(snap, memory):
    """Per body joint: warn when q is at a limit (robot/joints.py), fail when it's forced past it.

    past = how far q is beyond its nearest limit (negative: inside). Hands aren't
    checked: whether their q uses the spec's zero is unconfirmed. In AB mode
    (mode_pr 1) the ankles' and waist's q is a raw motor position, not an angle,
    so those slots are skipped (robot/joints.py: PR_LINKAGE_JOINTS).
    """
    if not snap.body:
        return None
    angles_only = snap.body.mode_pr != MODE_PR
    observations = []
    for j in snap.body.joints:
        if j.q is None:
            continue  # check_nan reports it
        if angles_only and j.slot in PR_LINKAGE_JOINTS:
            continue  # not an angle in AB mode
        past = max(j.q - j.upper, j.lower - j.q)  # > 0: past a limit; < 0: inside
        side = "upper" if j.q - j.upper > j.lower - j.q else "lower"
        limit = j.upper if side == "upper" else j.lower
        status = band(memory, j.name, past, -limits.JOINT_AT_LIMIT, limits.JOINT_PAST_LIMIT, limits.JOINT_LIMIT_MARGIN)
        if status == Status.FAIL:
            observations.append(Observation(j.name, Status.FAIL,
                                            f"forced past its {side} limit: q {j.q:+.3f}, limit {limit:+.3f} rad",
                                            past, limits.JOINT_PAST_LIMIT))
        elif status == Status.WARN:
            observations.append(Observation(j.name, Status.WARN,
                                            f"at its {side} limit: q {j.q:+.3f}, limit {limit:+.3f} rad",
                                            past, -limits.JOINT_AT_LIMIT))
        else:
            observations.append(Observation(j.name, Status.PASS))
    return observations


def check_frozen(snap, memory):
    """Per body joint: warn if q stays bit-identical for FROZEN_S while new messages keep arriving.

    Time only counts while the body topic delivers (its tick moves): a topic that
    stops is topic_flow's finding, not 31 frozen joints.
    """
    if not snap.body:
        return None
    readings = [(j.name, j.q) for j in snap.body.joints]
    return _unchanged(memory, snap.body.tick, readings, snap.t, limits.FROZEN_S)


def check_hand_frozen(snap, memory):
    """Per hand motor: warn if q stays bit-identical for HAND_FROZEN_S while the hand's messages keep arriving.

    Hands have no tick, so "a new message arrived" is the hand topic's message
    count moving. A motor at either end of its range (within HAND_AT_STOP) is
    skipped: at its stop q is clamped and never changes (a curled finger, the
    right thumb resting on its stop: docs/robot_findings.md).
    """
    observations = []
    for side, hand in snap.hands.items():
        if not hand:
            continue
        readings = [(f"{side}:{m.name}", None if _at_stop(m) else m.q) for m in hand.motors]
        count = snap.topics[HANDS[side]].count
        observations += _unchanged(memory.setdefault(side, {}), count, readings, snap.t, limits.HAND_FROZEN_S)
    return observations or None


def _at_stop(motor):
    """True if a hand motor sits at an end of its range, where its reading is clamped."""
    return motor.q is not None and min(abs(motor.q - motor.lower), abs(motor.q - motor.upper)) <= limits.HAND_AT_STOP


def _unchanged(memory, marker, readings, now, window):
    """Observations for [(subject, q)]: warn once a q has been bit-identical for `window` seconds
    and at least FROZEN_MIN_SAMPLES new messages.

    `marker` changes whenever a new message arrived (a tick, a message count). While
    it doesn't, nothing new is judged and the last observations are returned as
    they were, so a topic that stops is never read as frozen joints.
    """
    if memory.get("marker") == marker:
        return memory.get("last") or []  # no new message: nothing new to judge
    memory["marker"] = marker
    last = memory.setdefault("q", {})  # subject -> (q, since when unchanged, how many samples since)
    observations = []
    for subject, q_now in readings:
        if q_now is None:  # NaN (joint_nan reports it), or a hand motor at its stop
            last.pop(subject, None)
            observations.append(Observation(subject, Status.PASS))
            continue
        q, since, samples = last.get(subject, (None, now, 0))
        if q != q_now:
            last[subject] = (q_now, now, 1)
            observations.append(Observation(subject, Status.PASS))
            continue
        last[subject] = (q, since, samples + 1)
        unchanged = now - since
        if unchanged >= window and samples + 1 >= limits.FROZEN_MIN_SAMPLES:
            observations.append(Observation(subject, Status.WARN, f"q unchanged for {unchanged:.1f} s (stuck reading?)",
                                            unchanged, window))
        else:
            observations.append(Observation(subject, Status.PASS))
    memory["last"] = observations
    return observations


def check_motor_errors(snap, memory):
    """Per motor: warn if motorstate (error bits) isn't 0, naming the bits (robot/motors.py, from Unitree's docs)."""
    observations = []
    for subject, m in _motors(snap):
        if m.motorstate:
            names = ", ".join(decode_motorstate(m.motorstate))
            observations.append(Observation(subject, Status.WARN, f"motorstate 0x{m.motorstate:X}: {names}",
                                            m.motorstate, 0))
        else:
            observations.append(Observation(subject, Status.PASS))
    return observations or None


JOINT_NAN = Rule(
    "joint_nan", "No NaN joint readings",
    "Every body and hand motor reports real numbers for q, dq and tau.",
    check_nan, hold_s=0.0, clear_s=1.0,
)
JOINT_LIMITS = Rule(
    "joint_limits", "Joints within limits",
    f"Each body joint stays inside its limits (robot/joints.py): warn when within {limits.JOINT_AT_LIMIT} rad "
    f"of a limit (at it), fail when more than {limits.JOINT_PAST_LIMIT} rad past it (forced beyond).",
    check_limits, hold_s=0.0, clear_s=0.0,  # instant; band()'s margin stops flicker
)
JOINT_FROZEN = Rule(
    "joint_frozen", "Joint readings change",
    f"No body joint's q stays bit-identical for {limits.FROZEN_S:g} s while messages arrive (encoder noise "
    "always moves it a little).",
    check_frozen, hold_s=0.0, clear_s=0.5,
)
HAND_FROZEN = Rule(
    "hand_frozen", "Hand readings change",
    f"No hand motor's q stays bit-identical for {limits.HAND_FROZEN_S:g} s while the hand's messages arrive, "
    f"except at an end of its range (within {limits.HAND_AT_STOP} rad), where the reading is clamped.",
    check_hand_frozen, hold_s=0.0, clear_s=0.5,
)
MOTOR_ERRORS = Rule(
    "motor_errors", "No motor error bits",
    "motorstate is 0 on every body and hand motor.",
    check_motor_errors, hold_s=0.0, clear_s=1.0,  # error bits are a fact: flag at once
)
