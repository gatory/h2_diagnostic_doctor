"""ReplaySource: plays a recording back as if it were the robot. No DDS.

poll() returns every message whose time has come, keeping the recording's
original gaps (scaled by `speed`) and its original timestamps, so rates
measured on a replay match the live run. The file is read line by line,
so long recordings don't have to fit in memory.
"""

import time

from h2_bridge.telemetry.recording import read_header, read_message
from h2_bridge.telemetry.sources.base import Source, select_topics


class ReplaySource(Source):
    """Recording `path` at `speed` x real time.

    `topics` is a list of names to keep (None: everything recorded). Names, not
    TopicSpecs: what a recording holds is only known once it's opened.
    """

    live = False

    def __init__(self, path, topics=None, speed=1.0):
        self.path = path
        self._file = open(path)
        try:
            self.header, recorded = read_header(self._file)
            super().__init__(select_topics(recorded, topics))  # TopicError if not recorded
        except Exception:
            self._file.close()  # bad file or topic: don't leak the handle
            raise
        self.speed = speed
        self.done = False  # True once every message has been handed out
        self._next = self._read_next()  # first message, kept until its time comes
        self._first_t = None if self._next is None else self._next.t
        self._started = None

    def start(self):
        self._started = time.monotonic()
        return self

    def poll(self):
        if self._started is None:
            self.start()
        elapsed = (time.monotonic() - self._started) * self.speed
        due = []
        while self._next is not None and self._next.t - self._first_t <= elapsed:
            due.append(self._next)
            self._next = self._read_next()
        if self._next is None:
            self.done = True
        return due

    def _read_next(self):
        """Next message on one of our topics, or None at the end of the file."""
        for line in self._file:
            message = read_message(line)
            if message.topic in self.topics:
                return message
        return None

    def close(self):
        self._file.close()
