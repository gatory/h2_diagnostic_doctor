"""The recording file format: written by RecordingWriter, read by ReplaySource.

JSON Lines, one object per line: a header first, then every message in arrival order.

    {"recording": 1, "started": "2026-11-24T15:01:02-07:00", "host": "thor", "interface": "eth10",
     "domain_id": 0, "topics": {"rt/lf/lowstate": {"type": "unitree_hg::msg::dds_::LowState_", "expected_hz": 20.0}}}
    {"t": 1764000062.12, "topic": "rt/lf/lowstate", "data": {...}}

Files live in outputs/telemetry/<date>/<name>_<time>_<interface>.jsonl (via utils/outputs.py).
"""

import json
import socket
from datetime import datetime

from h2_bridge.telemetry.models import Message, TopicSpec
from h2_bridge.utils.sdk_types import lookup_type

FORMAT_VERSION = 1


class RecordingWriter:
    """Write every message from a LiveSource to a new recording file.

        with LiveSource("eth10", 0, CORE_TOPICS) as source, RecordingWriter(source) as rec:
            rec.write(source.poll())

    Attributes
    ----------
    path : Path
        Where the recording is being written.
    count : int
        Messages written so far.
    """

    def __init__(self, source, name="recording"):
        from h2_bridge.utils.outputs import output_path

        started = datetime.now().astimezone()
        self.path = output_path("telemetry", name, source.interface, when=started, ext="jsonl")
        self.count = 0
        self._file = open(self.path, "x", encoding="utf-8")  # "x": never overwrite a recording
        header = {
            "recording": FORMAT_VERSION,
            "started": started.isoformat(timespec="seconds"),
            "host": socket.gethostname(),
            "interface": source.interface,
            "domain_id": source.domain_id,
            "topics": {
                name: {"type": spec.type_name, "expected_hz": spec.expected_hz}
                for name, spec in source.topics.items()
            },
        }
        self._write_line(header)

    def write(self, messages):
        """Append `messages` (one poll's worth) and flush, so a crash loses at most this batch."""
        for m in messages:
            self._write_line({"t": m.t, "topic": m.topic, "data": m.data})
        self.count += len(messages)
        self._file.flush()

    def _write_line(self, obj):
        self._file.write(json.dumps(obj, allow_nan=False, separators=(",", ":")) + "\n")

    def close(self):
        """Close the file. Safe to call twice."""
        if not self._file.closed:
            self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()


def read_header(file):
    """Read the header line from an open recording; returns (header dict, {name: TopicSpec})."""
    header = json.loads(file.readline() or "null")
    if not isinstance(header, dict) or header.get("recording") != FORMAT_VERSION:
        raise ValueError(f"{file.name}: not an h2-doctor recording (version {FORMAT_VERSION})")
    topics = {
        name: TopicSpec(name, _sdk_class(info["type"]), info["expected_hz"])
        for name, info in header["topics"].items()
    }
    return header, topics


def read_message(line):
    """One message line -> Message."""
    record = json.loads(line)
    return Message(record["t"], record["topic"], record["data"])


def _sdk_class(type_name):
    """"unitree_hg::msg::dds_::LowState_" (or the "." form) -> the SDK's LowState_ class."""
    cls = lookup_type(type_name)
    if cls is None:
        raise ValueError(f"recording uses type {type_name!r}, which this SDK doesn't have")
    return cls
