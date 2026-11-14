"""`mcflow doctor`: check every external tool the workflow relies on."""

from rich.console import Console
from rich.table import Table

from mcflow.doctor.checks import ALL_CHECKS, CheckResult, DoctorContext, Status
from mcflow.doctor.env import SystemEnv

__all__ = ["CheckResult", "DoctorContext", "Status", "render", "run_checks"]

_STYLE = {Status.OK: "green", Status.WARN: "yellow", Status.FAIL: "red"}


def run_checks(env: SystemEnv, ctx: DoctorContext) -> list[CheckResult]:
    return [check(env, ctx) for check in ALL_CHECKS]


def render(results: list[CheckResult], console: Console) -> None:
    table = Table(show_header=True, header_style="bold")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Details", overflow="fold")
    for r in results:
        table.add_row(r.name, f"[{_STYLE[r.status]}]{r.status.value}[/]", r.summary)
    console.print(table)

    to_fix = [r for r in results if r.fix and r.status is not Status.OK]
    for r in to_fix:
        console.print(f"\n[bold {_STYLE[r.status]}]{r.name}[/]: how to fix")
        for line in r.fix.splitlines():
            console.print(f"  {line}", markup=False, highlight=False, soft_wrap=True)

    failed = sum(r.status is Status.FAIL for r in results)
    warned = sum(r.status is Status.WARN for r in results)
    if failed:
        console.print(f"\n[red]{failed} problem(s) to fix[/], {warned} warning(s).")
    elif warned:
        console.print(f"\n[green]Ready to go[/], with {warned} warning(s).")
    else:
        console.print("\n[green]Everything is in place.[/]")
