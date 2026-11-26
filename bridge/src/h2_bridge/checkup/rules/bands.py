"""band(): one way to grade a value against warn/fail thresholds, with hysteresis.

    status = band(memory, "battery", spread, warn=50, fail=100, margin=10)
    status = band(memory, "battery", soc, warn=20, fail=10, margin=2, higher_is_bad=False)

A value at or beyond `warn` is WARN, at or beyond `fail` is FAIL: instantly, no
waiting. Hysteresis keeps it from flickering: once a level is on, it stays on
until the value is `margin` back on the good side of that level's threshold.
So a cell spread that hits 50 mV warns at once, and only clears below 40 mV,
however long it hovers around 50.
"""

from h2_bridge.checkup.models import Status


def band(memory, subject, value, warn, fail, margin=0.0, higher_is_bad=True):
    """The Status for `value`, given the thresholds and what this subject's level was last time."""
    sign = 1 if higher_is_bad else -1  # flip so "bigger is worse" for both directions
    v, w, f = sign * value, sign * warn, sign * fail
    levels = memory.setdefault("bands", {})
    previous = levels.get(subject, Status.PASS)

    if v >= f or (previous == Status.FAIL and v >= f - margin):
        status = Status.FAIL
    elif v >= w or (previous.rank >= Status.WARN.rank and v >= w - margin):
        status = Status.WARN
    else:
        status = Status.PASS
    levels[subject] = status
    return status
