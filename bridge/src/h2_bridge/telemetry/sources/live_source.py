"""LiveSource: messages from the robot over DDS. Read-only: it only subscribes.

    DDS thread    our handler stamps the arrival time and drops the message in the inbox
    main thread   poll() empties the inbox and converts each message to a dict

The handler must stay tiny, or DDS overwrites messages before we take them.
The inbox is capped; overflow drops the oldest and counts it in `dropped`.
"""

import threading
import time
from collections import deque

from h2_bridge.telemetry.models import Message
from h2_bridge.telemetry.sources.base_source import Source, TopicError
from h2_bridge.utils.msg_to_dict import msg_to_dict

# Inbox cap (~30 s of core topics) so a stalled poll() can't use unbounded memory
MAX_PENDING = 10_000


class LiveSource(Source):
    """Subscribes to `topics` on the robot over DDS and hands out every message via poll().

    Parameters
    ----------
    interface : str
        Network interface DDS uses, e.g. "eth10".
    domain_id : int
        DDS domain; must match the robot's.
    topics : dict[str, TopicSpec]
        Topics to subscribe to, e.g. CORE_TOPICS.

    Attributes
    ----------
    dropped : dict[str, int]
        Messages lost per topic because poll() fell behind (inbox over MAX_PENDING). Should stay 0.
    """

    live = True

    def __init__(self, interface, domain_id, topics):
        super().__init__(topics)
        self.interface = interface
        self.domain_id = domain_id
        self.dropped = dict.fromkeys(self.topics, 0)
        self._inbox = deque()  # (arrival time, topic, SDK message)
        self._lock = threading.Lock()  # for the DDS thread and poll() since they both touch the inbox
        self._subscribers = []

    def start(self):
        """Start DDS and subscribe to every topic. Raises DDSError or TopicError; nothing is left subscribed on failure."""
        from unitree_sdk2py.core.channel import ChannelSubscriber

        from h2_bridge.dds_setup import init_dds

        if self._subscribers:
            return self
        
        init_dds(self.interface, self.domain_id)
        try:
            for name, spec in self.topics.items():
                try:
                    sub = ChannelSubscriber(name, spec.msg_type)
                    sub.Init(self._make_handler(name))
                except Exception as e:
                    raise TopicError(f"can't subscribe to {name!r} ({spec.type_name}): {e}") from e
                self._subscribers.append(sub)
        except Exception:
            self.close()
            raise
        return self

    def _make_handler(self, topic):
        """Callback for one topic (the SDK passes only the message, not its topic)."""

        def handle(msg):  # DDS thread: keep it tiny
            arrived = time.time()
            with self._lock:
                if len(self._inbox) >= MAX_PENDING:
                    _, lost, _ = self._inbox.popleft()
                    self.dropped[lost] += 1
                self._inbox.append((arrived, topic, msg))

        return handle

    def poll(self):
        """Empty the inbox and convert each message to a Message, oldest first."""
        with self._lock:  # swap in an empty inbox; hold the lock briefly
            inbox, self._inbox = self._inbox, deque()
        return [Message(t, topic, msg_to_dict(msg)) for t, topic, msg in inbox]

    def now(self):
        """Wall-clock time, the same clock the handler stamps arrivals with."""
        return time.time()

    def close(self):
        """Unsubscribe from every topic. Safe to call twice."""
        subscribers, self._subscribers = self._subscribers, []
        for sub in subscribers:
            sub.Close()
