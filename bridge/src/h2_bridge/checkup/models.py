"""Data model for checkup: statuses, what a rule reports, and what a finding is.

    Status        pass / warn / fail / no data
    Observation   one rule's verdict on one subject (a topic, joint, hand...) at one moment
    Rule          a named check: Snapshot (+ its own memory) -> Observations
    Finding       an Observation that has held long enough to count (debounced), with since when

Rules report raw Observations every poll; the engine (engine.py) debounces them
into Findings, so a value hovering at a limit doesn't flicker on and off.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Callable


class Status(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    NO_DATA = "no data"  # the rule's inputs never arrived: reported, never counted as a pass

    @property
    def rank(self):
        """Severity for "worst of": no data < pass < warn < fail."""
        return _RANK[self]


_RANK = {Status.NO_DATA: -1, Status.PASS: 0, Status.WARN: 1, Status.FAIL: 2}


@dataclass(frozen=True)
class Observation:
    """What a rule sees on one subject right now (not yet debounced)."""

    subject: str  # e.g. "rt/lf/lowstate", "L_elbow", "left hand", "battery"
    status: Status
    message: str = ""  # e.g. "no message for 2.3 s"
    value: float | None = None  # the measured value, for the report
    limit: float | None = None  # the limit it was compared with


@dataclass(frozen=True)
class Rule:
    """One check.

    `check(snapshot, memory)` returns a list of Observations, one per subject it
    looked at (passing ones too), or None when its inputs aren't there (no data).
    `memory` is a dict the engine keeps for this rule across polls, for rules
    that need history (e.g. "unchanged for 5 s"); most rules ignore it.

    An observation worse than the current status must hold for `hold_s` (on the
    source's clock) before it counts; a better one must hold for `clear_s`.
    """

    name: str  # stable id, e.g. "topic_flow" (used in reports and by the dashboard)
    title: str  # e.g. "Topics arriving"
    description: str
    check: Callable
    hold_s: float = 1.0 
    clear_s: float = 2.0


@dataclass(frozen=True)
class Finding:
    """A debounced, non-passing observation: what the warnings panel and the report list."""

    rule: str
    subject: str
    status: Status
    message: str
    value: float | None
    limit: float | None
    since: float  # the source's clock when it started counting
