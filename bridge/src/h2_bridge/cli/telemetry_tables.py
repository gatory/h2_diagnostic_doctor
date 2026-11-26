"""The live dashboard for `h2-doctor telemetry watch` and `replay`: every core topic on one screen.

    dashboard(snapshot, checkup)   -> one rich renderable, redrawn each poll
                                     (telemetry.snapshot.Snapshot, checkup.engine.Checkup or None)

Layout (about 155 x 50; on a smaller terminal it gets cut off at the right and bottom):

    ┌ Topics (row per topic) ┬ Battery ────┬ Warnings (checkup's findings) ┐
    │                        ├ Main board ─┤                               │
    ├ Body joints (31) ──────┼ Hands: joint x left │ right ────────────────┤
    │                        ├ IMUs: pelvis · torso · hands ────────────────┤

Every panel is as wide as its content (no stretching), so values sit next to
their labels; the hands and IMUs panels share one column and so one width.

Presentation only: each function takes telemetry data and returns rich objects;
printing (or redrawing it live) is up to the caller (cli/telemetry_commands.py).

Three rules:
- Facts, no verdicts of its own. Verdicts come from checkup: the topic colors
  (its topic_flow rule) and the Warnings panel (its findings). Everything else
  is shown as numbers. A "?" marks a unit or meaning that isn't confirmed
  (docs/robot_findings.md).
- One style per kind of text, everywhere, so a title never looks like a value:
  HEADER for column titles, LABEL for row labels and field names, plain for
  values, DIM for units, "?", legends and placeholders. The one exception: the
  two hands' values are LEFT and RIGHT, so the sides can't be mixed up.
- Only drawing happens here. Getting named values out of messages is
  telemetry/snapshot.py's job, shared with checkup (and later the server).
"""

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table

from h2_bridge.checkup.models import Status
from h2_bridge.robot import joints, sensors
from h2_bridge.telemetry.snapshot import BATTERY, HANDS, LOWSTATE, MAIN_BOARD

# Text styles (see the module docstring). Values have no style: plain text.
HEADER = "bold cyan"  # column titles
LABEL = "bold magenta"  # row labels and field names
DIM = "dim"  # units, "?", legends, placeholders
LEFT = "orange1"  # the left hand's values (hands and IMU panels)
RIGHT = "dodger_blue1"  # the right hand's values; clearly blue, not the HEADER cyan

# Checkup verdicts: the color of a topic's rate, and of a finding's status in the Warnings panel.
VERDICT = {Status.PASS: "green", Status.WARN: "yellow", Status.FAIL: "bold red"}

# The Warnings panel lists at most this many findings (worst first), then "and N more".
_MAX_WARNINGS = 10

_WAITING = f"[{DIM}]waiting for data...[/]"


def dashboard(snap, checkup=None):
    """The whole screen for one Snapshot; `checkup` (the engine, run on the same snapshots) gives the verdicts."""
    power = Table.grid()  # one column: battery over main board, at the same width
    power.add_row(_safe(_battery_panel, "Battery", snap.battery, BATTERY in snap.bad))
    power.add_row(_safe(_board_panel, "Main board", snap.board, MAIN_BOARD in snap.bad))

    # Grids without expand or ratios: each column is as wide as its widest panel;
    # only the Warnings panel takes whatever width is left.
    top = Table.grid(padding=(0, 1), expand=True)
    top.add_column()
    top.add_column()
    top.add_column(ratio=1)
    top.add_row(_topics_panel(snap, checkup), power, _warnings_panel(checkup))

    right = Table.grid()  # one column: the hands and IMUs panels get the same width
    right.add_row(_hands_panel(snap))
    right.add_row(_imu_panel(snap))

    middle = Table.grid(padding=(0, 1))
    # The body panel draws its rows with dashes before data, so it keeps its width and
    # the hands and IMUs don't jump sideways when the first message arrives.
    middle.add_row(_body_panel(snap.body, LOWSTATE in snap.bad), right)

    return Group(top, middle)


# ---------------------------------------------------------------- Panels: plain values -> rich


