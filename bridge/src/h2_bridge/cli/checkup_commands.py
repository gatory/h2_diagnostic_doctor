"""`h2-doctor checkup`: a preflight check of the robot's health.

    h2-doctor checkup                    # listen to the robot for 10 s, then a pass/warn/fail report
    h2-doctor checkup -t 30              # for 30 s
    h2-doctor checkup --replay           # check the newest recording instead (no robot needed)
    h2-doctor checkup --replay FILE      # check a given recording

It runs the same poll loop as `telemetry watch`, with two consumers: the
snapshot builder and the checkup engine (h2_bridge.checkup). The report is
always saved to outputs/checkup/<date>/. This module only parses arguments,
runs the loop and prints; the rules are in h2_bridge.checkup, the table in
checkup_tables.py.

Exit codes: 0 all pass · 1 couldn't run (no data, DDS error, unreadable file)
· 3 warnings, no failures · 4 at least one failure (2: bad arguments).
"""

import argparse

DEFAULT_SECS = 10.0

_EXAMPLES = """\
examples:
  h2-doctor checkup                         listen to the robot for 10 s, then report
  h2-doctor checkup -t 30                   listen for 30 s
  h2-doctor checkup --name before_walk      save as before_walk_<time>_<iface>.json
  h2-doctor checkup --replay                check the newest recording (no robot needed)
  h2-doctor checkup --replay FILE -t 20     the first 20 s of a given recording

The report is printed and saved to outputs/checkup/<date>/. It only judges
fields whose meaning is confirmed (docs/robot_findings.md); temperatures and
unknown fields are never judged. Limits: src/h2_bridge/checkup/limits.py.

exit codes:
  0  every check passed
  1  couldn't run: no data, DDS error, or an unreadable recording
  3  warnings, no failures
  4  at least one failure
"""


def register(commands):
    """Add the `checkup` command to the root parser's subcommands."""
    checkup = commands.add_parser(
        "checkup",
        help="Preflight check: listen, then a pass/warn/fail report",
        description="Listen to the core topics (or replay a recording), check them against the "
                    "health rules, print a pass/warn/fail report and save it. Read-only.",
        epilog=_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    checkup.add_argument(
        "-t", "--duration", type=_positive, default=None, metavar="SECS",
        help=f"how long to listen (default: {DEFAULT_SECS:g} s live, the whole recording with --replay)",
    )
    # --replay alone      -> "newest"
    # --replay FILE       -> FILE
    # not given           -> None: the live robot
    checkup.add_argument(
        "--replay", nargs="?", const="newest", default=None, metavar="FILE",
        help="check a .jsonl.gz recording instead of the robot (default: the newest one)",
    )
    checkup.add_argument(
        "--name", type=_report_name, default=None, metavar="NAME",
        help="start of the saved report's file name (default: checkup, or replay with --replay)",
    )
    checkup.set_defaults(func=_cmd_checkup)


def _cmd_checkup(args):
    """Handler for `h2-doctor checkup [-t SECS] [--replay [FILE]] [--name NAME]`.

    1. Source: LiveSource(iface, domain, CORE_TOPICS), or a stepped ReplaySource.
    2. The poll loop with the snapshot builder and the checkup engine.
    3. The report: printed, saved to outputs/checkup/, and turned into the exit code.
    """
    from datetime import datetime

    from rich.console import Console

    from h2_bridge.checkup import report as reports
    from h2_bridge.checkup.engine import Checkup
    from h2_bridge.cli import checkup_tables
    from h2_bridge.telemetry.snapshot import SnapshotBuilder

    err = Console(stderr=True)
    started = datetime.now().astimezone()
    opened = _open_source(args, err)
    if opened is None:
        return reports.EXIT_COULD_NOT_RUN
    source, info, run_args = opened

    from h2_bridge.dds_setup import DDSError
    from h2_bridge.telemetry.poll_loop import run
    from h2_bridge.telemetry.sources.base_source import TopicError

    try:
        with source:
            builder = SnapshotBuilder(source.topics, source.dropped)
            checkup = Checkup(builder)
            with err.status(info["status"]):
                stopped = run(source, [builder, checkup], **run_args)
            any_data = builder.snapshot(source.now()).any_data
    except (TopicError, DDSError) as e:
        err.print(f"[bold red]Can't check:[/] {e}")
        return reports.EXIT_COULD_NOT_RUN
    if stopped:
        err.print("[yellow]Stopped early (Ctrl-C):[/] the report covers only what was heard.")
    if not any_data:
        err.print("[bold red]No data received.[/] Check the interface and domain ID (nothing saved).")
        return reports.EXIT_COULD_NOT_RUN

    report = reports.build_report(checkup, started, info["source"])
    Console().print(checkup_tables.report_table(report))
    path = reports.save_report(report, args.name or info["name"], info["interface"], started)
    err.print(f"Saved the report to [bold]{path}[/]")
    return reports.exit_code(report)


def _open_source(args, err):
    """(source, info, run() keyword args) for the live robot or a recording; None (after a message) if it can't open."""
    from h2_bridge.telemetry.core_topics import CORE_TOPICS
    from h2_bridge.telemetry.poll_loop import POLL_SECS

    if args.replay is None:
        from h2_bridge.telemetry.sources.live_source import LiveSource

        secs = args.duration or DEFAULT_SECS
        source = LiveSource(args.interface, args.domain_id, CORE_TOPICS)
        info = {
            "source": {"kind": "live", "interface": args.interface, "domain_id": args.domain_id},
            "status": f"Checking the robot on {args.interface} for {secs:g} s... (Ctrl-C to stop early)",
            "name": "checkup",
            "interface": args.interface,
        }
        return source, info, {"duration": secs}

    from h2_bridge.telemetry.recording_format import EXTENSION
    from h2_bridge.telemetry.sources.replay_source import ReplaySource
    from h2_bridge.utils.output_paths import find_outputs

    path = args.replay
    if path == "newest":
        recordings = find_outputs("telemetry", ext=EXTENSION)  # newest first
        if not recordings:
            err.print("[bold red]No recordings[/] in outputs/telemetry/. Make one with `telemetry watch --record`.")
            return None
        path = str(recordings[0].path)
        err.print(f"Newest recording: [bold]{path}[/]")
    try:
        # Stepped: the clock moves POLL_SECS per poll, as a live run would, but as fast as the rules go.
        source = ReplaySource(path, step_s=POLL_SECS)
    except (OSError, ValueError) as e:  # missing file, not a .jsonl.gz recording
        err.print(f"[bold red]Can't check:[/] {e}")
        return None
    header = source.header
    info = {
        "source": {"kind": "replay", "file": str(path), "recorded": header.get("started"),
                   "host": header.get("host"), "interface": header.get("interface")},
        "status": "Checking the recording...",
        "name": "replay",
        "interface": header.get("interface") or "unknown",
    }
    return source, info, {"duration": args.duration, "poll_secs": 0}


def _report_name(value):
    """argparse type for --name: check the name before anything starts."""
    from h2_bridge.utils.output_paths import check_name

    try:
        return check_name(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from None


def _positive(value):
    """argparse type for -t: a number above 0."""
    secs = float(value)
    if secs <= 0:
        raise argparse.ArgumentTypeError(f"must be > 0, got {value}")
    return secs
