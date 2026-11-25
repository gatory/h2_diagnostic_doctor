"""`h2-doctor telemetry ...` commands: watch the robot's live data, record it, replay it.

    h2-doctor telemetry watch                                  # core topics, until Ctrl-C
    h2-doctor telemetry watch rt/lf/bmsstate rt/odommodestate  # any topics by name
    h2-doctor telemetry watch rt/lf/bmsstate --record          # also save what's watched
    h2-doctor telemetry replay FILE                            # play a recording back
    h2-doctor telemetry replay FILE rt/lf/bmsstate --speed 4   # some of it, 4x faster

Both commands run the same loop (_play): poll the source ~4 times a second and
hand every batch to each consumer (the recorder, the live table). This module
only parses arguments and drives that loop; the logic is in h2_bridge.telemetry
and the tables in telemetry_tables.py.
"""

import argparse

_WATCH_EXAMPLES = """\
examples:
  h2-doctor telemetry watch                                   overview of the core topics until Ctrl-C
  h2-doctor telemetry watch rt/lf/lowstate                    every value of one topic (one row per joint)
  h2-doctor telemetry watch rt/lf/bmsstate rt/odommodestate   any topics; non-core ones are looked up (cache, then discovery)
  h2-doctor telemetry watch -t 30                             stop after 30 s
  h2-doctor telemetry watch rt/lf/bmsstate --record           also save it to outputs/telemetry/<date>/
  h2-doctor telemetry watch --record before_walk -t 60        save the core topics as before_walk_<time>_<iface>.jsonl.gz
  h2-doctor telemetry watch -q --record                       record without the live table
  h2-doctor --iface eth0 telemetry watch                      another interface (global option, before the group)

Put TOPICs before --record: `--record rt/lf/x` would read the topic as NAME.

core topics: rt/lf/lowstate, rt/lf/secondary_imu, rt/lf/bmsstate, rt/lf/mainboardstate,
             rt/dex5/left/state, rt/dex5/right/state

overview columns:
  Hz        measured rate / expected rate (green: on rate, yellow: slow, red: silent or stale)
  Last      seconds since the topic's newest message (red: stale)
  Summary   a few key fields of the newest message; "?" marks an unconfirmed unit
"""

_REPLAY_EXAMPLES = """\
examples:
  h2-doctor telemetry replay FILE                     every recorded topic, at the recorded pace
  h2-doctor telemetry replay FILE rt/lf/lowstate      every value of one recorded topic
  h2-doctor telemetry replay FILE --speed 4           4x faster (rates and ages stay in recording time)

FILE is a recording made by `telemetry watch --record` (.jsonl.gz, or an older .jsonl).
Needs no robot or network.
"""

# How often the loop polls the source (and redraws the table).
POLL_SECS = 0.25


