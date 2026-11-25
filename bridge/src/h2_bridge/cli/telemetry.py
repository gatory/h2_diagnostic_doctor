"""`h2-doctor telemetry ...` commands: watch the robot's live data, record it, replay it.

    h2-doctor telemetry watch                                  # core topics, until Ctrl-C
    h2-doctor telemetry watch rt/lf/bmsstate rt/odommodestate  # any topics by name
    h2-doctor telemetry watch rt/lf/bmsstate --record          # also save what's watched
    h2-doctor telemetry replay FILE                            # play a recording back
    h2-doctor telemetry replay FILE rt/lf/bmsstate --speed 4   # some of it, 4x faster

Both commands pick topics the same way (a catalog: the robot for watch, the
recording for replay) and share one display loop. This module only parses
arguments and drives the display; the logic is in h2_bridge.telemetry and the
tables in telemetry_tables.py.
"""

import argparse

_WATCH_EXAMPLES = """\
examples:
  h2-doctor telemetry watch                                   overview of the core topics until Ctrl-C
  h2-doctor telemetry watch rt/lf/lowstate                    every value of one topic (one row per joint)
  h2-doctor telemetry watch rt/lf/bmsstate rt/odommodestate   any topics; non-core ones are found by discovery
  h2-doctor telemetry watch -t 30                             stop after 30 s
  h2-doctor telemetry watch rt/lf/bmsstate --record           also save it to outputs/telemetry/<date>/
  h2-doctor telemetry watch --record before_walk -t 60        save the core topics as before_walk_<time>_<iface>.jsonl
  h2-doctor --iface eth0 telemetry watch                      another interface (global option, before the group)

Put TOPICs before --record: `--record rt/lf/x` would read the topic as NAME.

core topics: rt/lf/lowstate, rt/lf/secondary_imu, rt/lf/bmsstate, rt/lf/mainboardstate,
             rt/dex5/left/state, rt/dex5/right/state

overview columns:
  Hz        measured rate / expected rate (green: on rate, yellow: slow, red: silent)
  Last      seconds since the topic's newest message
  Summary   a few key fields of the newest message; "?" marks an unconfirmed unit
"""

_REPLAY_EXAMPLES = """\
examples:
  h2-doctor telemetry replay FILE                     every recorded topic, at the recorded pace
  h2-doctor telemetry replay FILE rt/lf/bmsstate      only some of the recorded topics
  h2-doctor telemetry replay FILE --speed 4           4x faster (rates and ages stay in recording time)

FILE is a .jsonl made by `telemetry watch --record`. Needs no robot or network.
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

    # h2-doctor telemetry watch [TOPIC ...] [-t SECS] [--record [NAME]]
    watch = telemetry_cmds.add_parser(
        "watch",
        help="Live table of the core topics, or of any topics by name",
        description="Subscribe to robot topics and redraw a live table as data arrives: the core "
                    "topics by default, or the TOPICs given (any topic on the network). "
                    "Needs the robot's network (see the global --iface / --domain). Read-only.",
        epilog=_WATCH_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    watch.add_argument(
        "topics", nargs="*", metavar="TOPIC",
        help="topics to watch (default: the core topics); non-core ones are looked up by discovery",
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
    """Handler for `h2-doctor telemetry watch [TOPIC ...] [-t SECS] [--record [NAME]]`.

    1. Topics: LiveCatalog(iface, domain).select(args.topics or None):
       core topics instantly, others from the cache, then discovery.
    2. Source: LiveSource(iface, domain, topics).
    3. With --record: a RecordingWriter for the same topics.
    4. The shared loop (_run): poll ~4 times a second, hand every message to
       the rate meter and the recorder, keep the newest per topic for the table.

    Returns 1 if no data arrived (wrong interface or domain?) or a topic can't be found.
    """
    return _not_implemented(args)


def _cmd_replay(args):
    """Handler for `h2-doctor telemetry replay FILE [TOPIC ...] [--speed X]`.

    1. Topics: RecordingCatalog(FILE).select(args.topics or None):
       every recorded topic, or only the TOPICs given.
    2. Source: ReplaySource(FILE, topics, speed).
    3. The shared loop (_run), the same table as watch; ages and rates use
       source.now(), so they're in recording time.

    Ends when the recording does; says so if its last line was cut off.
    """
    return _not_implemented(args)


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


def _not_implemented(args):
    """Placeholder handler for telemetry commands that aren't built yet."""
    from rich.console import Console

    Console(stderr=True).print(f"[yellow]`telemetry {args.telemetry_command}` is not implemented yet.[/]")
    return 1
