"""Data model for one discovery run.

A Snapshot holds plain facts about what was seen on the DDS network.
It does no grouping or interpretation; that happens later, in analysis code.
Keeping the raw facts means a snapshot recorded on the robot can be
re-analyzed later on any machine.
"""

from dataclasses import dataclass, field
from typing import Literal

EndpointKind = Literal["writer", "reader"]


@dataclass
class Participant:
    """One DDS participant, roughly one program on the network."""

    key: str
    # Extra identifying info some programs attach to their QoS (may be empty).
    properties: dict[str, str] = field(default_factory=dict)


@dataclass
class Endpoint:
    """One writer or reader on a topic."""

    key: str
    participant_key: str  # which Participant owns this endpoint
    kind: EndpointKind
    topic_name: str
    type_name: str  # stored per endpoint: one topic can carry several types
    reliability: str | None = None  # e.g. "reliable" / "best_effort"
    durability: str | None = None  # e.g. "volatile" / "transient_local"


@dataclass
class Snapshot:
    """Everything seen during one discovery run, plus how it was taken."""

    taken_at: str  # ISO 8601 timestamp of when the run started
    host: str  # machine the run happened on
    iface: str
    domain: int
    duration_s: float
    participants: list[Participant] = field(default_factory=list)
    endpoints: list[Endpoint] = field(default_factory=list)
