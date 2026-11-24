"""Measure how fast each topic is arriving, from the messages themselves.

Uses each Message's arrival time `t`, not the wall clock, so it works the same
on a live source and (later) a replay.

    meter = RateMeter(window_s=2.0)
    meter.add(source.poll())     # every message, not just the newest
    meter.hz("rt/lf/lowstate")   # ~20.0
"""

from collections import defaultdict, deque


class RateMeter:
    """Messages per second per topic, over the last `window_s` seconds."""

    def __init__(self, window_s=2.0):
        self.window_s = window_s
        self._times = defaultdict(deque)  # topic -> arrival times inside the window
        self.total = defaultdict(int)  # topic -> messages seen since the start
        self._now = None  # newest arrival time seen on any topic

    def add(self, messages):
        """Count a batch of messages (oldest first)."""
        for m in messages:
            self._times[m.topic].append(m.t)
            self.total[m.topic] += 1
            if self._now is None or m.t > self._now:
                self._now = m.t

    def hz(self, topic, now=None):
        """Rate over the window ending at `now` (default: the newest message seen). 0.0 if silent."""
        now = self._now if now is None else now
        times = self._times[topic]
        while times and times[0] < now - self.window_s:  # forget what fell out of the window
            times.popleft()
        return len(times) / self.window_s

    def last_seen(self, topic):
        """Arrival time of the topic's newest message, or None if it never arrived."""
        times = self._times[topic]
        return times[-1] if times else None
