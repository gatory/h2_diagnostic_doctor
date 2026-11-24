"""Source: the interface every message source follows (live robot, recording).

    with LiveSource("eth10", 0, CORE_TOPICS) as source:
        messages = source.poll()   # every Message since the last poll

select_topics() helps callers pick topics by name (with "did you mean").
"""

import difflib
from abc import ABC, abstractmethod


class TopicError(ValueError):
    """Asked for a topic the source can't provide."""


class Source(ABC):
    """Base class for message sources.

    Subclasses call super().__init__(topics), then implement poll()
    (and start()/close() if they hold resources).

    Attributes
    ----------
    live : bool
        True for the robot, False for a recording.
    topics : dict[str, TopicSpec]
        The topics this source subscribes to.
    dropped : dict[str, int]
        Messages lost per topic because the consumer fell behind. Should stay 0.
    """

    live: bool

    def __init__(self, topics):
        """topics: {name: TopicSpec} to deliver."""
        self.topics = dict(topics)
        self.dropped = dict.fromkeys(self.topics, 0)

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


def select_topics(available, names=None):
    """Return {name: TopicSpec} for `names` (None: all of `available`).

        select_topics(CORE_TOPICS, ["rt/lf/bmsstate"])

    Raises TopicError, with close matches, for a name not in `available`.
    """
    if names is None:
        return dict(available)
    for name in names:
        if name not in available:
            close = difflib.get_close_matches(name, available, n=3, cutoff=0.5)
            hint = f"did you mean: {', '.join(close)}?" if close else f"available: {', '.join(available)}"
            raise TopicError(f"no topic {name!r}; {hint}")
    return {name: available[name] for name in names}


# class Source(ABC):
#     """Base class for LiveSource and ReplaySource.
    
#     Attributes
#     ----------
#     live : bool
#         True for the robot, False for a recording.
#     topics : dict[str, TopicSpec]
#         The topics this source subscribes to.
#     dropped : dict[str, int]
#         Messages lost per topic because the consumer fell behind. Should stay 0.
#     """


#     def start(self):
#         """Begin receiving. Returns self, so `LiveSource(...).start()` works."""
#         return self

#     @abstractmethod
#     def poll(self):
#         """Return every Message received since the last call, oldest first (may be empty)."""

#     def close(self):
#         """Stop receiving and release resources. Safe to call twice."""


#     def __enter__(self):
#         return self.start()

#     def __exit__(self, *exc_info):
#         self.close()
