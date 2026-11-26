"""Rules about power: the battery's cells and charge, the hands' error field."""

from h2_bridge.checkup import limits
from h2_bridge.checkup.models import Observation, Rule, Status


def check_cell_spread(snap, memory):
    """Battery: warn/fail if the cells drift apart (max - min, mV)."""
    if not snap.battery:
        return None
    spread = snap.battery.cell_spread
    if spread >= limits.CELL_SPREAD_FAIL_MV:
        status, limit = Status.FAIL, limits.CELL_SPREAD_FAIL_MV
    elif spread >= limits.CELL_SPREAD_WARN_MV:
        status, limit = Status.WARN, limits.CELL_SPREAD_WARN_MV
    else:
        return [Observation("battery", Status.PASS, value=spread)]
    return [Observation("battery", status, f"cell spread {spread} mV ({snap.battery.cell_min}-{snap.battery.cell_max})",
                        spread, limit)]


def check_charge(snap, memory):
    """Battery: warn/fail on a low state of charge (%)."""
    if not snap.battery:
        return None
    soc = snap.battery.soc
    if soc <= limits.SOC_FAIL:
        status, limit = Status.FAIL, limits.SOC_FAIL
    elif soc <= limits.SOC_WARN:
        status, limit = Status.WARN, limits.SOC_WARN
    else:
        return [Observation("battery", Status.PASS, value=soc)]
    return [Observation("battery", status, f"charge {soc}%", soc, limit)]


def check_hand_errors(snap, memory):
    """Per hand: warn if its error field isn't all 0. What the codes mean is unknown, so warn, not fail."""
    observations = [Observation(f"{side} hand", Status.WARN, f"error {list(hand.error)}")
                    if any(hand.error) else Observation(f"{side} hand", Status.PASS)
                    for side, hand in snap.hands.items() if hand]
    return observations or None


CELL_SPREAD = Rule(
    "cell_spread", "Battery cells balanced",
    f"The battery's cells are within {limits.CELL_SPREAD_WARN_MV} mV of each other (fail at "
    f"{limits.CELL_SPREAD_FAIL_MV}).",
    check_cell_spread, hold_s=2.0, clear_s=5.0,
)
CHARGE = Rule(
    "charge", "Battery charged",
    f"State of charge above {limits.SOC_WARN}% (fail at or below {limits.SOC_FAIL}%).",
    check_charge, hold_s=2.0, clear_s=5.0,
)
HAND_ERRORS = Rule(
    "hand_errors", "No hand errors",
    "Each Dex5 hand's error field is all 0.",
    check_hand_errors, hold_s=0.5, clear_s=2.0,
)