def _safe(build, title, part, bad):
    """build(part), or a placeholder panel titled `title`: "(unexpected message shape)"
    if the topic's newest message couldn't be read (`bad`), "waiting for data" while
    there's none yet (`part` None)."""
    if bad:
        return _bad_shape(title)
    if part is None:
        return Panel(_WAITING, title=title, title_align="left", border_style=DIM)
    return build(part)


def _bad_shape(title):
    return Panel(f"[{DIM}](unexpected message shape)[/]", title=title, title_align="left", border_style="yellow")


def _topics_panel(snap, checkup):
    """One row per topic: rate (recent / expected), average, time since the last message, drops (live only).

    The rate is colored by checkup's verdict on the topic (green ok, yellow slow,
    red silent or stale), plain before it has one.
    """
    live = any(status.dropped is not None for status in snap.topics.values())
    table = _table(expand=False)
    table.add_column("topic", style=LABEL, no_wrap=True)
    for name in ("Hz", "Avg", "Last") + (("Drop",) if live else ()):
        table.add_column(name, justify="right", no_wrap=True)
    for name, status in snap.topics.items():
        verdict = checkup.status_of("topic_flow", name) if checkup else None
        failing = verdict == Status.FAIL
        row = [name.removeprefix("rt/"),
               _rate_cell(status.hz, status.expected_hz, verdict),
               _avg_cell(status.avg_hz),
               _age_cell(status.age_s, failing)]
        if live:
            n = status.dropped or 0
            row.append("[green]0[/]" if n == 0 else f"[bold red]{n}[/]")
        table.add_row(*row)

    subtitle = _legend("Hz: last 2s / expected · Avg: since start")
    if live and sum(status.dropped or 0 for status in snap.topics.values()):
        subtitle = "[bold red]messages dropped: rates read low[/]"
    return Panel(table, title="Topics", title_align="left", subtitle=subtitle, subtitle_align="left")


def _warnings_panel(checkup):
    """checkup's current findings (debounced), worst first; "none" when everything passes."""
    title = "Warnings"
    if checkup is None:
        return Panel(f"[{DIM}](checkup not running)[/]", title=title, title_align="left", border_style=DIM)
    findings = checkup.findings()
    if not findings:
        body = "[green]none[/]" if checkup.started is not None else _WAITING
        return Panel(body, title=title, title_align="left",
                     subtitle=_legend("from checkup's rules"), subtitle_align="left")
    table = Table.grid(padding=(0, 1))
    table.add_column(no_wrap=True)  # status
    table.add_column(style=LABEL, no_wrap=True)  # subject
    table.add_column(overflow="ellipsis", no_wrap=True)  # message
    for f in findings[:_MAX_WARNINGS]:
        table.add_row(f"[{VERDICT[f.status]}]{f.status.value.upper()}[/]", f.subject.removeprefix("rt/"), f.message)
    extra = len(findings) - _MAX_WARNINGS
    parts = [table] + ([f"[{DIM}]... and {extra} more[/]"] if extra > 0 else [])
    worst = VERDICT[findings[0].status]
    return Panel(Group(*parts), title=f"{title} ({len(findings)})", title_align="left", border_style=worst,
                 subtitle=_legend("full report: h2-doctor checkup"), subtitle_align="left")


def _body_panel(body, bad):
    """The 31 joints; with no data yet (None), their names with dashes, at the same width."""
    if bad:
        title = f"Body joints · [{DIM}](unexpected message shape)[/]"
    elif body is None:
        title = f"Body joints · {_WAITING}"
    else:
        title = (f"Body joints · {_kv('mode_machine', body.mode_machine)} · "
                 f"{_kv('mode_pr', body.mode_pr)} · {_kv('tick', body.tick)}")

    table = _table(expand=False)
    table.add_column("#", justify="right", style=DIM, no_wrap=True, min_width=2)
    table.add_column("joint", style=LABEL, no_wrap=True)
    for name, width in (("q", 5), ("dq", 5), ("tau", 5), ("T °C?", 5), ("m/s?", 4)):
        table.add_column(name, justify="right", no_wrap=True, min_width=width)
    if body is None:
        for slot, (name, *_) in enumerate(joints.BODY_JOINTS):
            table.add_row(str(slot), name, *[f"[{DIM}]-[/]"] * 5)
    else:
        for j in body.joints:
            table.add_row(str(j.slot), j.name, _num(j.q, 2), _num(j.dq, 2), _num(j.tau, 1),
                          "/".join(map(str, j.temperatures)), f"{j.mode}/{j.motorstate}")
    return Panel(table, title=title, title_align="left", expand=False,
                 subtitle=_legend("q rad · dq rad/s · tau N·m? · T: 2 sensors?"),
                 subtitle_align="left")


