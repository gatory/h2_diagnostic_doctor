"""Rich tables for the `h2-doctor discovery ...` commands.

Presentation only: each function takes discovery data and returns a
rich Table; printing is up to the caller (cli/discovery_commands.py). One table
per kind of row:

    topics_table(topics)                      one row per topic (the summary)
    participants_table(snapshot)              one row per participant
    endpoints_table(name, info, snapshot)     one row per writer/reader of one topic
    saved_table(files)                        one row per saved snapshot file
    modes_table(answers, all_fsms)            one row per robot query (discovery modes)
    fsm_map_table(steps, names)               one row per mode stepped through (discovery modes --map)
    fsm_text(fsm_id, names)                   "601 HybridWalk", for --watch and --map lines

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
    from h2_bridge.discovery.snapshot_views import get_participant_ips

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

    from h2_bridge.discovery.snapshot_views import group_endpoints_by_participant

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


from h2_bridge.robot.fsm import MOTION_CLIP_IDS  # FSM ids from here up are motion clips


def modes_table(answers, all_fsms=False):
    """One row per robot_queries.Answer: the query, its answer (or the error), and how long it took.

    The FSM list shows the main states; the motion clips are summed up in one line unless `all_fsms`.
    """
    from rich.table import Table

    from h2_bridge.robot_queries import QUERIES

    table = Table(title="Robot modes (query-only)", header_style="bold cyan")
    table.add_column("Query", style="bold")
    table.add_column("SDK call", style="magenta")
    table.add_column("Answer")
    table.add_column("ms", justify="right", style="dim")

    for answer in answers:
        _, method, _ = QUERIES[answer.name]
        if answer.ok:
            text = _answer_text(answer, all_fsms)
        else:
            text = f"[red]{answer.error}[/] [dim]({answer.code})[/]"
        table.add_row(answer.name, method, text, f"{answer.seconds * 1000:.0f}")
    table.caption = f"{sum(a.ok for a in answers)} of {len(answers)} answered"
    return table


def _answer_text(answer, all_fsms=False):
    """An answer's value as text; available_fsms as one "id name" line per state."""
    import json

    from rich.markup import escape

    if answer.name == "available_fsms" and isinstance(answer.value, tuple) and len(answer.value) == 2:
        ids, names = answer.value
        rows = [(i, n) for i, n in zip(ids, names) if all_fsms or i < MOTION_CLIP_IDS]
        lines = [f"{i}  {escape(str(n))}" for i, n in rows]
        clips = len(ids) - len(rows)
        if clips:
            lines.append(f"[dim]+ {clips} motion clips (ids {MOTION_CLIP_IDS}+; --all lists them)[/]")
        return "\n".join(lines) or "[dim](none)[/]"
    if isinstance(answer.value, (dict, list)):
        return escape(json.dumps(answer.value))
    return escape(str(answer.value))


def fsm_text(fsm_id, names, markup=True):
    """"601 HybridWalk" (bold), or "no answer" when the robot didn't say."""
    from rich.markup import escape

    if fsm_id is None:
        return "[red]no answer[/]" if markup else "no answer"
    name = names.get(fsm_id, "?")
    return f"[bold]{fsm_id}[/] {escape(str(name))}" if markup else f"{fsm_id} {name}"


def fsm_map_table(steps, names):
    """One row per mode stepped through in --map: the mode, its FSM id and name, and whether it was settled."""
    from rich.table import Table

    table = Table(title="FSM map (from the remote)", header_style="bold cyan")
    table.add_column("Mode", style="bold")
    table.add_column("FSM id", justify="right")
    table.add_column("FSM name", style="magenta")
    table.add_column("Readings", style="dim")

    for _, label, reading in steps:
        if reading is None:
            table.add_row(label, "-", "[dim]skipped[/]", "")
            continue
        fsm_id = "?" if reading.fsm_id is None else str(reading.fsm_id)
        readings = ", ".join("-" if r is None else str(r) for r in reading.seen)
        if not reading.stable:
            readings = f"[yellow]{readings} (changing)[/]"
        table.add_row(label, fsm_id, str(names.get(reading.fsm_id, "?")), readings)
    return table
