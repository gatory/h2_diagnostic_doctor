"""Rich tables for the `h2-doctor telemetry ...` commands.

Presentation only: each function takes telemetry data and returns a rich
Table; printing (or redrawing it live) is up to the caller (cli/telemetry_commands.py).

    watch_table(topics, newest, meter, dropped, now)                 one row per topic, redrawn live
    topic_view(name, spec, message, meter, dropped, now)             every value of one topic, redrawn live
"""

# A topic counts as healthy at >= this fraction of its expected rate.
_RATE_OK = 0.8

# A topic is stale (shown red) once its newest message is older than this many
# expected periods, and at least _STALE_MIN_S seconds old.
_STALE_PERIODS = 5
_STALE_MIN_S = 0.5


def watch_table(topics, newest, meter, dropped, now):
    """One row per watched topic: its rate, how long since the last message, and a summary.

    Parameters
    ----------
    topics : dict[str, TopicSpec]
        What is being watched, in display order.
    newest : dict[str, Message]
        The newest message per topic so far (from latest()); a topic may be missing.
    meter : RateMeter
        Rates, measured from every message.
    dropped : dict[str, int] | None
        Messages lost per topic because the loop fell behind (LiveSource.dropped);
        None for a replay, which can't drop.
    now : float
        The source's clock (source.now()), for rates and the "Last" column.
    """
    from rich.table import Table

    from h2_bridge.cli.telemetry_summaries import summarize

    table = Table(title="Telemetry", header_style="bold cyan")
    table.add_column("Topic", style="bold", no_wrap=True)
    table.add_column("Type", style="magenta", no_wrap=True)
    table.add_column("Hz", justify="right", no_wrap=True)
    table.add_column("Last", justify="right", no_wrap=True)
    table.add_column("Summary", overflow="ellipsis", no_wrap=True)

    for name, spec in topics.items():
        message = newest.get(name)
        stale = message is not None and _is_stale(spec, now - message.t)
        table.add_row(
            name,
            spec.msg_type.__name__,
            "[red]0 (stale)[/]" if stale else _rate_cell(meter.hz(name, now), spec.expected_hz),
            _age_cell(message, now, stale),
            "[dim]waiting for data...[/]" if message is None else summarize(spec, message.data),
        )

    caption = f"{len(topics)} topics · rates over the last {meter.window_s:.0f}s"
    if dropped is not None:
        lost = sum(dropped.values())
        caption += " · " + (
            "[green]0 dropped[/]" if lost == 0 else f"[bold red]{lost} dropped: rates and values are behind[/]"
        )
    table.caption = caption
    return table


def _is_stale(spec, age):
    """True if a topic's newest message is too old for its expected rate."""
    limit = _STALE_PERIODS / spec.expected_hz if spec.expected_hz else 0.0
    return age > max(limit, _STALE_MIN_S)


def _age_cell(message, now, stale):
    """'0.0s' since the newest message; red when stale, '-' before the first."""
    if message is None:
        return "-"
    text = f"{now - message.t:.1f}s"
    return f"[red]{text}[/]" if stale else text


def _rate_cell(hz, expected):
    """'20.1 / 20' colored green (on rate), yellow (slow), red (silent), plain (no expectation)."""
    if expected is None:
        return f"{hz:.1f}" if hz else "[dim]0[/]"
    text = f"{hz:.1f} / {expected:g}"
    if hz == 0:
        return f"[red]{text}[/]"
    return f"[green]{text}[/]" if hz >= _RATE_OK * expected else f"[yellow]{text}[/]"


def topic_view(name, spec, message, meter, dropped, now):
    """Every value of one topic's newest message: a status line, a field list, and slot tables.

    Works for any message type without knowing it: the message dict is split by
    _split_fields() into plain fields (shown as Field | Value) and lists of
    sub-messages like motor_state (shown as one row per slot, one column per field).
    Slots get names from h2_bridge.robot.joints where it has them (joints, fingers).

    Parameters are as for watch_table, but for one topic: `message` is its newest
    Message (None until the first arrives) and `dropped` is its dropped count
    (None for a replay).
    """
    from rich.console import Group
    from rich.table import Table

    status = (
        f"[bold]{name}[/]  [magenta]{spec.msg_type.__name__}[/]  ·  "
        f"{_rate_cell(meter.hz(name, now), spec.expected_hz)} Hz  ·  "
        + ("[dim]waiting for data...[/]" if message is None else f"last {now - message.t:.1f}s ago")
        + ("" if not dropped else f"  ·  [bold red]{dropped} dropped[/]")
    )
    if message is None:
        return Group(status)

    fields, slot_lists = _split_fields(message.data)

    field_table = Table(header_style="bold cyan", show_edge=False)
    field_table.add_column("Field", style="bold", no_wrap=True)
    field_table.add_column("Value")
    for key, value in fields.items():
        field_table.add_row(key, _fmt(value))

    tables = []
    for key, slots in slot_lists.items():
        names = _slot_names(spec, key)
        columns = list(slots[0])  # the sub-message's field names, e.g. q, dq, tau_est
        table = Table(title=f"{key} ({len(slots)} slots)", header_style="bold cyan", show_edge=False)
        table.add_column("#", justify="right", style="dim")
        if names:
            table.add_column("Name", style="bold", no_wrap=True)
        for column in columns:
            table.add_column(column, justify="right")
        for i, slot in enumerate(slots):
            label = [names[i] if i < len(names) else "[dim](unused)[/]"] if names else []
            table.add_row(str(i), *label, *(_fmt(slot[c]) for c in columns))
        tables.append(table)

    return Group(status, field_table, *tables)


def _split_fields(data, prefix=""):
    """Split a message dict into ({"dotted.field": value}, {"dotted.field": [slot dicts]}).

    Nested sub-messages are flattened with dots (imu_state.rpy); lists whose items
    are sub-messages (motor_state) are kept apart so they can become tables.
    """
    fields, slot_lists = {}, {}
    for key, value in data.items():
        path = prefix + key
        if isinstance(value, dict):
            more_fields, more_lists = _split_fields(value, path + ".")
            fields.update(more_fields)
            slot_lists.update(more_lists)
        elif isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
            slot_lists[path] = value
        else:
            fields[path] = value
    return fields, slot_lists


def _slot_names(spec, field):
    """Names for the slots of a list field, from h2_bridge.robot.joints; [] if it has none."""
    from h2_bridge.robot import joints

    known = {
        ("LowState_", "motor_state"): [name for name, *_ in joints.BODY_JOINTS],
        ("HandState_", "motor_state"): [name for name, *_ in joints.HAND_JOINTS],
    }
    return known.get((spec.msg_type.__name__, field), [])


def _fmt(value):
    """One value as short, fixed-ish width text: floats to 3 decimals, lists space-separated."""
    if isinstance(value, float):
        return f"{value:+.3f}"
    if isinstance(value, list):
        return " ".join(_fmt(v) for v in value)
    if value is None:
        return "[dim]NaN[/]"  # to_dict turns NaN/inf into None
    return str(value)
