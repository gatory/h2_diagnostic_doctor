"""Where saved files go, so every command saves in the same organized pattern.

    outputs/<group>/<YYYY-MM-DD>/<name>_<HHMMSS>_<interface>.<ext>

    e.g. outputs/discovery/2026-11-23/snapshot_161435_eth10.json

Rule: every file the bridge writes gets its path from output_path().
Callers may choose the <name> part, but never the folder, so all results
end up in one place.
"""

import re
from datetime import datetime

from h2_bridge.constants import OUTPUT_DIR

# Letters, digits, "-", "_" and "." only, not starting with ".".
# No "/" or "\" means a name can never point outside its folder (e.g. "../x").
_NAME_PATTERN = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._-]*")


def check_name(name):
    """Return `name` if it's safe to use as the <name> part, else raise ValueError."""
    if not _NAME_PATTERN.fullmatch(name):
        raise ValueError(
            f"invalid name {name!r}: use only letters, digits, '-', '_' and '.' "
            "(no folders; the location is always outputs/<group>/<date>/)"
        )
    return name


def output_path(group, name, interface, when=None, ext="json"):
    """Return a path in the outputs folder, creating its folders if needed.

    Parameters
    ----------
    group : str
        Which part of the bridge made it, e.g. "discovery" or "telemetry".
    name : str
        What it is, e.g. "snapshot" or a user-chosen label. Checked with check_name().
    interface : str
        Network interface it was taken on, so laptop tests and robot runs
        are easy to tell apart by file name.
    when : datetime | None
        Time to put in the path (e.g. when a run started). Defaults to now.
    ext : str
        File extension, without the dot.
    """
    check_name(name)
    when = when or datetime.now()
    folder = OUTPUT_DIR / group / when.strftime("%Y-%m-%d")
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{name}_{when:%H%M%S}_{interface}.{ext}"
