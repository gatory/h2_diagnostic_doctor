"""SnapshotPublisher: the poll-loop consumer that hands each Snapshot to the WebSocket server.

    builder = SnapshotBuilder(source.topics, source.dropped)
    checkup = Checkup(builder)
    run(source, [builder, checkup, SnapshotPublisher(builder, checkup, server, source.live)],
        poll_secs=1 / rate_hz)

One message per poll, so the send rate is the poll rate: the server command
polls at --rate (30 Hz by default) instead of the loop's usual 4 Hz. It must
come after the builder and checkup in the consumer list (it reads both).
"""

import json

from h2_bridge.server.messages import snapshot_message


class SnapshotPublisher:
    """Poll-loop consumer: after every batch, publish the snapshot message (if anyone is listening).

    Attributes
    ----------
    sent : int
        Messages published so far.
    """

    def __init__(self, builder, checkup, server, live):
        self.builder = builder
        self.checkup = checkup
        self.server = server
        self.live = live
        self.sent = 0

    def add(self, messages, now):
        if not self.server.clients:
            return  # nobody to send to: skip the JSON work (checkup still runs as its own consumer)
        message = snapshot_message(self.builder.snapshot(now), self.checkup, self.live)
        self.server.publish(json.dumps(message, allow_nan=False, separators=(",", ":")))
        self.sent += 1
