"""`h2-doctor telemetry ...` commands: watch the robot's live data, record it, replay it.

    h2-doctor telemetry watch                 # the core topics, until Ctrl-C
    h2-doctor telemetry watch --record        # also save them
    h2-doctor telemetry watch -q --record     # save them without the live dashboard
    h2-doctor telemetry replay                # play the newest recording back
    h2-doctor telemetry replay FILE -s 4      # a given one, 4x faster

Both commands run the one poll loop (telemetry/poll_loop.py) with their
consumers: the rate meter, the recorder (watch --record) and the live
dashboard. This module only parses arguments and picks the consumers; the
logic is in h2_bridge.telemetry and the screen in telemetry_tables.py.
"""

import argparse

_WATCH_EXAMPLES = """\
examples:
  h2-doctor telemetry watch                              the core topics until Ctrl-C
  h2-doctor telemetry watch -t 30                        stop after 30 s
  h2-doctor telemetry watch --record                     also save them to outputs/telemetry/<date>/
  h2-doctor telemetry watch --record before_walk -t 60   save as before_walk_<time>_<iface>.jsonl.gz
  h2-doctor telemetry watch -q --record                  record without the live dashboard
  h2-doctor --iface eth0 telemetry watch                 another interface (global option, before the group)

core topics: rt/lf/lowstate, rt/lf/secondary_imu, rt/lf/bmsstate, rt/lf/mainboardstate,
             rt/dex5/left/state, rt/dex5/right/state

dashboard (needs a terminal of about 155 x 50):
  Topics       per topic: Hz over the last 2 s / expected, in checkup's verdict color (green:
               on rate, yellow: slow, red: silent or stale), Avg since the start, Last
               message age, Dropped
  Warnings     checkup's current findings, worst first (the same rules as `h2-doctor checkup`)
  Body joints  31 joints: q, dq, tau, both temperatures, mode, motorstate
  Hands        20 motors each (thumb: position only), pressure max per pad, error, power
  IMUs         pelvis, torso and both hands: rpy, gyro, accel, temperature
  Battery, Main board
  Numbers only, no warnings; "?" marks a unit or meaning that isn't confirmed.
"""

_REPLAY_EXAMPLES = """\
examples:
  h2-doctor telemetry replay                   the newest recording, at the recorded pace
  h2-doctor telemetry replay --speed 4         4x faster (rates and ages stay in recording time)
  h2-doctor telemetry replay FILE              a given recording

FILE is a .jsonl.gz recording made by `telemetry watch --record`; without it,
the newest one in outputs/telemetry/ is played.
The Warnings panel runs checkup's rules live; at a high --speed they see few
polls and can miss short problems: `h2-doctor checkup --replay` is the full check.
Needs no robot or network.
"""

