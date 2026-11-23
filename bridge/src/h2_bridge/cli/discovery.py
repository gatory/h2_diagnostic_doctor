"""`h2-doctor discovery ...` commands: inspect what's on the DDS network.

    h2-doctor discovery topics
    h2-doctor discovery topics --save
    h2-doctor discovery topics -t 5 -o snapshot.json

This module only parses arguments and prints results."""


def register(commands):
    """Add the `discovery` group to the root parser's subcommands."""
    discovery = commands.add_parser("discovery", help="Inspect DDS entities on the network")
    discovery_cmds = discovery.add_subparsers(dest="discovery_command", metavar="<command>", required=True)

    # h2-doctor discovery topics
    topics = discovery_cmds.add_parser("topics", help="List DDS topics with their writers and readers")
    topics.add_argument(
        "-t", "--duration", type=float, default=10, metavar="SECS",
        help="Seconds to listen (default: %(default)s)",
    )
    # Saving: --save uses the organized outputs folder, -o picks an exact file. Only one at a time.
    save = topics.add_mutually_exclusive_group()
    save.add_argument(
        "-s", "--save", action="store_true",
        help="Also save the full snapshot to outputs/discovery/<date>/",
    )
    save.add_argument("-o", "--output", metavar="FILE", help="Also save the full snapshot to this exact file")
    topics.set_defaults(func=_cmd_topics)


def _cmd_topics(args):
    """Handler for `h2-doctor discovery topics`."""
    from rich.console import Console

    from h2_bridge.discovery.collect import collect_snapshot, group_by_topic, save_snapshot

    out = Console()  # stdout: the data itself
    err = Console(stderr=True)  # stderr: spinner and messages, so piping stdout stays clean

    with err.status(f"Discovering on [bold]{args.interface}[/] (domain {args.domain_id}) for {args.duration}s..."):
        snapshot = collect_snapshot(args.interface, args.domain_id, secs=args.duration)

    if not snapshot.endpoints:
        err.print("[bold red]Nothing discovered.[/] Check the interface and domain ID.")
        return 1

    out.print(_topics_table(group_by_topic(snapshot)))

    if args.save or args.output:
        path = save_snapshot(snapshot, args.output)  # output=None -> outputs folder
        err.print(f"[green]Saved snapshot to[/] {path}")

    return 0


def _topics_table(topics):
    """Build a rich Table from group_by_topic()'s result."""
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
