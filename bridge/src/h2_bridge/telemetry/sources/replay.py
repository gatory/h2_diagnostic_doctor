"""ReplaySource: plays a recording back as if it were the robot. No DDS.

poll() returns every message whose time has come, keeping the recording's
original gaps (scaled by `speed`) and its original timestamps. now() runs on
the recording's clock, so ages and rates measured on a replay match the live
run. The file is read line by line, so long recordings don't have to fit in memory.
"""

import difflib
import json
import time

from h2_bridge.telemetry.recording import read_header, read_message
from h2_bridge.telemetry.sources.base import Source, TopicError


class ReplaySource(Source):
    """Recording `path` at `speed` x real time.

    `topics` is a list of names to keep (None: everything recorded). Names, not
    TopicSpecs: what a recording holds is only known once it's opened.

    Attributes
    ----------
    done : bool
        True once every message has been handed out.
    truncated : bool
        True if the last line was cut off (recording killed mid-write); it is skipped.
    """

    live = False

    def __init__(self, path, topics=None, speed=1.0):
        if speed <= 0:
            raise ValueError(f"speed must be > 0, got {speed}")
        self.path = path
        self.speed = speed
        self.done = False
        self.truncated = False
        self._started = None
        self._file = open(path, encoding="utf-8")
        try:
            self.header, recorded = read_header(self._file)
            super().__init__(_select_topics(recorded, topics))  # TopicError if not recorded
            self._next = self._read_next()  # first message, kept until its time comes
        except Exception:
            self._file.close()  # bad file or topic: don't leak the handle
            raise
        self._first_t = None if self._next is None else self._next.t

    def start(self):
        """Start the playback clock. Calling it again does nothing."""
        if self._started is None:
            self._started = time.monotonic()
        return self

    def poll(self):
        """Every message due by now on the playback clock, oldest first. Starts playback if needed."""
        self.start()
        end = self.now()
        due = []
        while self._next is not None and self._next.t <= end:
            due.append(self._next)
            self._next = self._read_next()
        if self._next is None:
            self.done = True
        return due

    def now(self):
        """Where playback is, in recording time (same units as Message.t)."""
        if self._first_t is None:  # empty recording
            return 0.0
        if self._started is None:
            return self._first_t
        return self._first_t + (time.monotonic() - self._started) * self.speed

    def _read_next(self):
        """Next message on one of our topics, or None at the end of the file."""
        for line in self._file:
            try:
                message = read_message(line)
            except json.JSONDecodeError:
                if self._file.read().strip():  # more after it: real corruption
                    raise
                self.truncated = True  # cut-off last line: treat as the end
                return None
            if message.topic in self.topics:
                return message
        return None

    def close(self):
        """Close the file. Safe to call twice."""
        self._file.close()


def _select_topics(recorded, names=None):
    """{name: TopicSpec} for `names` from the recording's topics (None: all of them).

    Raises TopicError, with close matches, for a name that wasn't recorded.
    """
    if names is None:
        return dict(recorded)
    for name in names:
        if name not in recorded:
            close = difflib.get_close_matches(name, recorded, n=3, cutoff=0.5)
            hint = f"did you mean: {', '.join(close)}?" if close else f"recorded: {', '.join(recorded)}"
            raise TopicError(f"{name!r} isn't in this recording; {hint}")
    return {name: recorded[name] for name in names}
