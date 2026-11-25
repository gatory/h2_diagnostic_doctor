"""Source: the interface every message source follows (LiveSource, ReplaySource).

    with LiveSource("eth10", 0, CORE_TOPICS) as source:
        messages = source.poll()   # every Message since the last poll
"""

from abc import ABC, abstractmethod


class TopicError(ValueError):
    """Asked for a topic the source can't provide."""


class Source(ABC):
    """Base class for message sources.
    
    Note
    ----
    Subclasses must call super().__init__(topics), set `live`, and implement poll()
    and now() (plus start()/close() if they hold resources).

    
    Attributes
    ----------
    live : bool
        True for the robot, False for a recording.
    topics : dict[str, TopicSpec]
        The topics this source delivers.
    """

    @property
    @abstractmethod
    def live(self):
        """True for the robot, False for a recording."""

    def __init__(self, topics):
        """topics: {name: TopicSpec} this source delivers."""
        self.topics = dict(topics)

    def start(self):
        """Begin receiving. Returns self, so `LiveSource(...).start()` works."""
        return self

    @abstractmethod
    def poll(self):
        """Return every Message received since the last call, oldest first (may be empty)."""

    @abstractmethod
    def now(self):
        """Current time on this source's clock, in the same units as Message.t.

        Use it instead of time.time() for ages and rates, so they work on a replay too.
        """

    def close(self):
        """Stop receiving and release resources. Safe to call twice."""

    # `with source:` starts it and always closes it, even on Ctrl-C.
    def __enter__(self):
        return self.start()

    def __exit__(self, *exc_info):
        self.close()
