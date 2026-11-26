"""Rules about topics arriving: silent, stale, slow, and messages dropped."""

from h2_bridge.checkup import limits
from h2_bridge.checkup.models import Observation, Rule, Status


def check_topic_flow(snap, memory):
    """Per topic: fail if silent or stale, warn if slow, else pass."""
    start = memory.setdefault("start", snap.t)
    elapsed = snap.t - start
    observations = []
    for name, status in snap.topics.items():
        if status.count == 0:
            if elapsed >= limits.TOPIC_STARTUP_GRACE_S:
                observations.append(Observation(name, Status.FAIL, "silent: no message since the start",
                                                elapsed, limits.TOPIC_STARTUP_GRACE_S))
            continue  # still starting: no verdict yet
        stale_after = max(limits.STALE_PERIODS / status.expected_hz if status.expected_hz else 0.0,
                          limits.STALE_MIN_S)
        if status.age_s > stale_after:
            observations.append(Observation(name, Status.FAIL, f"stale: no message for {status.age_s:.1f} s",
                                            status.age_s, stale_after))
        elif (status.expected_hz and elapsed >= 2.0  # the rate window (2 s) is full
              and status.hz < limits.RATE_OK * status.expected_hz):
            observations.append(Observation(name, Status.WARN,
                                            f"slow: {status.hz:.1f} Hz of {status.expected_hz:g} expected",
                                            status.hz, limits.RATE_OK * status.expected_hz))
        else:
            observations.append(Observation(name, Status.PASS))
    return observations


def check_dropped(snap, memory):
    """Per topic: warn if the live source dropped any messages (rates and recordings are then short)."""
    if all(status.dropped is None for status in snap.topics.values()):
        return None  # a replay can't drop
    observations = []
    for name, status in snap.topics.items():
        if status.dropped:
            observations.append(Observation(name, Status.WARN, f"{status.dropped} messages dropped: the loop fell behind",
                                            status.dropped, 0))
        else:
            observations.append(Observation(name, Status.PASS))
    return observations


TOPIC_FLOW = Rule(
    "topic_flow", "Topics arriving",
    "Each topic sends messages: not silent since the start, not stale, not below "
    f"{limits.RATE_OK:.0%} of its expected rate.",
    check_topic_flow, hold_s=0.0, clear_s=1.0,  # stale/slow already mean "for a while": flag at once
)
DROPPED = Rule(
    "dropped", "No dropped messages",
    "The live source kept up: no messages were dropped because the loop fell behind.",
    check_dropped, hold_s=0.0, clear_s=0.0,
)
