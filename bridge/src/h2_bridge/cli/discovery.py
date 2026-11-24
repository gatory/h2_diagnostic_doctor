"""`h2-doctor discovery ...` commands: inspect what's on the DDS network.

`topics` listens on the network (needs the robot); `show` reads saved
snapshots from outputs/discovery/ (works anywhere).

    h2-doctor discovery topics                      # listen 10 s, print the per-topic summary
    h2-doctor discovery topics -t 5 --save          # listen 5 s, also save the snapshot
    h2-doctor discovery topics --save before_walk   # save it named "before_walk"

    h2-doctor discovery show                        # newest snapshot: per-topic summary
    h2-doctor discovery show before_walk            # newest snapshot named "before_walk"
    h2-doctor discovery show --list                 # every saved snapshot
    h2-doctor discovery show --participants         # one row per participant (DDS connection)
    h2-doctor discovery show --endpoints rt/lowcmd  # one row per writer/reader of one topic

`show` has one view per kind of row: topics (default), participants,
endpoints, saved files. This module only parses arguments and prints
results; the logic is in h2_bridge.discovery.
"""

import argparse

# Examples shown at the bottom of `-h`, kept next to the parsers they describe.
_TOPICS_EXAMPLES = """\
examples:
  h2-doctor discovery topics                      listen 10 s, print the per-topic summary
  h2-doctor discovery topics -t 5 --save          listen 5 s, also save the snapshot
  h2-doctor discovery topics --save before_walk   save it as outputs/discovery/<date>/before_walk_<time>_<iface>.json
  h2-doctor --iface eth0 discovery topics         listen on another interface (global option, before the group)
"""

_SHOW_EXAMPLES = """\
views (pick one; default is the per-topic summary):
  (none)               one row per topic: its message type, writer and reader counts
  -p, --participants   one row per participant: Participant ID, process, PID, host, IP, counts
  -e, --endpoints T    one row per writer/reader of topic T, with its owner and QoS
  -l, --list           one row per saved snapshot file

examples:
  h2-doctor discovery show                          newest snapshot
  h2-doctor discovery show before_walk              newest snapshot saved as --save before_walk
  h2-doctor discovery show snapshot_155001_eth10    one exact file (name without .json)
  h2-doctor discovery show -p                       who is on the network
  h2-doctor discovery show -e rt/lowcmd             who writes and reads rt/lowcmd
"""


