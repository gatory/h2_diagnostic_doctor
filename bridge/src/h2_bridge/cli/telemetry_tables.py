"""The live dashboard for `h2-doctor telemetry watch` and `replay`: every core topic on one screen.

    dashboard(topics, newest, meter, dropped, now)   -> one rich renderable, redrawn each poll

Layout (about 150 x 46; on a smaller terminal it gets cut off at the right and bottom):

    ┌ Topics (row per topic) ┬ Battery ─────┬ Main board ┐
    ├ Body joints (31) ──────┼ Hands: joint x left │ right ┤
    │                        ├ IMUs: pelvis · torso · hands ┤

Every panel is as wide as its content (no stretching), so values sit next to
their labels; the hands and IMUs panels share one column and so one width.

Presentation only: each function takes telemetry data and returns rich objects;
printing (or redrawing it live) is up to the caller (cli/telemetry_commands.py).

Three rules:
- Facts, no verdicts. The only verdict colors are topic health (rate, staleness,
  drops). Joint limits, temperatures and error bits are shown as numbers: judging
  them is checkup's job. A "?" marks a unit or meaning that isn't confirmed
  (docs/robot_findings.md).
- One style per kind of text, everywhere, so a title never looks like a value:
  HEADER for column titles, LABEL for row labels and field names, plain for
  values, DIM for units, "?", legends and placeholders. The one exception: the
  two hands' values are LEFT and RIGHT, so the sides can't be mixed up.
- Getting values out of a message (the *_rows / *_fields functions: plain data,
  no rich) is kept apart from drawing them (the _*_panel functions), so the
  extraction can later move into telemetry for checkup and the server to share.
"""

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table

from h2_bridge.robot import joints, sensors

# Core topic names, as in telemetry/core_topics.py.
LOWSTATE = "rt/lf/lowstate"
TORSO_IMU = "rt/lf/secondary_imu"
BATTERY = "rt/lf/bmsstate"
MAIN_BOARD = "rt/lf/mainboardstate"
LEFT_HAND = "rt/dex5/left/state"
RIGHT_HAND = "rt/dex5/right/state"

# A topic counts as healthy at >= this fraction of its expected rate.
_RATE_OK = 0.8

# A topic is stale (shown red) once its newest message is older than this many
# expected periods, and at least _STALE_MIN_S seconds old.
_STALE_PERIODS = 5
_STALE_MIN_S = 0.5

# Text styles (see the module docstring). Values have no style: plain text.
HEADER = "bold cyan"  # column titles
LABEL = "bold magenta"  # row labels and field names
DIM = "dim"  # units, "?", legends, placeholders
LEFT = "orange1"  # the left hand's values (hands and IMU panels)
RIGHT = "dodger_blue1"  # the right hand's values; clearly blue, not the HEADER cyan

_WAITING = f"[{DIM}]waiting for data...[/]"


def dashboard(topics, newest, meter, dropped, now):
    """The whole screen.

    Parameters
    ----------
    topics : dict[str, TopicSpec]
        What the source delivers, in display order.
    newest : dict[str, Message]
        The newest message per topic so far (from latest()); a topic may be missing.
    meter : RateMeter
        Rates, measured from every message.
    dropped : dict[str, int] | None
        Messages lost per topic (LiveSource.dropped); None for a replay, which can't drop.
    now : float
        The source's clock (source.now()), for rates and ages.
    """
    data = {topic: message.data for topic, message in newest.items()}

    # Grids without expand or ratios: each column is as wide as its widest panel.
    top = Table.grid(padding=(0, 1))
    top.add_row(_topics_panel(topics, newest, meter, dropped, now),
                _safe(_battery_panel, "Battery", data.get(BATTERY)),
                _safe(_board_panel, "Main board", data.get(MAIN_BOARD)))

    right = Table.grid()  # one column: the hands and IMUs panels get the same width
    right.add_row(_hands_panel(data.get(LEFT_HAND), data.get(RIGHT_HAND)))
    right.add_row(_safe(_imu_panel, "IMUs", data))

    middle = Table.grid(padding=(0, 1))
    # Not _safe: before data the body panel draws its rows with dashes, so it keeps its
    # width and the hands and IMUs don't jump sideways when the first message arrives.
    middle.add_row(_body_panel(data.get(LOWSTATE)), right)

    return Group(top, middle)


