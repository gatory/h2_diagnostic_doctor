"""Consumers of the message stream: what the loop hands each poll's messages to.

    meter = RateMeter()
    messages = source.poll()
    meter.add(messages)                          # every message, so rates are true
    newest.update(latest(messages))              # only the newest per topic, for display
    meter.hz("rt/lf/lowstate", source.now())     # ~20.0

Both use each Message's own time `t` and the source's clock (source.now()),
never the wall clock, so they work the same on a live source and a replay.
"""

from collections import defaultdict, deque


def latest(messages):
    """{topic: newest Message} from a batch (oldest first, as poll() returns it)."""
    return {m.topic: m for m in messages}  # later messages overwrite earlier ones


class RateMeter:
    """Messages per second per topic, over the last `window_s` seconds.

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

    def add(self, messages):
        """Count a batch of messages (oldest first)."""
        for m in messages:
            times = self._times[m.topic]
            times.append(m.t)
            self.total[m.topic] += 1
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

    def _forget(self, times, now):
        """Drop arrival times that fell out of the window ending at `now`."""
        while times and times[0] < now - self.window_s:
            times.popleft()
