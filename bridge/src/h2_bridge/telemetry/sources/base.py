"""Source: the interface every message source follows (LiveSource, ReplaySource).

    with LiveSource("eth10", 0, CORE_TOPICS) as source:
        messages = source.poll()   # every Message since the last poll
"""

from abc import ABC, abstractmethod


class TopicError(ValueError):
    """Asked for a topic the source can't provide."""


class Source(ABC):
    """Base class for message sources.

    Attributes
    ----------
    live : bool
        True for the robot, False for a recording.
    topics : dict[str, TopicSpec]
        The topics this source subscribes to.
    """

    live: bool

    def __init__(self, topics):
        """Stores what topics any source is subscribed to"""
        self.topics = dict(topics)

    def start(self):
        """Begin receiving. Returns self, so `LiveSource(...).start()` works."""
        return self

    @abstractmethod
    def poll(self):
        """Return every Message received since the last call, oldest first (may be empty)."""

    def close(self):
        """Stop receiving and release resources. Safe to call twice."""

    # `with source:` starts it and always closes it, even on Ctrl-C.
    def __enter__(self):
        return self.start()

    def __exit__(self, *exc_info):
        self.close()
