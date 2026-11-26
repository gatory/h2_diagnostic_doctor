"""The recording file format: written by RecordingWriter, read by ReplaySource.

Gzipped JSON Lines, one object per line: a header, every message in arrival
order, then a footer when the recording closes.

    {"recording": 1, "started": "2026-11-24T15:01:02-07:00", "host": "thor", "interface": "eth10",
     "domain_id": 0, "topics": {"rt/lf/lowstate": {"type": "unitree_hg::msg::dds_::LowState_", "expected_hz": 20.0}}}
    {"t": 1764000062.12, "topic": "rt/lf/lowstate", "data": {...}}
    {"end": "2026-11-24T15:02:03-07:00", "duration_s": 61.0, "messages": 11300, "dropped": {"rt/lf/lowstate": 0}}

No footer means the recorder died (power loss, kill -9). Plain .jsonl files
(made before gzip) are still read. Files live in
outputs/telemetry/<date>/<name>_<time>_<interface>.jsonl.gz (via utils/output_paths.py).
"""

import gzip
import json
import socket
import time
from datetime import datetime

from h2_bridge.telemetry.models import Message, TopicSpec
from h2_bridge.utils.sdk_type_lookup import lookup_type

FORMAT_VERSION = 1

# gzip level: 6 shrinks recordings ~10x for ~1% of a core; 9 costs 4x the CPU for ~7% smaller.
COMPRESS_LEVEL = 6

_GZIP_MAGIC = b"\x1f\x8b"


class RecordingWriter:
    """Write every message from a LiveSource to a new recording file.

        with LiveSource("eth10", 0, CORE_TOPICS) as source, RecordingWriter(source) as rec:
            rec.write(source.poll())

    close() writes the footer (end time, message count, the source's `dropped`).

    Attributes
    ----------
    path : Path
        Where the recording is being written.
    count : int
        Messages written so far.
    """

    def __init__(self, source, name="recording"):
        from h2_bridge.utils.output_paths import output_path

        started = datetime.now().astimezone()
        self.path = output_path("telemetry", name, source.interface, when=started, ext="jsonl.gz")
        self.count = 0
        self._source = source
        self._started = time.monotonic()
        # "x": never overwrite a recording
        self._file = gzip.open(self.path, "xb", compresslevel=COMPRESS_LEVEL)
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
        self._file.flush()  # gzip sync flush: everything so far is decodable

    def _write_line(self, obj):
        line = json.dumps(obj, allow_nan=False, separators=(",", ":")) + "\n"
        self._file.write(line.encode("utf-8"))

    def close(self):
        """Write the footer and close the file. Safe to call twice."""
        if self._file.closed:
            return
        self._write_line({
            "end": datetime.now().astimezone().isoformat(timespec="seconds"),
            "duration_s": round(time.monotonic() - self._started, 1),
            "messages": self.count,
            "dropped": dict(getattr(self._source, "dropped", {})),
        })
        self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()


def open_recording(path):
    """Open a recording for reading as text: gzipped or plain, told apart by its first bytes."""
    with open(path, "rb") as f:
        gzipped = f.read(2) == _GZIP_MAGIC
    return gzip.open(path, "rt", encoding="utf-8") if gzipped else open(path, encoding="utf-8")


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


def read_line(line):
    """One line after the header -> a Message, or the footer as a dict (it has an "end" key)."""
    record = json.loads(line)
    if "end" in record:
        return record
    return Message(record["t"], record["topic"], record["data"])


def _sdk_class(type_name):
    """"unitree_hg::msg::dds_::LowState_" (or the "." form) -> the SDK's LowState_ class."""
    cls = lookup_type(type_name)
    if cls is None:
        raise ValueError(f"recording uses type {type_name!r}, which this SDK doesn't have")
    return cls
