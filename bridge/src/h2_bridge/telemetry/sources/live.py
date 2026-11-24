"""LiveSource: messages from the robot over DDS. READ-ONLY: it only subscribes.

How a message gets from the robot to poll():

    DDS thread    the SDK decodes it and calls our handler, which only stamps the
                  arrival time and drops it in the mailbox (_pending). Nothing slow
                  here: while the handler runs, newer messages can be overwritten.
    main thread   poll() empties the mailbox and converts each message to a dict.

A lock guards the mailbox because both threads touch it. The mailbox has a size
limit: if the main thread falls far behind, the oldest messages are thrown away
and counted in `dropped`, instead of using up memory.

Cost: every message is decoded and converted, so subscribe only to what you need
(~300 messages/s is fine; adding the ~1 kHz topics like rt/lowstate is not).
"""

import threading
import time
from collections import deque

from h2_bridge.telemetry.convert import to_dict
from h2_bridge.telemetry.models import Message
from h2_bridge.telemetry.sources.base import Source


class LiveSource(Source):
    """Subscribe to `topics` ({name: TopicSpec}) on the robot's DDS network."""

    live = True

    def __init__(self, interface, domain_id, topics, max_pending=10_000):
        self.interface = interface
        self.domain_id = domain_id
        self.topics = dict(topics)
        self.dropped = {name: 0 for name in self.topics}
        self._max_pending = max_pending  # ~30 s of watch's topics
        self._pending = deque()  # the mailbox: (arrival time, topic, SDK message)
        self._lock = threading.Lock()
        self._subscribers = []

    def start(self):
        from unitree_sdk2py.core.channel import ChannelSubscriber

        from h2_bridge.dds import init_dds

        init_dds(self.interface, self.domain_id)
        for name, spec in self.topics.items():
            sub = ChannelSubscriber(name, spec.msg_type)
            sub.Init(self._make_handler(name))  # no queueLen: the handler runs on DDS's thread
            self._subscribers.append(sub)
        return self

    def _make_handler(self, topic):
        """Build the callback for one topic (the SDK passes only the message, not its topic)."""

        def handle(msg):  # runs on a DDS thread: keep it tiny
            arrived = time.time()
            with self._lock:
                if len(self._pending) >= self._max_pending:
                    _, lost_topic, _ = self._pending.popleft()
                    self.dropped[lost_topic] += 1
                self._pending.append((arrived, topic, msg))

        return handle

    def poll(self):
        with self._lock:  # swap the mailbox for an empty one; hold the lock as briefly as possible
            pending, self._pending = self._pending, deque()
        return [Message(t, topic, to_dict(msg)) for t, topic, msg in pending]

    def close(self):
        subscribers, self._subscribers = self._subscribers, []
        for sub in subscribers:
            sub.Close()
