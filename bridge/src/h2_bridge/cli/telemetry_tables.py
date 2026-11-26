"""The live dashboard for `h2-doctor telemetry watch` and `replay`: every core topic on one screen.

    dashboard(topics, newest, meter, dropped, now)   -> one rich renderable, redrawn each poll

Layout (about 160 x 50; on a smaller terminal it gets cut off at the right and bottom):

    ┌ Topics: Hz / expected · Avg · Last · dropped, one column per topic ─────────┐
    ├ Body joints (31) ──────────┬ Hands (20 joints: left values | right values) ─┤
    │                            ├ IMUs: pelvis · torso · left hand · right hand ─┤
    ├ Battery ───────────────────┴ Main board ─────────────────────────────────────┤

Presentation only: each function takes telemetry data and returns rich objects;
printing (or redrawing it live) is up to the caller (cli/telemetry_commands.py).

Two rules:
- Facts, no verdicts. The only colors are topic health (rate, staleness). Joint
  limits, temperatures and error bits are shown as numbers: judging them is
  checkup's job. A "?" marks a unit or meaning that isn't confirmed
  (docs/robot_findings.md).
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

_WAITING = "[dim]waiting for data...[/]"


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

    middle = Table.grid(expand=True)
    middle.add_column()  # body: its natural width, so its numbers never get cut
    middle.add_column(ratio=1)  # hands and IMUs: the rest
    middle.add_row(_safe(_body_panel, "Body joints", data.get(LOWSTATE)),
                   Group(_hands_panel(data.get(LEFT_HAND), data.get(RIGHT_HAND)), _safe(_imu_panel, "IMUs", data)))

    bottom = Table.grid(expand=True)
    bottom.add_column(ratio=1)
    bottom.add_column(ratio=1)
    bottom.add_row(_safe(_battery_panel, "Battery", data.get(BATTERY)),
                   _safe(_board_panel, "Main board", data.get(MAIN_BOARD)))

    return Group(_topics_panel(topics, newest, meter, dropped, now), middle, bottom)


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
        return Panel(_WAITING, title=title, title_align="left", border_style="dim")
    try:
        return build(payload)
    except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError):
        return Panel("[dim](unexpected message shape)[/]", title=title, title_align="left", border_style="yellow")


def _topics_panel(topics, newest, meter, dropped, now):
    """One column per topic: rate (recent / expected), average, time since the last message, drops."""
    table = _table()
    table.add_column("", style="bold", no_wrap=True)
    for name in topics:
        table.add_column(name.removeprefix("rt/"), justify="right", no_wrap=True, overflow="ellipsis")

    rates, averages, ages, lost = ["Hz"], ["Avg"], ["Last"], ["Dropped"]
    for name, spec in topics.items():
        message = newest.get(name)
        stale = message is not None and _is_stale(spec, now - message.t)
        rates.append("[red]0 (stale)[/]" if stale else _rate_cell(meter.hz(name, now), spec.expected_hz))
        averages.append(_avg_cell(meter.average_hz(name)))
        ages.append(_age_cell(message, now, stale))
        if dropped is not None:
            n = dropped.get(name, 0)
            lost.append("[green]0[/]" if n == 0 else f"[bold red]{n}[/]")
    for row in (rates, averages, ages):
        table.add_row(*row)
    if dropped is not None:
        table.add_row(*lost)

    caption = f"rates over the last {meter.window_s:.0f}s · Avg since the start"
    if dropped is not None and sum(dropped.values()):
        caption += " · [bold red]messages dropped: rates and values are behind[/]"
    return Panel(table, title="Topics", subtitle=caption, subtitle_align="right")


def _body_panel(lowstate):
    table = _table(expand=False)
    table.add_column("#", justify="right", style="dim", no_wrap=True, min_width=2)
    table.add_column("joint", style="bold", no_wrap=True)
    for name, width in (("q", 5), ("dq", 5), ("tau", 5), ("T °C?", 5), ("m/s?", 4)):
        table.add_column(name, justify="right", no_wrap=True, min_width=width)
    for slot, name, q, dq, tau, temps, mode, state in body_rows(lowstate):
        table.add_row(str(slot), name, _num(q, 2), _num(dq, 2), _num(tau, 1),
                      "/".join(map(str, temps)), f"{mode}/{state}")
    title = (f"Body joints · mode_machine {lowstate['mode_machine']} · mode_pr {lowstate['mode_pr']} "
             f"· tick {lowstate['tick']}")
    return Panel(table, title=title, title_align="left", expand=False,
                 subtitle="q rad · dq rad/s · tau N·m? · T: 2 sensors?", subtitle_align="left")


def _hands_panel(left, right):
    """Both hands in one table: one row per finger joint, the left hand's values then the right's.

    One shared joint column keeps it narrow. A hand with no data yet shows dim dashes.
    """
    try:
        sides = [hand_rows(h) if h is not None else None for h in (left, right)]
        pads = [pad_maxima(h) if h is not None else None for h in (left, right)]
    except (KeyError, IndexError, TypeError, ValueError):
        return Panel("[dim](unexpected message shape)[/]", title="Hands", title_align="left", border_style="yellow")

    table = _table()
    # The joint names are the one thing that may shrink (to "middle_knuckle_sw…"), never the numbers.
    table.add_column("joint", style="bold", no_wrap=True, overflow="ellipsis", ratio=1, min_width=12)
    for style in ("", "cyan"):  # left hand, then the right hand in cyan
        for name, width in (("q", 5), ("dq", 5), ("tau", 5), ("T", 2), ("m/s", 3)):
            table.add_column(name, justify="right", no_wrap=True, min_width=width, style=style,
                             header_style=f"bold {style or 'cyan'}")
    for slot, (name, *_) in enumerate(joints.HAND_JOINTS):
        cells = [name]
        for rows in sides:
            if rows is None:
                cells += ["[dim]-[/]"] * 5
                continue
            _, _, q, dq, tau, temperature, mode, state = rows[slot]
            cells += [_num(q, 2), _num(dq, 2), _num(tau, 2),
                      "[dim]-[/]" if temperature is None else str(temperature), f"{mode}/{state}"]
        table.add_row(*cells)

    lines = []
    for side, style, hand, maxima in (("left ", "bold", left, pads[0]), ("right", "bold cyan", right, pads[1])):
        if hand is None:
            lines.append(f"[{style}]{side}[/] {_WAITING}")
            continue
        lines.append(f"[{style}]{side}[/] error {hand['error']} · power {_num(hand['power_v'], 2)} V? "
                     f"{_num(hand['power_a'], 3)} A? · system {_num(hand['system_v'], 2)} V?")
        lines.append(f"[{style}]{side}[/] pads max? {' '.join(f'{p:.0f}' for p in maxima)}")
    return Panel(Group(table, *lines), title="Hands · left | [cyan]right[/]", title_align="left",
                 subtitle="T °C? (thumb: position only) · m/s: mode/motorstate? · pads: max pressure of 16 pads",
                 subtitle_align="left")


def _table(expand=True):
    """A table with no column borders: they cost 3 characters a column, which this screen can't spare."""
    return Table(box=box.SIMPLE_HEAD, expand=expand, show_edge=False, header_style="bold cyan",
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

    table = _table()
    table.add_column("", style="bold", no_wrap=True, min_width=5)
    for name in fields:
        table.add_column(name, justify="right", no_wrap=True, min_width=17)  # "+0.00 +0.00 +0.00"
    for key, label in (("rpy", "rpy"), ("gyro", "gyro"), ("accel", "accel"), ("temp", "temp?")):
        cells = []
        for f in fields.values():
            if f is None:
                cells.append("[dim]-[/]")
            elif key == "temp":
                cells.append(str(f[key]))
            else:
                cells.append(" ".join(_num(v, 2) for v in f[key]))
        table.add_row(label, *cells)
    return Panel(table, title="IMUs", title_align="left",
                 subtitle="rpy rad · gyro rad/s · accel m/s² · pelvis - torso = the waist's rotation",
                 subtitle_align="left")


def _battery_panel(bms):
    f = battery_fields(bms)
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("charge", f"{f['soc']}% · health {f['soh']}%")
    table.add_row("voltage", f"{f['volts']:.2f} V · current {f['current']} (mA?)")
    table.add_row("cells", f"{f['cell_min']}-{f['cell_max']} mV · spread {f['cell_max'] - f['cell_min']} mV "
                           f"({sensors.NUM_BMS_CELLS} cells)")
    table.add_row("temps", " ".join(map(str, f["temperatures"])) + " °C?")
    table.add_row("other", f"cycles {f['cycle']} · bmsstate {f['state']} ? · version {f['version']}")
    return Panel(table, title="Battery", title_align="left")


def _board_panel(board):
    f = board_fields(board)
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("temps", " ".join(map(str, f["temperatures"])) + " °C? (which parts: unknown)")
    table.add_row("fans", f"{f['fans']} ?")
    table.add_row("state", f"{f['state']} ?")
    table.add_row("value", " ".join(_num(v, 2) for v in f["value"]) + " ?")
    return Panel(table, title="Main board", title_align="left")


# ---------------------------------------------------------------- Cells


def _num(value, decimals=3):
    """A float as fixed-width text; NaN/inf (None after msg_to_dict) as a dim 'NaN'."""
    if value is None:
        return "[dim]NaN[/]"
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
    return "[dim]-[/]" if hz is None else f"{hz:.1f}"


def _rate_cell(hz, expected):
    """'20.1 / 20' colored green (on rate), yellow (slow), red (silent), plain (no expectation)."""
    if expected is None:
        return f"{hz:.1f}" if hz else "[dim]0[/]"
    text = f"{hz:.1f} / {expected:g}"
    if hz == 0:
        return f"[red]{text}[/]"
    return f"[green]{text}[/]" if hz >= _RATE_OK * expected else f"[yellow]{text}[/]"
