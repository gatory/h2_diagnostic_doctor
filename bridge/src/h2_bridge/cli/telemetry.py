"""`h2-doctor telemetry ...` commands: read the robot's live data.

    h2-doctor telemetry watch                   # live overview: one row per core topic, until Ctrl-C
    h2-doctor telemetry watch rt/lf/bmsstate    # live values of one topic
    h2-doctor telemetry watch -t 30             # stop after 30 s
    h2-doctor telemetry record           # not implemented yet
    h2-doctor telemetry replay FILE      # not implemented yet

`watch` reads the topics in h2_bridge.telemetry.layout (CORE_TOPICS). This
module only parses arguments and drives the display; the logic is in
h2_bridge.telemetry and the tables in telemetry_tables.py.
"""

import argparse

from h2_bridge.cli import telemetry_tables

_WATCH_EXAMPLES = """\
examples:
  h2-doctor telemetry watch                   overview of the core topics until Ctrl-C
  h2-doctor telemetry watch rt/lf/lowstate    every value of one topic (one row per joint)
  h2-doctor telemetry watch -t 30             stop after 30 s
  h2-doctor --iface eth0 telemetry watch      another interface (global option, before the group)

topics: rt/lf/lowstate, rt/lf/secondary_imu, rt/lf/bmsstate, rt/lf/mainboardstate,
        rt/dex5/left/state, rt/dex5/right/state

overview columns:
  Hz        measured rate / expected rate (green: on rate, yellow: slow, red: silent)
  Last      seconds since the topic's newest message
  Summary   a few key fields of the newest message; "?" marks an unconfirmed unit
"""


def register(commands):
    """Add the `telemetry` group to the root parser's subcommands."""
    telemetry = commands.add_parser(
        "telemetry",
        help="Read live robot data",
        description="Read the robot's live data: joints, IMUs, battery, main board, hands.",
    )
    telemetry_cmds = telemetry.add_subparsers(dest="telemetry_command", metavar="<command>", required=True)

    # h2-doctor telemetry watch [TOPIC] [-t SECS]
    watch = telemetry_cmds.add_parser(
        "watch",
        help="Live table of the core topics, or of every value of one topic",
        description="Subscribe to the core robot topics and redraw a live table as data arrives: "
                    "one row per topic, or with TOPIC, every value that topic sends. "
                    "Needs the robot's network (see the global --iface / --domain). Read-only.",
        epilog=_WATCH_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    watch.add_argument(
        "topic", nargs="?", default=None,
        help="show every value of this one topic (default: the overview of all core topics)",
    )
    watch.add_argument(
        "-t", "--duration", type=float, default=None, metavar="SECS",
        help="Stop after SECS seconds (default: run until Ctrl-C)",
    )
    watch.set_defaults(func=_cmd_watch)

    # h2-doctor telemetry record  (saves to outputs/telemetry/<date>/ via h2_bridge.utils.outputs)
    record = telemetry_cmds.add_parser("record", help="Save telemetry to outputs/telemetry/<date>/ (not implemented yet)")
    record.set_defaults(func=_not_implemented)

    # h2-doctor telemetry replay FILE
    replay = telemetry_cmds.add_parser("replay", help="Play back a recording (not implemented yet)")
    replay.add_argument("file", help="Recording made by `telemetry record`")
    replay.set_defaults(func=_not_implemented)


def _cmd_watch(args):
    """Handler for `h2-doctor telemetry watch [TOPIC]`: redraw a table ~4 times a second.

    Without TOPIC: the overview, one row per core topic. With TOPIC: subscribe
    to that topic only and show all its values. Either way every message goes
    through the RateMeter (so rates are true); only the newest per topic is
    kept for display.
    """
    import time

    from rich.console import Console
    from rich.live import Live

    from h2_bridge.telemetry.rates import RateMeter
    from h2_bridge.telemetry.sources.base import latest
    from h2_bridge.telemetry.sources.live import LiveSource
    from h2_bridge.telemetry.layout import CORE_TOPICS

    out = Console()
    err = Console(stderr=True)

    if args.topic is None:
        topics = CORE_TOPICS
    elif args.topic in CORE_TOPICS:
        topics = {args.topic: CORE_TOPICS[args.topic]}  # only this one: less load, truer rate
    else:
        import difflib

        close = difflib.get_close_matches(args.topic, CORE_TOPICS, n=3, cutoff=0.5)
        hint = f"Did you mean: {', '.join(close)}?" if close else f"Choose from: {', '.join(CORE_TOPICS)}"
        err.print(f"[bold red]Can't watch {args.topic!r}:[/] not a core topic. {hint}")
        return 1

    meter = RateMeter()
    newest = {}  # topic -> newest Message so far
    end = None if args.duration is None else time.monotonic() + args.duration

    what = f"{len(topics)} topics" if args.topic is None else f"[bold]{args.topic}[/]"
    err.print(f"Watching {what} on [bold]{args.interface}[/] (domain {args.domain_id}). Ctrl-C to stop.")

    with LiveSource(args.interface, args.domain_id, topics) as source:

        def draw():
            now = time.time()
            if args.topic is None:
                return telemetry_tables.watch_table(topics, newest, meter, source.dropped, now)
            return telemetry_tables.topic_view(
                args.topic, topics[args.topic], newest.get(args.topic), meter, source.dropped[args.topic], now
            )

        with Live(draw(), console=out, refresh_per_second=4) as live:
            while end is None or time.monotonic() < end:
                time.sleep(0.25)
                messages = source.poll()
                meter.add(messages)  # every message
                newest.update(latest(messages))  # only the newest, for display
                live.update(draw())

    if not newest:
        err.print("[bold red]No data received.[/] Check the interface and domain ID.")
        return 1
    return 0


def _not_implemented(args):
    """Placeholder handler for telemetry commands that aren't built yet."""
    from rich.console import Console

    Console(stderr=True).print(f"[yellow]`telemetry {args.telemetry_command}` is not implemented yet.[/]")
    return 1
