"""`h2-doctor server ...` commands: stream snapshots to the dashboard over WebSocket.

    h2-doctor server live                  # the robot's core topics, until Ctrl-C
    h2-doctor server replay                # the newest recording
    h2-doctor server replay FILE -s 4      # a given one, 4x faster

Both run the one poll loop with the snapshot builder, checkup and the
SnapshotPublisher, at --rate polls (and messages) a second. This module only
parses arguments and picks the source; the server is h2_bridge.server.
"""

import argparse

from h2_bridge.constants import SERVER_DEFAULTS

_EXAMPLES = """\
examples:
  h2-doctor server live                         the robot, on ws://0.0.0.0:8765
  h2-doctor server replay                       the newest recording, at the recorded pace
  h2-doctor server replay FILE --speed 4        a given recording, 4x faster
  h2-doctor server --port 9000 --rate 10 live   another port, 10 messages a second

Each message is one complete snapshot plus checkup's verdicts (see
h2_bridge/server/messages.py). Read-only: nothing sent to the robot, and
anything a browser sends is ignored.
"""


def register(commands):
    """Add the `server` group to the root parser's subcommands."""
    server = commands.add_parser(
        "server",
        help="Stream snapshots to the dashboard (WebSocket)",
        description="Serve the robot's data, or a recording, to the dashboard over WebSocket.",
        epilog=_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    server.add_argument(
        "--host", default=SERVER_DEFAULTS["host"],
        help="address to listen on (default: %(default)s, every interface)",
    )
    server.add_argument(
        "--port", type=int, default=SERVER_DEFAULTS["port"],
        help="port to listen on (default: %(default)s)",
    )
    server.add_argument(
        "--rate", type=_positive, default=SERVER_DEFAULTS["rate_hz"], metavar="HZ",
        help="snapshots sent per second (default: %(default)g)",
    )
    server_cmds = server.add_subparsers(dest="server_command", metavar="<command>", required=True)

    # h2-doctor server live
    live = server_cmds.add_parser(
        "live",
        help="Serve the robot's core topics",
        description="Subscribe to the core topics and serve them until Ctrl-C. Needs the robot's "
                    "network (see the global --iface / --domain). Read-only.",
    )
    live.set_defaults(func=_cmd_live)

    # h2-doctor server replay [FILE] [--speed X]
    replay = server_cmds.add_parser(
        "replay",
        help="Serve a recording as if it were the robot",
        description="Play a recording at its original pace (times --speed) and serve it: the "
                    "newest one, or FILE. Needs no robot or network. Stops at the end.",
    )
    replay.add_argument(
        "file", nargs="?", default=None, metavar="FILE",
        help=".jsonl.gz recording made by `telemetry watch --record` (default: the newest in outputs/telemetry/)",
    )
    replay.add_argument(
        "-s", "--speed", type=_positive, default=1.0, metavar="X",
        help="playback speed, e.g. 4 = 4x faster (default: %(default)s)",
    )
    replay.set_defaults(func=_cmd_replay)


def _cmd_live(args):
    """Handler for `h2-doctor server live`. Returns 1 if DDS or the server can't start."""
    from rich.console import Console

    from h2_bridge.dds_setup import DDSError
    from h2_bridge.telemetry.core_topics import CORE_TOPICS
    from h2_bridge.telemetry.sources.base_source import TopicError
    from h2_bridge.telemetry.sources.live_source import LiveSource

    err = Console(stderr=True)
    try:
        with LiveSource(args.interface, args.domain_id, CORE_TOPICS) as source:
            what = f"the {len(CORE_TOPICS)} core topics on [bold]{args.interface}[/] (domain {args.domain_id})"
            return _serve(err, source, what, args)
    except (TopicError, DDSError) as e:
        err.print(f"[bold red]Can't watch:[/] {e}")
        return 1


def _cmd_replay(args):
    """Handler for `h2-doctor server replay [FILE] [--speed X]`. Returns 1 if there's no
    recording, it can't be read, or the server can't start."""
    from rich.console import Console

    from h2_bridge.telemetry.recording_format import EXTENSION
    from h2_bridge.telemetry.sources.replay_source import ReplaySource
    from h2_bridge.utils.output_paths import find_outputs

    err = Console(stderr=True)
    path = args.file
    if path is None:
        recordings = find_outputs("telemetry", ext=EXTENSION)  # newest first
        if not recordings:
            err.print("[bold red]No recordings[/] in outputs/telemetry/. Make one with `telemetry watch --record`.")
            return 1
        path = recordings[0].path
    try:
        source = ReplaySource(path, speed=args.speed)
    except (OSError, ValueError) as e:
        err.print(f"[bold red]Can't replay:[/] {e}")
        return 1
    with source:
        return _serve(err, source, f"[bold]{path}[/] at {args.speed:g}x", args)


def _serve(err, source, what, args):
    """Start the server, run the poll loop with builder, checkup and publisher, then print a summary."""
    from h2_bridge.checkup.engine import Checkup
    from h2_bridge.server.publisher import SnapshotPublisher
    from h2_bridge.server.ws_server import WebSocketServer
    from h2_bridge.telemetry.poll_loop import run
    from h2_bridge.telemetry.snapshot import SnapshotBuilder

    builder = SnapshotBuilder(source.topics, source.dropped)
    checkup = Checkup(builder)
    try:
        server = WebSocketServer(args.host, args.port).start()
    except OSError as e:  # port in use, bad address
        err.print(f"[bold red]Can't serve on {args.host}:{args.port}:[/] {e.strerror or e}")
        return 1
    with server:
        publisher = SnapshotPublisher(builder, checkup, server, source.live)
        err.print(f"Serving {what} on [bold]ws://{args.host}:{server.port}[/], "
                  f"{args.rate:g} snapshots/s. Ctrl-C to stop.")
        run(source, [builder, checkup, publisher], poll_secs=1.0 / args.rate)
    ended = "Recording finished" if source.done else "Stopped"
    err.print(f"{ended}: sent {publisher.sent} snapshots.")
    return 0


def _positive(value):
    """argparse type: a number above 0."""
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError(f"must be > 0, got {value}")
    return number