# ---------------------------------------------------------------- Rows: message data -> plain values


def body_rows(lowstate):
    """One tuple per body joint: (slot, name, q, dq, tau_est, temperatures, mode, motorstate)."""
    rows = []
    for slot, (name, _, _) in enumerate(joints.BODY_JOINTS):
        m = lowstate["motor_state"][slot]
        rows.append((slot, name, m["q"], m["dq"], m["tau_est"], m["temperature"], m["mode"], m["motorstate"]))
    return rows


def hand_rows(hand):
    """One tuple per hand motor: (slot, name, q, dq, tau_est, temperature or None, mode, motorstate).

    temperature is None for the position-only thumb slots, which report none.
    """
    rows = []
    for slot, (name, _, _, position_only) in enumerate(joints.HAND_JOINTS):
        m = hand["motor_state"][slot]
        temperature = None if position_only else m["temperature"][0]
        rows.append((slot, name, m["q"], m["dq"], m["tau_est"], temperature, m["mode"], m["motorstate"]))
    return rows


def pad_maxima(hand):
    """The highest reading on each of the hand's pressure pads (16 pads x 12 cells)."""
    return [max(pad["pressure"]) for pad in hand["press_sensor_state"]]


def imu_fields(imu):
    """{"rpy", "gyro", "accel": 3 floats each; "temp": int} from an IMUState_ dict."""
    return {"rpy": imu["rpy"], "gyro": imu["gyroscope"], "accel": imu["accelerometer"], "temp": imu["temperature"]}


def battery_fields(bms):
    """The battery's values, cells trimmed to the real ones (robot/sensors.py)."""
    cells = bms["cell_vol"][: sensors.NUM_BMS_CELLS]
    return {
        "soc": bms["soc"],
        "soh": bms["soh"],
        "volts": bms["bmsvoltage"][0] / 1000,  # mV -> V; equals the sum of the cells
        "current": bms["current"],
        "cell_min": min(cells),
        "cell_max": max(cells),
        "temperatures": _trim_zeros(bms["temperature"]),
        "cycle": bms["cycle"],
        "state": bms["bmsstate"],
        "version": f"{bms['version_high']}.{bms['version_low']}",
    }


def board_fields(board):
    """The main board's values, temperatures trimmed to the real ones (robot/sensors.py)."""
    return {
        "temperatures": board["temperature"][: sensors.NUM_MAINBOARD_TEMPS],
        "fans": board["fan_state"],
        "state": board["state"],
        "value": board["value"],
    }


def _trim_zeros(values):
    """`values` without its trailing zeros (unused slots)."""
    end = len(values)
    while end and values[end - 1] == 0:
        end -= 1
    return values[:end]


# ---------------------------------------------------------------- Panels: plain values -> rich


def _safe(build, title, payload):
    """build(payload), or a placeholder panel titled `title` while there's no data
    (payload None) or if the data has an unexpected shape: one odd message must
    never crash the screen."""
    if payload is None:
        return Panel(_WAITING, title=title, title_align="left", border_style=DIM)
    try:
        return build(payload)
    except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError):
        return Panel(f"[{DIM}](unexpected message shape)[/]", title=title, title_align="left", border_style="yellow")


def _topics_panel(topics, newest, meter, dropped, now):
    """One row per topic: rate (recent / expected), average, time since the last message, drops (live only)."""
    table = _table(expand=False)
    table.add_column("topic", style=LABEL, no_wrap=True)
    for name in ("Hz", "Avg", "Last") + (("Drop",) if dropped is not None else ()):
        table.add_column(name, justify="right", no_wrap=True)
    for name, spec in topics.items():
        message = newest.get(name)
        stale = message is not None and _is_stale(spec, now - message.t)
        row = [name.removeprefix("rt/"),
               "[red]0 (stale)[/]" if stale else _rate_cell(meter.hz(name, now), spec.expected_hz),
               _avg_cell(meter.average_hz(name)),
               _age_cell(message, now, stale)]
        if dropped is not None:
            n = dropped.get(name, 0)
            row.append("[green]0[/]" if n == 0 else f"[bold red]{n}[/]")
        table.add_row(*row)

    subtitle = _legend(f"Hz: last {meter.window_s:.0f}s / expected · Avg: since start")
    if dropped is not None and sum(dropped.values()):
        subtitle = "[bold red]dropped: values are behind[/]"
    return Panel(table, title="Topics", title_align="left", subtitle=subtitle, subtitle_align="left")


