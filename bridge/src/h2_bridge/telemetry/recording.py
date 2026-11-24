"""The recording file format: written by RecordingWriter, read by ReplaySource.

JSON Lines, one object per line: a header first, then every message in arrival order.

    {"recording": 1, "started": "2026-11-24T15:01:02", "interface": "eth10", "domain_id": 0,
     "topics": {"rt/lf/lowstate": {"type": "unitree_hg.msg.dds_.LowState_", "expected_hz": 20.0, "feeds": "..."}}}
    {"t": 1764000062.12, "topic": "rt/lf/lowstate", "data": {...}}

Files live in outputs/telemetry/<date>/<name>_<time>_<interface>.jsonl (via outputs.py).
"""

import importlib
import json
from datetime import datetime

from h2_bridge.telemetry.models import Message, TopicSpec

FORMAT_VERSION = 1


class RecordingWriter:
    """Append every message from a LiveSource to a new recording file.

        with LiveSource("eth10", 0) as source, RecordingWriter(source) as rec:
            rec.write(source.poll())
    """

    def __init__(self, source, name="recording"):
        from h2_bridge.outputs import output_path

        started = datetime.now()
        self.path = output_path("telemetry", name, source.interface, when=started, ext="jsonl")
        self._file = open(self.path, "w")
        header = {
            "recording": FORMAT_VERSION,
            "started": started.isoformat(timespec="seconds"),
            "interface": source.interface,
            "domain_id": source.domain_id,
            "topics": {
                name: {"type": spec.msg_type.__idl_typename__, "expected_hz": spec.expected_hz, "feeds": spec.feeds}
                for name, spec in source.topics.items()
            },
        }
        self._file.write(json.dumps(header) + "\n")

    def write(self, messages):
        for m in messages:
            self._file.write(json.dumps({"t": m.t, "topic": m.topic, "data": m.data}) + "\n")

    def close(self):
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
        name: TopicSpec(_sdk_class(info["type"]), info["expected_hz"], info.get("feeds", ""))
        for name, info in header["topics"].items()
    }
    return header, topics


def read_message(line):
    """One message line -> Message."""
    record = json.loads(line)
    return Message(record["t"], record["topic"], record["data"])


def _sdk_class(type_name):
    """"unitree_hg.msg.dds_.LowState_" -> the SDK's LowState_ class."""
    module_name, _, class_name = type_name.rpartition(".")
    try:
        return getattr(importlib.import_module(f"unitree_sdk2py.idl.{module_name}"), class_name)
    except (ImportError, AttributeError):
        raise ValueError(f"recording uses type {type_name!r}, which this SDK doesn't have") from None
