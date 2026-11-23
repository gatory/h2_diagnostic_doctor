"""`h2-doctor telemetry ...` commands: read the robot's live data.

    h2-doctor telemetry watch <topic>
    h2-doctor telemetry record -o FILE
    h2-doctor telemetry replay FILE

Scaffold only: the commands parse arguments but don't do anything yet.
Their options will be added once the logic exists in h2_bridge.telemetry.
"""


def register(commands):
    """Add the `telemetry` group to the root parser's subcommands."""
    telemetry = commands.add_parser("telemetry", help="Read live robot data (not implemented yet)")
    telemetry_cmds = telemetry.add_subparsers(dest="telemetry_command", metavar="<command>", required=True)

    # h2-doctor telemetry watch <topic>
    watch = telemetry_cmds.add_parser("watch", help="Print one topic's messages as they arrive")
    watch.add_argument("topic", help="DDS topic name, e.g. rt/lf/lowstate")
    watch.set_defaults(func=_not_implemented)

    # h2-doctor telemetry record -o FILE
    record = telemetry_cmds.add_parser("record", help="Save telemetry to a file")
    record.add_argument("-o", "--output", metavar="FILE", required=True, help="File to write the recording to")
    record.set_defaults(func=_not_implemented)

    # h2-doctor telemetry replay FILE
    replay = telemetry_cmds.add_parser("replay", help="Play back a recording")
    replay.add_argument("file", help="Recording made by `telemetry record`")
    replay.set_defaults(func=_not_implemented)


def _not_implemented(args):
    """Placeholder handler shared by every telemetry command until it's built."""
    from rich.console import Console

    Console(stderr=True).print(f"[yellow]`telemetry {args.telemetry_command}` is not implemented yet.[/]")
    return 1