def register(commands):
    """Add the `discovery` group to the root parser's subcommands."""
    discovery = commands.add_parser(
        "discovery",
        help="Inspect what's on the DDS network (live, or from saved snapshots)",
        description="See which programs are on the robot's DDS network and what they send and listen for.",
    )
    discovery_cmds = discovery.add_subparsers(dest="discovery_command", metavar="<command>", required=True)

    # h2-doctor discovery topics
    topics = discovery_cmds.add_parser(
        "topics",
        help="Listen on the network and list every topic with its writers and readers",
        description="Listen on the DDS network for a while, then print one row per topic. "
                    "Needs the robot's network (see the global --iface / --domain).",
        epilog=_TOPICS_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,  # keep the examples' line breaks
    )
    topics.add_argument(
        "-t", "--duration", type=float, default=10, metavar="SECS",
        help="Seconds to listen; longer catches programs that announce slowly (default: %(default)s)",
    )
    # --save alone      -> name "snapshot"
    # --save my_label   -> name "my_label"   (the folder can't be changed)
    # not given         -> None, nothing saved
    topics.add_argument(
        "-s", "--save", nargs="?", const="snapshot", default=None, type=_save_name, metavar="NAME",
        help="Also save the full snapshot to outputs/discovery/<date>/, "
             "optionally named NAME (default name: snapshot)",
    )
    topics.set_defaults(func=_cmd_topics)

    # h2-doctor discovery show [NAME] [--list | --participants | --endpoints TOPIC]
    # Reads outputs/discovery/ only, so it works without the robot.
    show = discovery_cmds.add_parser(
        "show",
        help="Show a saved snapshot from outputs/discovery/ (no robot needed)",
        description="Read a snapshot saved by `discovery topics --save` and print it as a table. "
                    "Works anywhere, e.g. on a laptop after copying outputs/ from the Thor.",
        epilog=_SHOW_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    show.add_argument(
        "name", nargs="?", default=None,
        help="which snapshot: a saved name (picks the newest with that name) or a full "
             "file name without .json, like snapshot_155001_eth10 (default: the newest)",
    )
    # Which view; one at a time. None given: the per-topic summary.
    view = show.add_mutually_exclusive_group()
    view.add_argument(
        "-p", "--participants", action="store_true",
        help="one row per participant (DDS connection): Participant ID, process, PID, host, IP, writer/reader counts",
    )
    view.add_argument(
        "-e", "--endpoints", metavar="TOPIC",
        help="one row per endpoint (writer or reader) of TOPIC, with its owner and QoS",
    )
    view.add_argument("-l", "--list", action="store_true", help="one row per saved snapshot file, newest first")
    show.set_defaults(func=_cmd_show)


def _cmd_topics(args):
    """Handler for `h2-doctor discovery topics`: collect a snapshot, print the per-topic summary, maybe save it."""
    from rich.console import Console

    from h2_bridge.discovery.analysis import group_by_topic
    from h2_bridge.discovery.collect import collect_snapshot
    from h2_bridge.discovery.persistence import save_snapshot

    out = Console()  # stdout: the data itself
    err = Console(stderr=True)  # stderr: spinner and messages, so piping stdout stays clean

    with err.status(f"Discovering on [bold]{args.interface}[/] (domain {args.domain_id}) for {args.duration}s..."):
        snapshot = collect_snapshot(args.interface, args.domain_id, secs=args.duration)

    if not snapshot.endpoints:
        err.print("[bold red]Nothing discovered.[/] Check the interface and domain ID.")
        return 1

    out.print(_topics_table(group_by_topic(snapshot)))

    if args.save:
        path = save_snapshot(snapshot, name=args.save)
        err.print(f"[green]Saved snapshot to[/] {path}")

    return 0


def _cmd_show(args):
    """Handler for `h2-doctor discovery show`.

    Picks a saved snapshot (newest, or newest matching `name`), prints a
    one-line summary of the run, then one view: --participants, --endpoints
    TOPIC, or the per-topic summary. --list lists the files instead.
    """
    from rich.console import Console

    from h2_bridge.discovery.analysis import group_by_topic
    from h2_bridge.discovery.persistence import load_snapshot
    from h2_bridge.outputs import find_outputs

    out = Console()
    err = Console(stderr=True)

    files = find_outputs("discovery")  # newest first
    if not files:
        err.print("[bold red]No saved snapshots.[/] Save one with `discovery topics --save`.")
        return 1

    if args.list:
        out.print(_saved_table(files))
        return 0

    if args.name:
        # Match the <name> part, or the whole file name without ".json".
        matches = [f for f in files if args.name in (f.name, f.path.stem)]
        if not matches:
            names = ", ".join(sorted({f.name for f in files}))
            err.print(f"[bold red]No snapshot named {args.name!r}.[/] Saved names: {names}")
            return 1
        chosen = matches[0]  # newest with that name
    else:
        chosen = files[0]  # newest overall

    try:
        snapshot = load_snapshot(chosen.path)
    except ValueError as e:
        err.print(f"[bold red]{e}[/]")
        return 1

    out.print(
        f"[bold]{chosen.path.name}[/]  taken {snapshot.taken_at} on {snapshot.host}, "
        f"{snapshot.interface} (domain {snapshot.domain_id}), {snapshot.duration_s}s: "
        f"{len(snapshot.participants)} participants, {len(snapshot.endpoints)} endpoints"
    )

    if args.participants:
        out.print(_participants_table(snapshot))
        return 0

    if args.endpoints:
        topics = group_by_topic(snapshot)
        if args.endpoints not in topics:
            import difflib

            close = difflib.get_close_matches(args.endpoints, topics, n=5, cutoff=0.5)
            hint = f" Did you mean: {', '.join(close)}?" if close else ""
            err.print(f"[bold red]No topic {args.endpoints!r} in this snapshot.[/]{hint}")
            return 1
        out.print(_endpoints_table(args.endpoints, topics[args.endpoints], snapshot))
        return 0

    out.print(_topics_table(group_by_topic(snapshot)))
    return 0


# Owner columns: who an entry belongs to, in the same order and style in every table:
# Participants (ID) -> Process -> PID -> Host -> IP
def _add_owner_columns(table):
    """Add the shared owner columns to a rich Table."""
    table.add_column("Participants", style="bold")
    table.add_column("Process")
    table.add_column("PID", justify="right", style="dim")
    table.add_column("Host", style="magenta")
    table.add_column("IP")


def _owner_cells(participant, participant_key):
    """Cell values for the owner columns. `participant` may be None if it wasn't seen."""
    from h2_bridge.discovery.analysis import get_participant_ips

    if participant is None:
        return [participant_key[:13], "?", "?", "?", "?"]
    props = participant.properties
    return [
        participant.key[:13],  # short form of the key; enough to tell participants apart
        props.get("__ProcessName", "?"),
        props.get("__Pid", "?"),
        props.get("__Hostname", "?"),
        ", ".join(get_participant_ips(participant)) or "?",
    ]


def _owner_sort_key(participant):
    """Sort by host, then process, then PID, so a program's participants sit together."""
    if participant is None:
        return ("~", "", 0)  # unknown owners last
    props = participant.properties
    pid = props.get("__Pid", "")
    return (
        props.get("__Hostname", ""),
        props.get("__ProcessName", ""),
        int(pid) if pid.isdigit() else 0,  # numeric, so 999 sorts before 1000
    )


def _participants_table(snapshot):
    """Build a rich Table with one row per participant (one DDS connection).

    Columns go from the participant itself to where it lives:
    Participant ID -> the program (Process, PID) that opened it -> the computer (Host, IP).
    """
    from rich.table import Table

    from h2_bridge.discovery.analysis import group_endpoints_by_participant

    owned = group_endpoints_by_participant(snapshot)

    table = Table(title="Participants", header_style="bold cyan")
    _add_owner_columns(table)
    table.add_column("Writers", justify="right", style="green")
    table.add_column("Readers", justify="right", style="yellow")

    for p in sorted(snapshot.participants, key=_owner_sort_key):
        mine = owned.get(p.key, [])
        table.add_row(
            *_owner_cells(p, p.key),
            str(sum(e.kind == "writer" for e in mine)),
            str(sum(e.kind == "reader" for e in mine)),
        )

    table.caption = f"{len(snapshot.participants)} participant(s)"
    return table


def _endpoints_table(name, info, snapshot):
    """Build a rich Table of every endpoint on one topic (info = one group_by_topic() entry).

    Writers first, then readers; each group sorted like the participants table.
    """
    from rich.table import Table

    participants = {p.key: p for p in snapshot.participants}

    table = Table(title=f"{name}  ({', '.join(sorted(info['types']))})", header_style="bold cyan")
    table.add_column("Kind")
    _add_owner_columns(table)
    table.add_column("Reliability")
    table.add_column("Durability")
    table.add_column("Type info", justify="center")

    for group in (info["writers"], info["readers"]):
        for e in sorted(group, key=lambda e: _owner_sort_key(participants.get(e.participant_key))):
            table.add_row(
                "[green]writer[/]" if e.kind == "writer" else "[yellow]reader[/]",
                *_owner_cells(participants.get(e.participant_key), e.participant_key),
                e.qos.get("Reliability", {}).get("kind", "?"),
                e.qos.get("Durability", {}).get("kind", "?"),
                "✓" if e.has_type_info else "✗",
            )

    table.caption = f"{len(info['writers'])} writer(s), {len(info['readers'])} reader(s)"
    return table


def _saved_table(files):
    """Build a rich Table listing saved snapshots (find_outputs()'s result), newest first."""
    from rich.table import Table

    table = Table(title="Saved Snapshots", header_style="bold cyan")
    table.add_column("Date")
    table.add_column("Time")
    table.add_column("Name", style="bold")
    table.add_column("Interface", style="magenta")
    table.add_column("File", style="dim")

    for f in files:
        table.add_row(f.date, f"{f.time[:2]}:{f.time[2:4]}:{f.time[4:]}", f.name, f.interface, f.path.name)

    table.caption = f"{len(files)} snapshot(s) in outputs/discovery/"
    return table


def _save_name(value):
    """argparse type for --save: check the name before any discovery runs."""
    import argparse

    from h2_bridge.outputs import check_name

    try:
        return check_name(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from None


def _topics_table(topics):
    """Build the per-topic summary table (one row per topic) from group_by_topic()'s result."""
    from rich.table import Table

    table = Table(title="Discovered DDS Topics", header_style="bold cyan")
    table.add_column("Topic", style="bold")
    table.add_column("Message Type", style="magenta")
    table.add_column("Writers", justify="right", style="green")
    table.add_column("Readers", justify="right", style="yellow")

    for name in sorted(topics):
        info = topics[name]
        table.add_row(
            name,
            "\n".join(sorted(info["types"])),  # usually one; several would show one per line
            str(len(info["writers"])),
            str(len(info["readers"])),
        )

    table.caption = f"{len(topics)} topic(s)"
    return table
