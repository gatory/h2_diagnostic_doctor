"""Sorts where saved outputs go so they follow the same organized pattern.

    outputs/<group>/<YYYY-MM-DD>/<name>_<HHMMSS>_<interface>.<ext>

    e.g. outputs/discovery/2026-11-23/snapshot_161435_eth10.json

    Saved file may have custom [NAME] but may not have custom paths for consistency.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from h2_bridge.constants import OUTPUT_DIR

# Name Format Check: letters, digits, "-", "_" and "." only, not starting with ".".
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
        Name of the file without extension, checked by check_name() for safety.
    interface : str
        Network interface it was taken on, so laptop tests and robot runs
        are easy to tell apart by file name.
    when : datetime | None
        Time to put in the path (e.g. when a run started, not when function is executed).
    ext : str
        File extension, without the dot.
    """
    check_name(name)
    when = when or datetime.now()
    folder = OUTPUT_DIR / group / when.strftime("%Y-%m-%d")
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{name}_{when:%H%M%S}_{interface}.{ext}"


class SavedFile(NamedTuple):
    """Read only representation of one file in the outputs folder, with its path split back into parts."""

    path: Path
    date: str  # "2026-11-23" (the folder)
    time: str  # "161435"
    name: str  # "snapshot", "before_walk", ...
    interface: str  # "eth10", ...


# Reverses output_path()'s file name, once the extension is removed: <name>_<HHMMSS>_<interface>
_FILE_PATTERN = re.compile(r"(?P<name>.+)_(?P<time>\d{6})_(?P<interface>.+)")


def find_outputs(group, ext="json"):
    """List the files saved under outputs/<group>/ with extension `ext`, newest first.

    `ext` is matched exactly and may contain dots ("jsonl.gz"): it's removed
    before the name is split, so it can't leak into the interface part.
    Files that don't follow the output_path() pattern are skipped.
    """
    suffix = f".{ext}"
    files = []
    for path in (OUTPUT_DIR / group).glob(f"*/*{suffix}"):
        match = _FILE_PATTERN.fullmatch(path.name[: -len(suffix)])
        if match:
            files.append(SavedFile(path, path.parent.name, match["time"], match["name"], match["interface"]))
    return sorted(files, key=lambda f: (f.date, f.time), reverse=True)