def _body_panel(lowstate):
    """The 31 joints; with no data yet (None), their names with dashes, at the same width."""
    try:
        rows = None if lowstate is None else body_rows(lowstate)
        title = "Body joints · " + (_WAITING if lowstate is None else
                                    f"{_kv('mode_machine', lowstate['mode_machine'])} · "
                                    f"{_kv('mode_pr', lowstate['mode_pr'])} · {_kv('tick', lowstate['tick'])}")
    except (KeyError, IndexError, TypeError, ValueError):
        rows, title = None, f"Body joints · [{DIM}](unexpected message shape)[/]"

    table = _table(expand=False)
    table.add_column("#", justify="right", style=DIM, no_wrap=True, min_width=2)
    table.add_column("joint", style=LABEL, no_wrap=True)
    for name, width in (("q", 5), ("dq", 5), ("tau", 5), ("T °C?", 5), ("m/s?", 4)):
        table.add_column(name, justify="right", no_wrap=True, min_width=width)
    if rows is None:
        for slot, (name, *_) in enumerate(joints.BODY_JOINTS):
            table.add_row(str(slot), name, *[f"[{DIM}]-[/]"] * 5)
    else:
        for slot, name, q, dq, tau, temps, mode, state in rows:
            table.add_row(str(slot), name, _num(q, 2), _num(dq, 2), _num(tau, 1),
                          "/".join(map(str, temps)), f"{mode}/{state}")
    return Panel(table, title=title, title_align="left", expand=False,
                 subtitle=_legend("q rad · dq rad/s · tau N·m? · T: 2 sensors?"),
                 subtitle_align="left")


def _hands_panel(left, right):
    """Both hands in one table: one row per finger joint, the left hand's values, a divider, then the right's.

    One shared joint column keeps it narrow. A hand with no data yet shows dim dashes.
    """
    try:
        sides = [hand_rows(h) if h is not None else None for h in (left, right)]
        pads = [pad_maxima(h) if h is not None else None for h in (left, right)]
    except (KeyError, IndexError, TypeError, ValueError):
        return Panel(f"[{DIM}](unexpected message shape)[/]", title="Hands", title_align="left", border_style="yellow")

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
        for side, rows in zip(("left", "right"), sides):
            if side == "right":
                cells.append("│")
            if rows is None:
                cells += [f"[{DIM}]-[/]"] * len(columns)
                continue
            _, _, q, dq, tau, temperature, mode, state = rows[slot]
            cells += [_num(q, 2), _num(dq, 2), _num(tau, 2),
                      f"[{DIM}]-[/]" if temperature is None else str(temperature), f"{mode}/{state}"]
        table.add_row(*cells)

    lines = []
    for side, style, hand, maxima in (("left ", LEFT, left, pads[0]), ("right", RIGHT, right, pads[1])):
        side = f"[bold {style}]{side}[/]"
        if hand is None:
            lines.append(f"{side} {_WAITING}")
            continue
        lines.append(f"{side} {_kv('error', hand['error'])} · "
                     f"{_kv('power', _num(hand['power_v'], 2))}{_unit(' V?')} {_num(hand['power_a'], 3)}{_unit(' A?')} · "
                     f"{_kv('system', _num(hand['system_v'], 2))}{_unit(' V?')}")
        lines.append(f"{side} {_kv('pads max', ' '.join(f'{p:.0f}' for p in maxima))}{_unit(' ?')}")
    return Panel(Group(table, *lines), title=f"Hands · [{LEFT}]left[/] │ [{RIGHT}]right[/]", title_align="left",
                 subtitle=_legend("T °C? (thumb: none) · m/s: mode/motorstate? · pads: max of 16"),
                 subtitle_align="left")


