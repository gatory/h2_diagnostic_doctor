"""What the server sends: one Snapshot plus checkup's verdicts, as JSON-safe data.

This is the contract between the bridge and the dashboard. One kind of message
for now, sent many times a second, always complete (never a diff), so a browser
that connects late is up to date with the first message it gets:

    {"type": "snapshot",
     "protocol": 1,
     "source": "live" | "replay",
     "t": 1795799761.78,                      # the source's clock (recording time on a replay)
     "snapshot": {                            # telemetry.snapshot.Snapshot, field for field
        "topics": {"rt/lf/lowstate": {"name": ..., "hz": 20.1, "expected_hz": 20.0, ...}, ...},
        "body": {"joints": [{"slot": 0, "name": "L_hip_pitch", "q": 0.12, "lower": ..., "upper": ...,
                             ...}, ...],
                 "imu": {...}, "mode_machine": 6, "mode_pr": 0, "tick": ...} | null,
        "torso_imu": {...} | null,
        "hands": {"left": {...} | null, "right": {...} | null},
        "battery": {...} | null,
        "board": {...} | null,
        "bad": ["rt/lf/bmsstate"]},           # topics whose newest message had an unexpected shape
     "checkup": {
        "now": "pass" | "warn" | "fail",      # the worst finding counting right now (pass if none)
        "worst": "pass" | "warn" | "fail" | "no data",   # the worst of the whole run
        "running_s": 4.2,                     # how long checkup has judged, on the source's clock
        "preflight_s": 10.0,                  # PREFLIGHT_S: how long before its verdict counts
        "preflight": true,                    # running_s < preflight_s: show "Preflight...", not a verdict
        "findings": [{"rule": "joint_limits", "subject": "L_knee", "status": "warn",
                      "message": "...", "value": -0.118, "limit": -0.087, "since": ...}, ...]}}

A part of the snapshot is null before its first message. Every number is finite
or null: NaN/inf become null, since JSON has no NaN (a browser's JSON.parse rejects it).
Bump PROTOCOL when a field is renamed or removed (adding one doesn't need it).
"""

import dataclasses
import math

from h2_bridge.checkup.limits import PREFLIGHT_S
from h2_bridge.checkup.models import Status

PROTOCOL = 1


def snapshot_message(snap, checkup, live):
    """The message for one Snapshot and the Checkup that judged it (plain dicts, lists, numbers)."""
    snapshot = _clean(dataclasses.asdict(snap))
    del snapshot["t"]  # it's at the top level
    snapshot["bad"] = sorted(snap.bad)
    findings = checkup.findings()  # worst first
    running = 0.0 if checkup.started is None else checkup.last - checkup.started
    return {
        "type": "snapshot",
        "protocol": PROTOCOL,
        "source": "live" if live else "replay",
        "t": _clean(snap.t),
        "snapshot": snapshot,
        "checkup": {
            "now": findings[0].status.value if findings else Status.PASS.value,
            "worst": checkup.overall().value,
            "running_s": _clean(running),
            "preflight_s": PREFLIGHT_S,
            "preflight": running < PREFLIGHT_S,
            "findings": [_clean(dataclasses.asdict(f)) for f in findings],
        },
    }


def _clean(value):
    """Make `value` JSON-safe: tuples/sets -> lists, NaN/inf -> None, enums -> their value."""
    if isinstance(value, Status):
        return value.value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_clean(item) for item in value]
    return value
