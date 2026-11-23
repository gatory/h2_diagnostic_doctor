"""`h2-doctor discovery ...` commands: inspect what's on the DDS network.

    h2-doctor discovery topics
    h2-doctor discovery topics -t 5 -o topics.json

This module only parses arguments and prints results."""


def register(commands):
    """Add the `discovery` group to the root parser's subcommands."""
    discovery = commands.add_parser("discovery", help="Inspect DDS entities on the network")
    discovery_cmds = discovery.add_subparsers(dest="discovery_command", metavar="<command>", required=True)

    # h2-doctor discovery topics
    topics = discovery_cmds.add_parser("topics", help="List DDS topics with active publishers")
    topics.add_argument(
        "-t", "--duration", type=float, default=10, metavar="SECS",
        help="Seconds to listen for publishers (default: %(default)s)",
    )
    topics.add_argument("-o", "--output", metavar="FILE", help="Also save the discovered topics to this JSON file")
    topics.set_defaults(func=_cmd_topics)


def _cmd_topics(args):
    """Handler for `h2-doctor discovery topics`."""
    from rich.console import Console

    from h2_bridge.discovery.topic_discovery import (
        discover_publishers,
        get_topics_table,
        save_topics_to_file,
    )

    out = Console()  # stdout: the data itself
    err = Console(stderr=True)  # stderr: spinner and messages, so piping stdout stays clean

    with err.status(f"Discovering publishers on [bold]{args.interface}[/] (domain {args.domain_id}) for {args.duration}s..."):
        topics = discover_publishers(iface=args.interface, domain=args.domain_id, secs=args.duration)

    if not topics:
        err.print("[bold red]No publishers discovered.[/] Check the interface and domain ID.")
        return 1

    out.print(get_topics_table(topics))

    if args.output:
        path = save_topics_to_file(topics, filename=args.output)
        err.print(f"[green]Saved topics to[/] {path}")

    return 0
