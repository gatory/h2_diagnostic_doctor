"""Rich output for `h2-doctor checkup`: the report as a table.

Presentation only: takes a report (checkup/report.py's build_report()) and
returns rich objects; printing is up to cli/checkup_commands.py.

    report_table(report)    one row per rule: status, what it checks, what it found
"""

from rich.console import Group
from rich.table import Table
from rich.text import Text

# One style per status, shared with the dashboard's warnings panel.
STATUS_STYLE = {"pass": "green", "warn": "yellow", "fail": "bold red", "no data": "dim"}


def status_text(status):
    """'PASS' / 'WARN' / 'FAIL' / 'NO DATA' in its color."""
    return Text(status.upper(), style=STATUS_STYLE.get(status, ""))


def report_table(report):
    """The whole report: one row per rule, then a line with the overall result."""
    table = Table(title="Checkup", header_style="bold cyan", title_justify="left")
    table.add_column("Status", no_wrap=True)
    table.add_column("Check", style="bold magenta", no_wrap=True)
    table.add_column("Result")

    for rule in report["rules"]:
        findings = rule["findings"]
        if rule["status"] == "no data":
            detail = Text(_no_data_reason(rule["rule"]), style="dim")
        elif not findings:
            detail = Text(f"{rule['checked']} checked, all fine", style="dim")
        else:
            lines = [f"{f['subject']}: {f['message']}" + _when(f) for f in findings[:4]]
            if len(findings) > 4:
                lines.append(f"... and {len(findings) - 4} more (see the saved report)")
            detail = "\n".join(lines)
        table.add_row(status_text(rule["status"]), rule["title"], detail)

    source = report["source"]
    where = (f"live on {source['interface']}" if source["kind"] == "live"
             else f"replay of {source['file'].rsplit('/', 1)[-1]}")
    overall = Text.assemble("Overall ", status_text(report["overall"]),
                            (f"  ·  {report['duration_s']:g} s, {where}", "dim"))
    return Group(table, overall)


def _when(finding):
    """' (from 2.0 s)' or ' (2.0-8.5 s)': when in the run it counted."""
    first, last = finding["first_s"], finding["last_s"]
    if first is None:
        return ""
    return f" [dim]({first:g}-{last:g} s)[/]" if last is not None and last - first >= 0.5 else f" [dim](at {first:g} s)[/]"


def _no_data_reason(rule):
    return {"dropped": "not known for a replay (only a live source can drop)"}.get(rule, "its topic sent nothing")
