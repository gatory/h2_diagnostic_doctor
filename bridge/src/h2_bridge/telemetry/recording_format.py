"""The recording file format: written by RecordingWriter, read by RecordingReader.

Gzipped JSON Lines, one object per line: a header, every message in arrival
order, then a footer when the recording closes.

    {"recording": 1, "started": "2026-11-24T15:01:02-07:00", "host": "thor", "interface": "eth10",
     "domain_id": 0, "topics": {"rt/lf/lowstate": {"type": "unitree_hg::msg::dds_::LowState_", "expected_hz": 20.0}}}
    {"t": 1764000062.12, "topic": "rt/lf/lowstate", "data": {...}}
    {"end": "2026-11-24T15:02:03-07:00", "duration_s": 61.0, "messages": 11300, "dropped": {"rt/lf/lowstate": 0},
     "avg_hz": {"rt/lf/lowstate": 20.01}}

avg_hz is each topic's average rate over the recording (None below 2 messages);
footers written before it existed don't have it.

No footer means the recorder died (power loss, kill -9). Plain .jsonl files
(made before gzip) are still read. Files live in
outputs/telemetry/<date>/<name>_<time>_<interface>.jsonl.gz (via utils/output_paths.py).
"""

import gzip
import json
import socket
import time
import zlib
from datetime import datetime

from h2_bridge.telemetry.models import Message, TopicSpec
from h2_bridge.telemetry.rate_meter import RateMeter
from h2_bridge.utils.sdk_type_lookup import lookup_type

FORMAT_VERSION = 1

# gzip level: 6 shrinks recordings ~10x for ~1% of a core; 9 costs 4x the CPU for ~7% smaller.
COMPRESS_LEVEL = 6

_GZIP_MAGIC = b"\x1f\x8b"

# What reading a gzip file that was cut off (recorder killed mid-write) raises.
_CUT_OFF = (EOFError, zlib.error, gzip.BadGzipFile)


class RecordingWriter:
    """Write every message from a LiveSource to a new recording file.

        with LiveSource("eth10", 0, CORE_TOPICS) as source, RecordingWriter(source) as rec:
            rec.write(source.poll())

    close() writes the footer (end time, message count, the source's `dropped`, and
    each topic's average rate, measured from the messages written).

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
        self._rates = RateMeter()  # its own, so the footer's rates never depend on the caller
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
        self._rates.add(messages)
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
            "dropped": dict(self._source.dropped or {}),
            "avg_hz": self._rates.average_rates(self._source.topics),
        })
        self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()


class RecordingReader:
    """Walk a recording one message at a time, then say how it ended.

        with RecordingReader(path) as reader:
            reader.header, reader.topics       # read on open
            while (m := reader.next_message()) is not None:
                ...
            reader.footer, reader.truncated    # how it ended, once next_message() returned None

    One line at a time, so long recordings never have to fit in memory. Reads
    gzipped (.jsonl.gz) and plain (.jsonl) files. A file cut off mid-write (the
    recorder was killed) ends early with `truncated` set; damage in the middle
    of a file raises.

    Attributes
    ----------
    header : dict
        The first line: started, host, interface, domain_id, topics.
    topics : dict[str, TopicSpec]
        Every topic the recording holds.
    footer : dict | None
        The last line (end, duration_s, messages, dropped, avg_hz) once reached;
        stays None if the recorder died before writing it.
    truncated : bool
        True if the file was cut off; the cut-off part is skipped.
    """

    def __init__(self, path):
        self.path = path
        self.footer = None
        self.truncated = False
        self._ended = False
        self._file = _open_text(path)
        try:
            self.header, self.topics = self._read_header()
        except Exception:
            self._file.close()  # not a recording: don't leak the handle
            raise

    def next_message(self):
        """The next Message, or None at the end (footer, end of file, or cut off)."""
        if self._ended:
            return None
        line = self._next_line()
        if line is None:
            return self._end()
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            if not self._rest_is_empty():  # more after it: real corruption
                raise
            self.truncated = True  # cut-off last line: treat as the end
            return self._end()
        if "end" in record:  # the footer: the recording ends here
            self.footer = record
            return self._end()
        return Message(record["t"], record["topic"], record["data"])

    def close(self):
        """Close the file. Safe to call twice."""
        self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def _read_header(self):
        header = json.loads(self._file.readline() or "null")
        if not isinstance(header, dict) or header.get("recording") != FORMAT_VERSION:
            raise ValueError(f"{self.path}: not an h2-doctor recording (version {FORMAT_VERSION})")
        topics = {
            name: TopicSpec(name, _sdk_class(info["type"]), info["expected_hz"])
            for name, info in header["topics"].items()
        }
        return header, topics

    def _next_line(self):
        """The next line, or None at the end of the file (or where a cut-off gzip stream stops)."""
        try:
            return next(self._file, None)
        except _CUT_OFF:
            self.truncated = True
            return None

    def _rest_is_empty(self):
        """True if nothing readable follows (a cut-off gzip tail counts as nothing)."""
        try:
            return not self._file.read().strip()
        except _CUT_OFF:
            return True

    def _end(self):
        self._ended = True
        return None


def _open_text(path):
    """Open a recording as text: gzipped or plain, told apart by its first bytes."""
    with open(path, "rb") as f:
        gzipped = f.read(2) == _GZIP_MAGIC
    return gzip.open(path, "rt", encoding="utf-8") if gzipped else open(path, encoding="utf-8")


def _sdk_class(type_name):
    """"unitree_hg::msg::dds_::LowState_" (or the "." form) -> the SDK's LowState_ class."""
    cls = lookup_type(type_name)
    if cls is None:
        raise ValueError(f"recording uses type {type_name!r}, which this SDK doesn't have")
    return cls
