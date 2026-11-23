"""Where saved files go, so every command saves in the same organized pattern.

    outputs/<group>/<YYYY-MM-DD>/<name>_<HHMMSS>_<interface>.<ext>

    e.g. outputs/discovery/2026-11-23/snapshot_161435_eth10.json
"""

from datetime import datetime

from h2_bridge.constants import OUTPUT_DIR


def output_path(group, name, interface, when=None, ext="json"):
    """Return a path in the outputs folder, creating its folders if needed.

    Parameters
    ----------
    group : str
        Which part of the bridge made it, e.g. "discovery" or "telemetry".
    name : str
        What it is, e.g. "snapshot".
    interface : str
        Network interface it was taken on, so laptop tests and robot runs
        are easy to tell apart by file name.
    when : datetime | None
        Time to put in the path (e.g. when a run started). Defaults to now.
    ext : str
        File extension, without the dot.
    """
    when = when or datetime.now()
    folder = OUTPUT_DIR / group / when.strftime("%Y-%m-%d")
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{name}_{when:%H%M%S}_{interface}.{ext}"