def _table(expand=True):
    """A table with no column borders: they cost 3 characters a column, which this screen can't spare."""
    return Table(box=box.SIMPLE_HEAD, expand=expand, show_edge=False, header_style=HEADER,
                 pad_edge=False, padding=(0, 1))


def _imu_panel(data):
    """Pelvis (inside lowstate), torso (secondary_imu), and each hand's IMU, side by side."""
    sources = {
        "pelvis": data.get(LOWSTATE, {}).get("imu_state"),
        "torso": data.get(TORSO_IMU),
        "left hand": data.get(LEFT_HAND, {}).get("imu_state"),
        "right hand": data.get(RIGHT_HAND, {}).get("imu_state"),
    }
    fields = {name: imu_fields(imu) if imu else None for name, imu in sources.items()}

    table = _table(expand=False)
    table.add_column("", style=LABEL, no_wrap=True, min_width=5)
    side_style = {"left hand": LEFT, "right hand": RIGHT}
    for name in fields:
        style = side_style.get(name, "")
        table.add_column(name, justify="right", no_wrap=True, min_width=17,  # "+0.00 +0.00 +0.00"
                         style=style, header_style=f"bold {style}" if style else HEADER)
    for key, label in (("rpy", "rpy"), ("gyro", "gyro"), ("accel", "accel"), ("temp", "temp?")):
        cells = []
        for f in fields.values():
            if f is None:
                cells.append(f"[{DIM}]-[/]")
            elif key == "temp":
                cells.append(str(f[key]))
            else:
                cells.append(" ".join(_num(v, 2) for v in f[key]))
        table.add_row(label, *cells)
    return Panel(table, title="IMUs", title_align="left",
                 subtitle=_legend("rad · rad/s · m/s² · pelvis - torso = the waist's rotation"),
                 subtitle_align="left")


def _battery_panel(bms):
    f = battery_fields(bms)
    table = _fields_grid()
    table.add_row("charge", f"{f['soc']}{_unit('%')} · {_kv('health', f['soh'])}{_unit('%')}")
    table.add_row("voltage", f"{f['volts']:.2f}{_unit(' V')} · {_kv('current', f['current'])}{_unit(' mA?')}")
    table.add_row("cells", f"{f['cell_min']}-{f['cell_max']}{_unit(' mV')} · "
                           f"{_kv('spread', f['cell_max'] - f['cell_min'])}{_unit(' mV')}")
    table.add_row("temps", " ".join(map(str, f["temperatures"])) + _unit(" °C?"))
    table.add_row("cycles", f"{f['cycle']} · {_kv('version', f['version'])}")
    table.add_row("state", " ".join(map(str, f["state"])) + _unit(" ?"))
    return Panel(table, title="Battery", title_align="left",
                 subtitle=_legend(f"{sensors.NUM_BMS_CELLS} cells"), subtitle_align="left")


def _board_panel(board):
    f = board_fields(board)
    table = _fields_grid()
    table.add_row("temps", " ".join(map(str, f["temperatures"])) + _unit(" °C?"))
    table.add_row("fans", " ".join(map(str, f["fans"])) + _unit(" ?"))
    table.add_row("state", " ".join(map(str, f["state"])) + _unit(" ?"))
    table.add_row("value", " ".join(_num(v, 2) for v in f["value"]) + _unit(" ?"))
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


def _avg_cell(hz):
    """Average rate since the start; '-' until a topic has 2 messages."""
    return f"[{DIM}]-[/]" if hz is None else f"{hz:.1f}"


def _rate_cell(hz, expected):
    """'20.1 / 20' colored green (on rate), yellow (slow), red (silent), plain (no expectation)."""
    if expected is None:
        return f"{hz:.1f}" if hz else f"[{DIM}]0[/]"
    text = f"{hz:.1f} / {expected:g}"
    if hz == 0:
        return f"[red]{text}[/]"
    return f"[green]{text}[/]" if hz >= _RATE_OK * expected else f"[yellow]{text}[/]"
