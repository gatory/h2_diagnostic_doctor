"""Consumers of the message stream: what the loop hands each poll's messages to.

    meter = RateMeter()
    messages = source.poll()
    meter.add(messages)                          # every message, so rates are true
    newest.update(latest(messages))              # only the newest per topic, for display
    meter.hz("rt/lf/lowstate", source.now())     # ~20.0, over the last window_s
    meter.average_hz("rt/lf/lowstate")           # ~20.0, over the whole run

Both use each Message's own time `t` and the source's clock (source.now()),
never the wall clock, so they work the same on a live source and a replay.
"""

from collections import defaultdict, deque


def latest(messages):
    """{topic: newest Message} from a batch (oldest first, as poll() returns it)."""
    return {m.topic: m for m in messages}  # later messages overwrite earlier ones


class RateMeter:
    """Messages per second per topic: recent (hz) and over the whole run (average_hz).

    Attributes
    ----------
    window_s : float
        How far back rates look.
    total : dict[str, int]
        Messages seen per topic since the start.
    """

    def __init__(self, window_s=2.0):
        self.window_s = window_s
        self.total = defaultdict(int)
        self._times = defaultdict(deque)  # topic -> arrival times inside the window
        self._first = {}  # topic -> time of its first message
        self._last = {}  # topic -> time of its newest message

    def add(self, messages):
        """Count a batch of messages (oldest first)."""
        for m in messages:
            times = self._times[m.topic]
            times.append(m.t)
            self.total[m.topic] += 1
            self._first.setdefault(m.topic, m.t)
            self._last[m.topic] = m.t
            self._forget(times, m.t)  # keep memory bounded even if hz() is never called

    def hz(self, topic, now):
        """Rate over the window ending at `now` (the source's clock). 0.0 if silent.

        Measured from the gaps between the window's messages, (n - 1) / span: exact,
        where counting messages in the window could only step in 1/window_s Hz.
        """
        times = self._times[topic]
        self._forget(times, now)
        span = times[-1] - times[0] if len(times) >= 2 else 0.0
        return (len(times) - 1) / span if span > 0 else 0.0

    def average_hz(self, topic):
        """Rate over every message seen, (n - 1) / (last - first); None below 2 messages.

        Measured per topic from its own first and last message, so a topic that
        started late isn't averaged over time it wasn't there.
        """
        n = self.total.get(topic, 0)
        span = self._last[topic] - self._first[topic] if n >= 2 else 0.0
        return (n - 1) / span if span > 0 else None

    def average_rates(self, topics):
        """{topic: average_hz rounded to 2 decimals, or None} for each of `topics`."""
        return {
            topic: None if (hz := self.average_hz(topic)) is None else round(hz, 2)
            for topic in topics
        }

    def _forget(self, times, now):
        """Drop arrival times that fell out of the window ending at `now`."""
        while times and times[0] < now - self.window_s:
            times.popleft()