def register(commands):
    """Add the `telemetry` group to the root parser's subcommands."""
    telemetry = commands.add_parser(
        "telemetry",
        help="Watch, record and replay robot data",
        description="Watch the robot's live data (joints, IMUs, battery, main board, hands), "
                    "record it, and replay recordings.",
    )
    telemetry_cmds = telemetry.add_subparsers(dest="telemetry_command", metavar="<command>", required=True)

    # h2-doctor telemetry watch [-t SECS] [--record [NAME]] [--quiet]
    watch = telemetry_cmds.add_parser(
        "watch",
        help="Live dashboard of the core topics",
        description="Subscribe to the core topics and redraw a live dashboard as data arrives. "
                    "Needs the robot's network (see the global --iface / --domain). Read-only.",
        epilog=_WATCH_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
        help="also save the core topics to outputs/telemetry/<date>/, "
             "optionally named NAME (default name: recording)",
    )
    watch.add_argument(
        "-q", "--quiet", action="store_true",
        help="no live dashboard, just a start line and a summary (e.g. for long recordings)",
    )
    watch.set_defaults(func=_cmd_watch)

    # h2-doctor telemetry replay [FILE] [--speed X]
    replay = telemetry_cmds.add_parser(
        "replay",
        help="Play back a recording in the same live dashboard",
        description="Play a recording back at its original pace (times --speed) in the same "
                    "dashboard as watch: the newest one, or FILE.",
        epilog=_REPLAY_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    replay.add_argument(
        "file", nargs="?", default=None, metavar="FILE",
        help=".jsonl.gz recording made by `telemetry watch --record` (default: the newest in outputs/telemetry/)",
    )
    replay.add_argument(
        "-s", "--speed", type=_speed, default=1.0, metavar="X",
        help="playback speed, e.g. 4 = 4x faster, 0.5 = half speed (default: %(default)s)",
    )
    replay.set_defaults(func=_cmd_replay)


def _cmd_watch(args):
    """Handler for `h2-doctor telemetry watch [-t SECS] [--record [NAME]] [--quiet]`.

    1. Source: LiveSource(iface, domain, CORE_TOPICS).
    2. With --record: a RecordingWriter for the same topics.
    3. _play: the rate meter, the recorder and the live table (unless --quiet) get every batch.

    Returns 1 if DDS can't start, a topic can't be subscribed to, or no data arrived.
    """
    import contextlib

    from rich.console import Console

    from h2_bridge.dds_setup import DDSError
    from h2_bridge.telemetry.core_topics import CORE_TOPICS
    from h2_bridge.telemetry.recording_format import RecordingWriter
    from h2_bridge.telemetry.sources.base_source import TopicError
    from h2_bridge.telemetry.sources.live_source import LiveSource

    err = Console(stderr=True)
    try:
        with (
            LiveSource(args.interface, args.domain_id, CORE_TOPICS) as source,
            RecordingWriter(source, args.record) if args.record else contextlib.nullcontext() as recorder,
        ):
            saving = f" to [bold]{recorder.path}[/]" if recorder else ""
            err.print(f"Watching the {len(CORE_TOPICS)} core topics on [bold]{args.interface}[/] "
                      f"(domain {args.domain_id}){saving}. Ctrl-C to stop.")
            meter = _play(source, recorder, args.duration, show_table=not args.quiet)
    except (TopicError, DDSError) as e:
        err.print(f"[bold red]Can't watch:[/] {e}")
        return 1

    _print_summary(err, source.topics, meter, source.dropped, recorder)
    if not any(meter.total.values()):
        err.print("[bold red]No data received.[/] Check the interface and domain ID.")
        return 1
    return 0


def _cmd_replay(args):
    """Handler for `h2-doctor telemetry replay [FILE] [--speed X]`.

    1. File: FILE, or the newest .jsonl.gz in outputs/telemetry/ (find_outputs()).
    2. Source: ReplaySource(file, speed): every topic the recording holds.
    3. _play with the same dashboard as watch; ages and rates use source.now(),
       so they're in recording time.

    Ends when the recording does, then says how it ended (footer, or cut off).
    Returns 1 if there's no recording, or the file can't be read.
    """
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
        err.print(f"Newest recording: [bold]{path}[/]")
    try:
        source = ReplaySource(path, speed=args.speed)
    except (OSError, ValueError) as e:  # missing file, not a .jsonl.gz recording
        err.print(f"[bold red]Can't replay:[/] {e}")
        return 1

    header = source.header
    err.print(f"Replaying {len(source.topics)} topic(s) recorded {header.get('started', '?')} on "
              f"[bold]{header.get('host', '?')}[/] ({header.get('interface', '?')}) at {args.speed:g}x. "
              "Ctrl-C to stop.")
    with source:
        meter = _play(source, None, None, show_table=True)

    recorded_hz = (source.footer or {}).get("avg_hz")  # None: no footer, or one from before avg_hz
    _print_summary(err, source.topics, meter, None, None, recorded_hz)
    if source.footer:
        dropped = sum(source.footer.get("dropped", {}).values())
        err.print(f"Recording ended cleanly: {source.footer.get('messages', '?')} messages over "
                  f"{source.footer.get('duration_s', '?')} s, {dropped} dropped while recording.")
        if recorded_hz is None:
            err.print("[dim]This recording's footer has no average rates (made before they were saved).[/]")
    elif source.done:
        err.print("[yellow]No footer:[/] the recorder didn't close cleanly"
                  + (" (the file is cut off)." if source.truncated else "."))
    return 0


def _play(source, recorder, duration, show_table):
    """Run the poll loop on `source` with this command's consumers; return the RateMeter.

    Consumers, in order: the snapshot builder (always: it feeds the rate meter,
    so rates exist even with --quiet), the recorder (if any) and, with
    `show_table`, checkup's engine and the live dashboard, which draws the
    builder's snapshot with checkup's verdicts. The meter's `total` is the
    message count per topic.
    """
    from rich.console import Console
    from rich.live import Live

    from h2_bridge.checkup.engine import Checkup
    from h2_bridge.telemetry.poll_loop import run
    from h2_bridge.telemetry.snapshot import SnapshotBuilder

    builder = SnapshotBuilder(source.topics, source.dropped)
    consumers = [builder] + ([recorder] if recorder else [])
    if not show_table:
        run(source, consumers, duration)
        return builder.meter
    checkup = Checkup(builder)
    dashboard = _Dashboard(builder, checkup)
    with Live(dashboard.render(source.now()), console=Console(), auto_refresh=False) as live:
        dashboard.live = live
        run(source, consumers + [checkup, dashboard], duration)
    return builder.meter


class _Dashboard:
    """Poll-loop consumer that redraws the live dashboard after every batch."""

    def __init__(self, builder, checkup):
        self.builder = builder  # both must come before this in the consumer list
        self.checkup = checkup
        self.live = None  # the rich Live it draws into, set once it's open

    def add(self, messages, now):
        self.live.update(self.render(now), refresh=True)

    def render(self, now):
        from h2_bridge.cli import telemetry_tables

        return telemetry_tables.dashboard(self.builder.snapshot(now), self.checkup)


def _print_summary(err, topics, meter, dropped, recorder, recorded_hz=None):
    """One line per topic: messages, average rate (vs expected for core topics; vs the
    recording's own average on a replay), drops (live only); then where the recording went."""
    for topic, spec in topics.items():
        avg = meter.average_hz(topic)
        rate = "   -  Hz" if avg is None else f"{avg:6.2f} Hz"
        if spec.expected_hz:
            rate += f" / {spec.expected_hz:g} expected"
        if recorded_hz and recorded_hz.get(topic) is not None:
            rate += f" · {recorded_hz[topic]:g} Hz when recorded"
        lost = f"  [red]{dropped[topic]} dropped[/]" if dropped and dropped[topic] else ""
        err.print(f"  {topic:<28} {meter.total.get(topic, 0):>8} messages  avg {rate}{lost}")
    if recorder:
        err.print(f"Saved {recorder.count} messages to [bold]{recorder.path}[/]")


def _record_name(value):
    """argparse type for --record: check the name before anything starts."""
    from h2_bridge.utils.output_paths import check_name

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
