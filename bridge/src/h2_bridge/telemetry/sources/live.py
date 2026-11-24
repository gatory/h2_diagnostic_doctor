"""LiveSource: messages from the robot over DDS. Read-only: it only subscribes.

    DDS thread    our handler stamps the arrival time and drops the message in the inbox
    main thread   poll() empties the inbox and converts each message to a dict

The handler must stay tiny, or DDS overwrites messages before we take them.
The inbox is capped; overflow drops the oldest and counts it in `dropped`.
"""

import dataclasses
import math
import threading
import time
from collections import deque

from h2_bridge.telemetry.models import Message
from h2_bridge.telemetry.sources.base import Source


class LiveSource(Source):
    """`topics` ({name: TopicSpec}, e.g. CORE_TOPICS) on `interface` / `domain_id`."""

    live = True

    def __init__(self, interface, domain_id, topics, max_pending=10_000):
        super().__init__(topics)
        self.interface = interface
        self.domain_id = domain_id
        self._max_pending = max_pending  # ~30 s of all core topics
        self._inbox = deque()  # (arrival time, topic, SDK message)
        self._lock = threading.Lock()  # the DDS thread and poll() both touch the inbox
        self._subscribers = []

    def start(self):
        from unitree_sdk2py.core.channel import ChannelSubscriber

        from h2_bridge.dds import init_dds

        init_dds(self.interface, self.domain_id)
        for name, spec in self.topics.items():
            sub = ChannelSubscriber(name, spec.msg_type)
            sub.Init(self._make_handler(name))  # no queueLen: runs on DDS's own thread
            self._subscribers.append(sub)
        return self

    def _make_handler(self, topic):
        """Callback for one topic (the SDK passes only the message, not its topic)."""

        def handle(msg):  # DDS thread: keep it tiny
            arrived = time.time()
            with self._lock:
                if len(self._inbox) >= self._max_pending:
                    _, lost, _ = self._inbox.popleft()
                    self.dropped[lost] += 1
                self._inbox.append((arrived, topic, msg))

        return handle

    def poll(self):
        with self._lock:  # swap in an empty inbox; hold the lock briefly
            inbox, self._inbox = self._inbox, deque()
        return [Message(t, topic, _to_dict(msg)) for t, topic, msg in inbox]

    def close(self):
        subscribers, self._subscribers = self._subscribers, []
        for sub in subscribers:
            sub.Close()


def _to_dict(obj):
    """SDK message -> plain JSON-safe data (dicts, lists, numbers; NaN/inf -> None)."""
    if dataclasses.is_dataclass(obj):
        return {f.name: _to_dict(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, (list, tuple)):
        return [_to_dict(x) for x in obj]
    if isinstance(obj, (bytes, bytearray)):
        return list(obj)
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj
