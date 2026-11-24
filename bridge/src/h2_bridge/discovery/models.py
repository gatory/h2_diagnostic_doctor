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
    """One DDS participant: one connection a program opened to the DDS network.

    Usually one per program, but a program can open several participants.
    Its properties say which program (process name, PID) and which
    computer (hostname, IP) it belongs to.
    """

    key: str
    # Extra identifying info some programs attach to their QoS (may be empty).
    properties: dict[str, str] = field(default_factory=dict)


@dataclass
class Endpoint:
    """One writer or reader on a topic."""

    key: str
    participant_key: str  # endpoint owner ID
    kind: EndpointKind
    topic_name: str
    type_name: str  # msg type
    qos: dict = field(default_factory=dict) # QoS policies as a dict, for inspection
    has_type_info: bool = False # True if it announced a type ID (its type definition may be fetchable)


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
