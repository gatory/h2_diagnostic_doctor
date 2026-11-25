"""Data model for telemetry: which topics we read, and the messages they carry.

    TopicSpec   one topic we know how to read (name, SDK class, expected rate)
    Message     one message received from a topic, as plain data

A Message is the same whether it came from the robot or a recording, so
everything downstream (watch, the recorder, the dashboard server) works
on either.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TopicSpec:
    """One topic the bridge subscribes to. Frozen: this is fixed config, not state."""

    name: str  # e.g. "rt/lf/lowstate"
    msg_type: type  # SDK message class that decodes it, e.g. LowState_
    expected_hz: float | None  # rate measured on the Thor; None if not measured yet

    @property
    def type_name(self):
        """DDS type name as discovery reports it, e.g. "unitree_hg::msg::dds_::LowState_"."""
        return self.msg_type.__idl_typename__.replace(".", "::")


@dataclass
class Message:
    """One message from one topic."""

    t: float  # arrival time, seconds since the epoch (time.time())
    topic: str  # e.g. "rt/lf/lowstate"
    data: dict  # the decoded message as plain, JSON-safe Python data