def register(commands):
    """Add the `telemetry` group to the root parser's subcommands."""
    telemetry = commands.add_parser(
        "telemetry",
        help="Watch, record and replay robot data",
        description="Watch the robot's live data (joints, IMUs, battery, main board, hands), "
                    "record it, and replay recordings.",
    )
    telemetry_cmds = telemetry.add_subparsers(dest="telemetry_command", metavar="<command>", required=True)

    # h2-doctor telemetry watch [TOPIC ...] [-t SECS] [--record [NAME]] [--quiet]
    watch = telemetry_cmds.add_parser(
        "watch",
        help="Live table of the core topics, or of any topics by name",
        description="Subscribe to robot topics and redraw a live table as data arrives: the core "
                    "topics by default, or the TOPICs given (any topic on the network). "
                    "One TOPIC shows every value it sends. "
                    "Needs the robot's network (see the global --iface / --domain). Read-only.",
        epilog=_WATCH_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    watch.add_argument(
        "topics", nargs="*", metavar="TOPIC",
        help="topics to watch (default: the core topics); others are looked up in the cache, then by discovery",
    )
    watch.add_argument(
        "-t", "--duration", type=float, default=None, metavar="SECS",
        help="stop after SECS seconds (default: run until Ctrl-C)",
    )
    # --record alone      -> name "recording"
    # --record my_label   -> name "my_label"   (the folder can't be changed)
    # not given           -> None, nothing saved
    watch.add_argument(
        "-r", "--record", nargs="?", const="recording", default=None, type=_record_name, metavar="NAME",
        help="also save what's watched (only those topics) to outputs/telemetry/<date>/, "
             "optionally named NAME (default name: recording)",
    )
    watch.add_argument(
        "-q", "--quiet", action="store_true",
        help="no live table, just a start line and a summary (e.g. for long recordings)",
    )
    watch.set_defaults(func=_cmd_watch)

    # h2-doctor telemetry replay FILE [TOPIC ...] [--speed X]
    replay = telemetry_cmds.add_parser(
        "replay",
        help="Play back a recording in the same live table",
        description="Play a recording back at its original pace (times --speed) in the same table "
                    "as watch: every recorded topic by default, or only the TOPICs given.",
        epilog=_REPLAY_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    replay.add_argument("file", metavar="FILE", help="recording made by `telemetry watch --record`")
    replay.add_argument(
        "topics", nargs="*", metavar="TOPIC",
        help="recorded topics to show (default: all of them)",
    )
    replay.add_argument(
        "-s", "--speed", type=_speed, default=1.0, metavar="X",
        help="playback speed, e.g. 4 = 4x faster, 0.5 = half speed (default: %(default)s)",
    )
    replay.set_defaults(func=_cmd_replay)


def _cmd_watch(args):
    """Handler for `h2-doctor telemetry watch [TOPIC ...] [-t SECS] [--record [NAME]] [--quiet]`.

    1. Topics: the core topics, or resolve_topics(TOPICs) (core, then the cache, then discovery).
    2. Source: LiveSource(iface, domain, topics).
    3. With --record: a RecordingWriter for the same topics.
    4. _play: the live table (unless --quiet) and the recorder get every batch.

    Returns 1 if a topic can't be found, DDS can't start, or no data arrived.
    """
    import contextlib

    from rich.console import Console

    from h2_bridge.dds import DDSError
    from h2_bridge.telemetry.layout import CORE_TOPICS
    from h2_bridge.telemetry.recording import RecordingWriter
    from h2_bridge.telemetry.resolve import resolve_topics
    from h2_bridge.telemetry.sources.base import TopicError
    from h2_bridge.telemetry.sources.live import LiveSource

    err = Console(stderr=True)
    try:
        topics = resolve_topics(args.topics, args.interface, args.domain_id) if args.topics else CORE_TOPICS
        with (
            LiveSource(args.interface, args.domain_id, topics) as source,
            RecordingWriter(source, args.record) if args.record else contextlib.nullcontext() as recorder,
        ):
            saving = f" to [bold]{recorder.path}[/]" if recorder else ""
            err.print(f"Watching {len(topics)} topic(s) on [bold]{args.interface}[/] "
                      f"(domain {args.domain_id}){saving}. Ctrl-C to stop.")
            counts = _play(source, recorder, args.duration, show_table=not args.quiet)
    except (TopicError, DDSError) as e:
        err.print(f"[bold red]Can't watch:[/] {e}")
        return 1

    _print_summary(err, counts, source.dropped, recorder)
    if not any(counts.values()):
        err.print("[bold red]No data received.[/] Check the interface and domain ID.")
        return 1
    return 0


def _cmd_replay(args):
    """Handler for `h2-doctor telemetry replay FILE [TOPIC ...] [--speed X]`.

    1. Source: ReplaySource(FILE, TOPICs or all recorded, speed).
    2. _play with the same table as watch; ages and rates use source.now(),
       so they're in recording time.

    Ends when the recording does, then says how it ended (footer, or cut off).
    Returns 1 if the file or a topic can't be read.
    """
    from rich.console import Console

    from h2_bridge.telemetry.sources.base import TopicError
    from h2_bridge.telemetry.sources.replay import ReplaySource

    err = Console(stderr=True)
    try:
        source = ReplaySource(args.file, args.topics or None, speed=args.speed)
    except (OSError, ValueError, TopicError) as e:  # missing file, not a recording, topic not recorded
        err.print(f"[bold red]Can't replay:[/] {e}")
        return 1

    header = source.header
    err.print(f"Replaying {len(source.topics)} topic(s) recorded {header.get('started', '?')} on "
              f"[bold]{header.get('host', '?')}[/] ({header.get('interface', '?')}) at {args.speed:g}x. "
              "Ctrl-C to stop.")
    with source:
        counts = _play(source, None, None, show_table=True)

    _print_summary(err, counts, None, None)
    if source.footer:
        dropped = sum(source.footer.get("dropped", {}).values())
        err.print(f"Recording ended cleanly: {source.footer.get('messages', '?')} messages over "
                  f"{source.footer.get('duration_s', '?')} s, {dropped} dropped while recording.")
    elif not str(args.file).endswith(".gz"):
        err.print("[dim]Plain .jsonl recording (made before footers): no record of drops.[/]")
    elif source.done:
        err.print("[yellow]No footer:[/] the recorder didn't close cleanly"
                  + (" (the file is cut off)." if source.truncated else "."))
    return 0


def _play(source, recorder, duration, show_table):
    """Run the loop on `source` with its consumers; return {topic: messages seen}.

    Every batch goes to the recorder (if any) and, with `show_table`, to the
    live table: rates from every message, values from the newest per topic.
    One TOPIC gets the every-value view; several get the overview.
    """
    from rich.console import Console
    from rich.live import Live

    from h2_bridge.cli import telemetry_tables
    from h2_bridge.telemetry.stream import RateMeter, latest

    counts = dict.fromkeys(source.topics, 0)
    meter = RateMeter()
    newest = {}  # topic -> newest Message so far
    detail = next(iter(source.topics)) if len(source.topics) == 1 else None
    dropped = getattr(source, "dropped", None)  # only a live source can drop

    def draw(now):
        if detail:
            lost = None if dropped is None else dropped[detail]
            return telemetry_tables.topic_view(detail, source.topics[detail], newest.get(detail), meter, lost, now)
        return telemetry_tables.watch_table(source.topics, newest, meter, dropped, now)

    def on_poll(messages, now):
        if recorder:
            recorder.write(messages)
        for m in messages:
            counts[m.topic] += 1
        if show_table:
            meter.add(messages)  # every message
            newest.update(latest(messages))  # only the newest, for display
            live.update(draw(now), refresh=True)

    if not show_table:
        _run(source, duration, on_poll)
        return counts
    with Live(draw(source.now()), console=Console(), auto_refresh=False) as live:
        _run(source, duration, on_poll)
    return counts


def _run(source, duration, on_poll):
    """Poll `source` until `duration` (None: forever), Ctrl-C, or the source is done.

    Calls on_poll(messages, now) after each poll, with `now` read right then on
    the source's clock. Ctrl-C only sets a flag, so it can never land halfway
    through writing a line; a second Ctrl-C stops at once.
    """
    import signal
    import time

    stop = False

    def on_ctrl_c(signum, frame):
        nonlocal stop
        if stop:  # second Ctrl-C: give up waiting
            raise KeyboardInterrupt
        stop = True

    end = None if duration is None else time.monotonic() + duration
    previous = signal.signal(signal.SIGINT, on_ctrl_c)
    try:
        while not stop and not source.done and (end is None or time.monotonic() < end):
            time.sleep(POLL_SECS)
            messages = source.poll()
            on_poll(messages, source.now())
    finally:
        signal.signal(signal.SIGINT, previous)


def _print_summary(err, counts, dropped, recorder):
    """One line per topic: messages seen (and dropped, live only); then where the recording went."""
    for topic, n in counts.items():
        lost = f"  [red]{dropped[topic]} dropped[/]" if dropped and dropped[topic] else ""
        err.print(f"  {topic:<28} {n:>8} messages{lost}")
    if recorder:
        err.print(f"Saved {recorder.count} messages to [bold]{recorder.path}[/]")


def _record_name(value):
    """argparse type for --record: check the name before anything starts."""
    from h2_bridge.utils.outputs import check_name

    try:
        return check_name(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from None


def _speed(value):
    """argparse type for --speed: a number above 0."""
    speed = float(value)
    if speed <= 0:
        raise argparse.ArgumentTypeError(f"must be > 0, got {value}")
    return speed
