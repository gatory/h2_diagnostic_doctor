"""ReplaySource: plays a recording back as if it were the robot. No DDS.

poll() returns every message whose time has come, keeping the recording's
original gaps (scaled by `speed`) and its original timestamps. now() runs on
the recording's clock, so ages and rates measured on a replay match the live
run. Reading the file (one line at a time, .jsonl.gz only, cut off or not)
is RecordingReader's job; this class only decides when each message is due.
"""

import time

from h2_bridge.telemetry.recording_format import RecordingReader
from h2_bridge.telemetry.sources.base_source import Source


class ReplaySource(Source):
    """Recording `path` at `speed` x real time: every topic it holds.

    Attributes
    ----------
    done : bool
        True once every message has been handed out.
    truncated : bool
        True if the file was cut off (recording killed mid-write); the cut-off part is skipped.
    footer : dict | None
        The recording's footer (end, duration_s, messages, dropped, avg_hz) once it's reached;
        stays None if the recorder died before writing it.
    """

    live = False

    def __init__(self, path, speed=1.0):
        if speed <= 0:
            raise ValueError(f"speed must be > 0, got {speed}")
        self.path = path
        self.speed = speed
        self.done = False
        self._started = None
        self._reader = RecordingReader(path)  # OSError / ValueError: missing file, not a recording
        super().__init__(self._reader.topics)
        try:
            self._next = self._reader.next_message()  # first message, kept until its time comes
        except Exception:
            self._reader.close()  # corrupt file: don't leak the handle
            raise
        self._first_t = None if self._next is None else self._next.t
        self._last_t = self._first_t  # newest message handed out so far

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
            self._last_t = self._next.t
            self._next = self._reader.next_message()
        if self._next is None:
            self.done = True
        return due

    def now(self):
        """Where playback is, in recording time (same units as Message.t).

        Stops at the last message once the recording is done, so the final
        state shows as the recording ended, not as gone stale.
        """
        if self._first_t is None:  # empty recording
            return 0.0
        if self._started is None:
            return self._first_t
        if self.done:
            return self._last_t
        return self._first_t + (time.monotonic() - self._started) * self.speed

    @property
    def header(self):
        """The recording's header (started, host, interface, domain_id, topics)."""
        return self._reader.header

    @property
    def footer(self):
        """The recording's footer once reached; None if not yet, or if the recorder died."""
        return self._reader.footer

    @property
    def truncated(self):
        """True if the file was cut off (recording killed mid-write)."""
        return self._reader.truncated

    def close(self):
        """Close the file. Safe to call twice."""
        self._reader.close()