def _hands_panel(snap):
    """Both hands in one table: one row per finger joint, the left hand's values, a divider, then the right's.

    One shared joint column keeps it narrow. A hand with no data yet shows dim dashes.
    """
    if any(topic in snap.bad for topic in HANDS.values()):
        return _bad_shape("Hands")
    left, right = snap.hands["left"], snap.hands["right"]

    columns = (("q", 5), ("dq", 5), ("tau", 5), ("T", 2), ("m/s", 3))
    table = _table(expand=False)  # natural width: the numbers sit right next to the joint names
    table.collapse_padding = True  # 1 space between columns, not 2: room for both hands and the divider
    table.add_column("joint", style=LABEL, no_wrap=True)
    for side, style in (("left", LEFT), ("right", RIGHT)):
        if side == "right":
            table.add_column("│", style=DIM, header_style=DIM, no_wrap=True)  # divider between the hands
        for name, width in columns:
            table.add_column(name, justify="right", no_wrap=True, min_width=width, style=style)
    for slot, (name, *_) in enumerate(joints.HAND_JOINTS):
        cells = [name]
        for side, hand in (("left", left), ("right", right)):
            if side == "right":
                cells.append("│")
            if hand is None:
                cells += [f"[{DIM}]-[/]"] * len(columns)
                continue
            m = hand.motors[slot]
            cells += [_num(m.q, 2), _num(m.dq, 2), _num(m.tau, 2),
                      f"[{DIM}]-[/]" if m.temperature is None else str(m.temperature), f"{m.mode}/{m.motorstate}"]
        table.add_row(*cells)

    lines = []
    for side, style, hand in (("left ", LEFT, left), ("right", RIGHT, right)):
        side = f"[bold {style}]{side}[/]"
        if hand is None:
            lines.append(f"{side} {_WAITING}")
            continue
        lines.append(f"{side} {_kv('error', list(hand.error))} · "
                     f"{_kv('power', _num(hand.power_v, 2))}{_unit(' V?')} {_num(hand.power_a, 3)}{_unit(' A?')} · "
                     f"{_kv('system', _num(hand.system_v, 2))}{_unit(' V?')}")
        lines.append(f"{side} {_kv('pads max', ' '.join(f'{p:.0f}' for p in hand.pad_max))}{_unit(' ?')}")
    return Panel(Group(table, *lines), title=f"Hands · [{LEFT}]left[/] │ [{RIGHT}]right[/]", title_align="left",
                 subtitle=_legend("T °C? (thumb: none) · m/s: mode/motorstate? · pads: max of 16"),
                 subtitle_align="left")


def _table(expand=True):
    """A table with no column borders: they cost 3 characters a column, which this screen can't spare."""
    return Table(box=box.SIMPLE_HEAD, expand=expand, show_edge=False, header_style=HEADER,
                 pad_edge=False, padding=(0, 1))


