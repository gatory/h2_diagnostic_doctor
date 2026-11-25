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
results; the logic is in h2_bridge.discovery and the tables in
discovery_tables.py.
"""

import argparse

from h2_bridge.cli import discovery_tables

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
    from h2_bridge.discovery.topic_cache import load_topic_cache, update_topic_cache

    out = Console()  # stdout: the data itself
    err = Console(stderr=True)  # stderr: spinner and messages, so piping stdout stays clean

    with err.status(f"Discovering on [bold]{args.interface}[/] (domain {args.domain_id}) for {args.duration}s..."):
        snapshot = collect_snapshot(args.interface, args.domain_id, secs=args.duration)

    if not snapshot.endpoints:
        err.print("[bold red]Nothing discovered.[/] Check the interface and domain ID.")
        return 1

    out.print(discovery_tables.topics_table(group_by_topic(snapshot)))

    changes = update_topic_cache(snapshot)  # so telemetry can watch these topics without discovery
    known = len(load_topic_cache())
    err.print(f"[dim]Topic cache: {known} topics ({len(changes['new'])} new, {len(changes['changed'])} changed, "
              f"{len(changes['removed'])} removed for conflicting types)[/]")

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
    from h2_bridge.utils.outputs import find_outputs

    out = Console()
    err = Console(stderr=True)

    files = find_outputs("discovery")  # newest first
    if not files:
        err.print("[bold red]No saved snapshots.[/] Save one with `discovery topics --save`.")
        return 1

    if args.list:
        out.print(discovery_tables.saved_table(files))
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
        out.print(discovery_tables.participants_table(snapshot))
        return 0

    if args.endpoints:
        topics = group_by_topic(snapshot)
        if args.endpoints not in topics:
            import difflib

            close = difflib.get_close_matches(args.endpoints, topics, n=5, cutoff=0.5)
            hint = f" Did you mean: {', '.join(close)}?" if close else ""
            err.print(f"[bold red]No topic {args.endpoints!r} in this snapshot.[/]{hint}")
            return 1
        out.print(discovery_tables.endpoints_table(args.endpoints, topics[args.endpoints], snapshot))
        return 0

    out.print(discovery_tables.topics_table(group_by_topic(snapshot)))
    return 0


def _save_name(value):
    """argparse type for --save: check the name before any discovery runs."""
    import argparse

    from h2_bridge.utils.outputs import check_name

    try:
        return check_name(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from None
