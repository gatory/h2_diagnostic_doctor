"""Bridge Commands

    h2_doctor bridge discover topics
    h2_doctor bridge discover topics --iface <interface> --record
"""

import argparse


def _cmd_discover_topics(args):
    """Handler for `h2_doctor bridge discover topics`."""
    from rich.console import Console

    from h2_bridge.discovery.topic_discovery import (
        discover_publishers,
        get_topics_table,
        save_topics_to_file,
    )

    console = Console()
    with console.status(f"Discovering publishers on [bold]{args.iface}[/] (domain {args.domain}) for {args.secs}s..."):
        topics = discover_publishers(iface=args.iface, domain=args.domain, secs=args.secs)

    if not topics:
        console.print("[bold red]No publishers discovered.[/] Check the interface and domain ID.")
        return 1

    console.print(get_topics_table(topics))

    if args.record:
        path = save_topics_to_file(topics, filename=args.output)
        console.print(f"[green]Saved topics to[/] {path}")

    return 0


def build_parser():
    """Build the argparse command tree."""
    parser = argparse.ArgumentParser(prog="h2_doctor", description="H2 Diagnostic Doctor")
    commands = parser.add_subparsers(dest="command", metavar="<command>", required=True)

    # h2_doctor bridge ...
    bridge = commands.add_parser("bridge", help="On-device bridge commands")
    bridge_cmds = bridge.add_subparsers(dest="bridge_command", metavar="<bridge-command>", required=True)

    # h2_doctor bridge discover ...
    discover = bridge_cmds.add_parser("discover", help="Discover DDS entities")
    discover_cmds = discover.add_subparsers(dest="discover_command", metavar="<what>", required=True)

    # h2_doctor bridge discover topics
    topics = discover_cmds.add_parser("topics", help="List DDS topics with active publishers")
    topics.add_argument("--iface", default="eth10", help="Network interface to discover on (default: %(default)s)")
    topics.add_argument("--domain", type=int, default=0, help="DDS domain ID (default: %(default)s)")
    topics.add_argument("--secs", type=float, default=10, help="Seconds to listen for publishers (default: %(default)s)")
    topics.add_argument("--record", action="store_true", help="Save discovered topics to a JSON file")
    topics.add_argument("-o", "--output", default=None, help="JSON file path for --record (default: discovered_topics_<timestamp>.json)")
    topics.set_defaults(func=_cmd_discover_topics)

    return parser


def cli(args=None):
    """Parse `args` (defaults to sys.argv[1:]) and run the selected command."""
    parser = build_parser()
    ns = parser.parse_args(args)
    return ns.func(ns)