def _imu_panel(snap):
    """Pelvis (inside lowstate), torso (secondary_imu), and each hand's IMU, side by side."""
    hands = snap.hands
    fields = {
        "pelvis": snap.body and snap.body.imu,
        "torso": snap.torso_imu,
        "left hand": hands["left"] and hands["left"].imu,
        "right hand": hands["right"] and hands["right"].imu,
    }

    table = _table(expand=False)
    table.add_column("", style=LABEL, no_wrap=True, min_width=5)
    side_style = {"left hand": LEFT, "right hand": RIGHT}
    for name in fields:
        style = side_style.get(name, "")
        table.add_column(name, justify="right", no_wrap=True, min_width=17,  # "+0.00 +0.00 +0.00"
                         style=style, header_style=f"bold {style}" if style else HEADER)
    for key, label in (("rpy", "rpy"), ("gyro", "gyro"), ("accel", "accel"), ("temperature", "temp?")):
        cells = []
        for imu in fields.values():
            if imu is None:
                cells.append(f"[{DIM}]-[/]")
            elif key == "temperature":
                cells.append(str(imu.temperature))
            else:
                cells.append(" ".join(_num(v, 2) for v in getattr(imu, key)))
        table.add_row(label, *cells)
    return Panel(table, title="IMUs", title_align="left",
                 subtitle=_legend("rad · rad/s · m/s² · pelvis - torso = the waist's rotation"),
                 subtitle_align="left")


def _battery_panel(b):
    table = _fields_grid()
    table.add_row("charge", f"{b.soc}{_unit('%')} · {_kv('health', b.soh)}{_unit('%')}")
    table.add_row("voltage", f"{b.volts:.2f}{_unit(' V')} · {_kv('current', b.current)}{_unit(' mA?')}")
    table.add_row("cells", f"{b.cell_min}-{b.cell_max}{_unit(' mV')} · "
                           f"{_kv('spread', b.cell_spread)}{_unit(' mV')}")
    table.add_row("temps", " ".join(map(str, b.temperatures)) + _unit(" °C?"))
    table.add_row("cycles", f"{b.cycle} · {_kv('version', b.version)}")
    table.add_row("state", " ".join(map(str, b.state)) + _unit(" ?"))
    return Panel(table, title="Battery", title_align="left",
                 subtitle=_legend(f"{sensors.NUM_BMS_CELLS} cells"), subtitle_align="left")


def _board_panel(board):
    table = _fields_grid()
    table.add_row("temps", " ".join(map(str, board.temperatures)) + _unit(" °C?"))
    table.add_row("fans", " ".join(map(str, board.fans)) + _unit(" ?"))
    table.add_row("state", " ".join(map(str, board.state)) + _unit(" ?"))
    table.add_row("value", " ".join(_num(v, 2) for v in board.value) + _unit(" ?"))
    return Panel(table, title="Main board", title_align="left",
                 subtitle=_legend("which part each temp is: unknown"), subtitle_align="left")


def _fields_grid():
    """Two columns, LABEL then value: for panels that are a list of fields rather than a table."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style=LABEL, no_wrap=True)
    table.add_column()
    return table


def _kv(label, value):
    """'label value' with the label styled as a field name, for fields inside a line of text."""
    return f"[{LABEL}]{label}[/] {value}"


def _unit(text):
    """A unit, '?' or note after a value, dimmed so the number stands out."""
    return f"[{DIM}]{text}[/]"


def _legend(text):
    """A panel subtitle explaining units: dimmed, so it never reads as data."""
    return f"[{DIM}]{text}[/]"


# ---------------------------------------------------------------- Cells


def _num(value, decimals=3):
    """A float as fixed-width text; NaN/inf (None after msg_to_dict) as a dim 'NaN'."""
    if value is None:
        return f"[{DIM}]NaN[/]"
    return f"{value:+.{decimals}f}"


def _age_cell(age, failing):
    """'0.0s' since the newest message; red when checkup fails the topic, '-' before the first."""
    if age is None:
        return "-"
    text = f"{age:.1f}s"
    return f"[red]{text}[/]" if failing else text


def _avg_cell(hz):
    """Average rate since the start; '-' until a topic has 2 messages."""
    return f"[{DIM}]-[/]" if hz is None else f"{hz:.1f}"


def _rate_cell(hz, expected, verdict):
    """'20.1 / 20' in checkup's verdict color (green, yellow, red); plain with no verdict yet."""
    text = f"{hz:.1f}" if expected is None else f"{hz:.1f} / {expected:g}"
    style = VERDICT.get(verdict)
    if style:
        return f"[{style}]{text}[/]"
    return text if hz else f"[{DIM}]{text}[/]"
