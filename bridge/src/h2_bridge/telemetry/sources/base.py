"""Source: what every message source looks like (the live robot, later a recording).

Everything that consumes telemetry (watch, the recorder, the dashboard server)
talks only to a Source, so it can't tell where the messages come from. Swap
LiveSource for a ReplaySource and nothing else changes.

A source hands out EVERY message; each consumer decides how much it keeps:

    with LiveSource("eth10", 0, CORE_TOPICS) as source:
        while True:
            messages = source.poll()      # every message since the last poll
            recorder.write(messages)      # keeps all of them
            newest = latest(messages)     # the screen only needs the newest per topic
"""

from abc import ABC, abstractmethod


class Source(ABC):
    """Base class for message sources. Subclasses implement poll().

    Attributes
    ----------
    live : bool
        True for the robot, False for a recording.
    topics : dict[str, TopicSpec]
        The topics this source delivers.
    dropped : dict[str, int]
        Messages lost per topic because the consumer fell behind. Should stay 0;
        if it isn't, rates and recordings are missing data.
    """

    live: bool
    topics: dict
    dropped: dict

    def start(self):
        """Begin receiving. Returns self, so `source = LiveSource(...).start()` works."""
        return self

    @abstractmethod
    def poll(self):
        """Return every Message received since the last call (oldest first); may be empty."""

    def close(self):
        """Stop receiving and release resources. Safe to call more than once."""

    # `with source:` starts it and always closes it, even on Ctrl-C or an error.
    def __enter__(self):
        return self.start()

    def __exit__(self, *exc_info):
        self.close()


def latest(messages):
    """The newest Message per topic: {topic: Message}. For displays, which can't use every one."""
    newest = {}
    for m in messages:  # oldest first, so later ones overwrite earlier ones
        newest[m.topic] = m
    return newest
