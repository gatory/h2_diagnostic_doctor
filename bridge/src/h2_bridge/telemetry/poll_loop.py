"""The one poll loop: poll a source and hand every batch to each consumer.

    run(source, [meter, recorder, dashboard], duration=10)

Every consumer gets the same list of messages, in the order given, plus the
source's clock at that moment. A consumer is any object with

    add(messages, now)    called once per poll, messages oldest first (may be empty)

`watch`, `replay` and `checkup` all run this loop; they differ only in the
source and the consumers. Order matters when one consumer reads another
(e.g. checkup reads the snapshot builder): put the one being read first.

Ctrl-C only sets a flag, checked between polls, so it can never land halfway
through a consumer's work (a recorder writing a line); a second Ctrl-C stops at once.
"""

import signal
import time

# How often the loop polls the source (and consumers redraw).
POLL_SECS = 0.25


def run(source, consumers, duration=None, poll_secs=POLL_SECS):
    """Poll `source` until `duration` seconds pass on its clock (None: forever), Ctrl-C, or it's done.

    `duration` is measured on the source's clock (source.now()), not the wall
    clock: the same thing for a live source, and "the first N seconds of the
    recording" for a replay. `poll_secs` is the wall-clock time from one poll to
    the next (0 for a replay that steps its own clock): the loop sleeps only for
    what's left of it after the consumers' work, so a slow redraw doesn't stretch
    every poll (and with it every warning's delay). If the work takes longer, the
    next poll starts at once. Returns True if stopped by Ctrl-C.
    """
    stop = False

    def on_ctrl_c(signum, frame):
        nonlocal stop
        if stop:  # second Ctrl-C: give up waiting
            raise KeyboardInterrupt
        stop = True

    source.start()  # no-op if already started; makes now() meaningful for the deadline
    end = None if duration is None else source.now() + duration
    previous = signal.signal(signal.SIGINT, on_ctrl_c)
    next_poll = time.monotonic() + poll_secs
    try:
        while not stop and not source.done:
            if poll_secs:
                time.sleep(max(0.0, next_poll - time.monotonic()))
                next_poll = max(next_poll + poll_secs, time.monotonic())  # never bank up missed polls
            messages = source.poll()
            now = source.now()
            for consumer in consumers:
                consumer.add(messages, now)
            if end is not None and now >= end:
                break
    finally:
        signal.signal(signal.SIGINT, previous)
    return stop
