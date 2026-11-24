"""Rich tables for the `h2-doctor discovery ...` commands.

Presentation only: each function takes discovery data and returns a
rich Table; printing is up to the caller (cli/discovery.py). One table
per kind of row:

    topics_table(topics)                      one row per topic (the summary)
    participants_table(snapshot)              one row per participant
    endpoints_table(name, info, snapshot)     one row per writer/reader of one topic
    saved_table(files)                        one row per saved snapshot file

participants_table and endpoints_table share the owner columns
(Participants, Process, PID, Host, IP) via the _owner_* helpers below.
"""


def topics_table(topics):
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


def participants_table(snapshot):
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


def endpoints_table(name, info, snapshot):
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


def saved_table(files):
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
