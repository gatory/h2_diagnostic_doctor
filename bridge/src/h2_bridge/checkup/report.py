"""The checkup report: what a run found, as plain data, and saving it as JSON.

    report = build_report(checkup, started=..., source={...})
    path = save_report(report, name="checkup", interface="eth10")
    exit_code(report)       # 0 pass, 3 warnings, 4 failures (1 "couldn't run" is the CLI's)

Saved to outputs/checkup/<date>/<name>_<time>_<interface>.json (via output_path()):

    {"checkup": 1, "started": "2026-11-26T14:02:10-08:00", "duration_s": 10.0,
     "source": {"kind": "live", "interface": "eth10", "domain_id": 0},
     "overall": "warn",
     "rules": [{"rule": "cell_spread", "title": "Battery cells balanced", "status": "warn",
                "description": "...", "checked": 1,
                "findings": [{"subject": "battery", "status": "warn", "message": "cell spread 61 mV (3830-3891)",
                              "value": 61, "limit": 50, "first_s": 2.0, "last_s": 10.0}]}, ...]}

first_s / last_s are seconds since the start of the run, on the source's clock.
"""

import json

from h2_bridge.checkup.models import Status

REPORT_VERSION = 1

# Exit codes for `h2-doctor checkup` (2 is argparse's: bad arguments).
EXIT_PASS = 0
EXIT_COULD_NOT_RUN = 1  # no data, DDS error, unreadable file
EXIT_WARN = 3  # warnings, no failures
EXIT_FAIL = 4  # at least one failure


def build_report(checkup, started, source):
    """The report for a finished run, as JSON-safe data.

    started: when the run began (datetime, for the report and the file name);
    source: what was checked, e.g. {"kind": "live", "interface": "eth10", "domain_id": 0}.
    """
    t0 = checkup.started or 0.0
    since = lambda t: None if t is None else round(t - t0, 2)  # noqa: E731
    return {
        "checkup": REPORT_VERSION,
        "started": started.isoformat(timespec="seconds"),
        "duration_s": round((checkup.last or t0) - t0, 1),
        "source": source,
        "overall": checkup.overall().value,
        "rules": [
            {
                "rule": r.name,
                "title": r.title,
                "status": r.status.value,
                "description": r.description,
                "checked": r.checked,
                "findings": [
                    {"subject": subject, "status": obs.status.value, "message": obs.message,
                     "value": _round(obs.value), "limit": obs.limit,
                     "first_s": since(first), "last_s": since(last)}
                    for subject, obs, first, last in r.bad
                ],
            }
            for r in checkup.results()
        ],
    }


def save_report(report, name, interface, started):
    """Write the report to outputs/checkup/<date>/<name>_<time>_<interface>.json; return the path."""
    from h2_bridge.utils.output_paths import output_path

    path = output_path("checkup", name, interface, when=started, ext="json")
    with open(path, "x") as f:  # "x": never overwrite a report
        json.dump(report, f, indent=2)
    return path


def exit_code(report):
    """0 if everything passed (or had no data), 3 for warnings only, 4 for any failure."""
    overall = Status(report["overall"])
    return {Status.FAIL: EXIT_FAIL, Status.WARN: EXIT_WARN}.get(overall, EXIT_PASS)


def _round(value):
    return round(value, 3) if isinstance(value, float) else value
