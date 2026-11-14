"""The `mcflow` command line."""

import dataclasses
import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from mcflow import __version__, doctor, paper, scaffold
from mcflow.doctor.env import SystemEnv
from mcflow.project import ProjectConfig, find_project_root, load
from mcflow.versions import pins

app = typer.Typer(
    help="AI development workflow for Paper plugins with custom resource packs.",
    no_args_is_help=True,
    add_completion=False,
)
kb_app = typer.Typer(
    help="Sync the knowledge base with the shared GitHub repo.", no_args_is_help=True
)
app.add_typer(kb_app, name="kb")

console = Console()
err = Console(stderr=True)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"mcflow {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
) -> None:
    pass


def _ask_paper_version(versions: list[paper.PaperVersion]) -> paper.PaperVersion:
    newest = versions[0].id
    floor = pins()["paper"]["minimum_version"]
    while True:
        answer = typer.prompt(
            f"Which Paper version does the plugin target? ({floor} to {newest}, or 'latest')",
            default="latest",
        )
        try:
            return paper.resolve(answer, versions)
        except paper.UnsupportedPaperVersion as e:
            err.print(f"[red]{e}[/]")


@app.command()
def init(
    path: Annotated[Path, typer.Argument(help="Folder for the new workspace.")] = Path("."),
    paper_version: Annotated[
        str | None,
        typer.Option(
            "--paper-version", "-p", help="Target Paper version, e.g. 1.21.11 or 'latest'."
        ),
    ] = None,
    name: Annotated[
        str | None, typer.Option(help="Project name. Defaults to the folder name.")
    ] = None,
    offline: Annotated[
        bool,
        typer.Option(help="Use mcflow's built-in Paper version list instead of asking PaperMC."),
    ] = False,
) -> None:
    """Create a new mcflow project workspace."""
    root = path.resolve()
    if find_project_root(root) == root:
        err.print(f"[red]{root} is already an mcflow workspace.[/]")
        raise typer.Exit(1)

    versions, source = paper.available_versions(online=not offline)
    if source == "cached" and not offline:
        err.print("[yellow]Couldn't reach PaperMC; using mcflow's built-in version list.[/]")
    if paper_version is None:
        target = _ask_paper_version(versions)
    else:
        try:
            target = paper.resolve(paper_version, versions)
        except paper.UnsupportedPaperVersion as e:
            err.print(f"[red]{e}[/]")
            raise typer.Exit(1) from None

    config = ProjectConfig(
        name=name or root.name,
        paper_version=target.id,
        java_minimum=target.java_minimum,
        knowledge_repo=pins()["knowledge"]["default_repo"],
    )
    try:
        created = scaffold.create(root, config)
    except scaffold.WorkspaceConflict as e:
        err.print("[red]Nothing was written, because these files already exist:[/]")
        for p in e.existing:
            err.print(f"  {p}")
        err.print("Move them aside, or run `mcflow init` in an empty folder.")
        raise typer.Exit(1) from None

    console.print(f"[green]Created {config.name}[/] in {root} ({len(created)} files).")
    console.print(f"Target: Paper {target.id}, Java {target.java_minimum}+.")
    if not target.supported:
        console.print(
            "[yellow]PaperMC no longer supports this version. It still works with mcflow.[/]"
        )
    console.print("\nNext:")
    console.print(f"  cd {path}" if path != Path(".") else "  (you're already in the folder)")
    console.print("  mcflow doctor      # check Java, Node, ctags, TokToken and Claude Code")
    console.print("  claude             # start working")


def _doctor_context(paper_version: str | None, offline: bool) -> doctor.DoctorContext:
    requested = paper_version
    if requested is None and (root := find_project_root(Path.cwd())) is not None:
        requested = load(root).paper_version
    if requested is None:
        return doctor.DoctorContext(paper=None)
    versions, source = paper.available_versions(online=not offline)
    try:
        return doctor.DoctorContext(paper=paper.resolve(requested, versions), paper_source=source)
    except paper.UnsupportedPaperVersion as e:
        err.print(f"[red]{e}[/]")
        raise typer.Exit(2) from None


@app.command(name="doctor")
def doctor_cmd(
    paper_version: Annotated[
        str | None,
        typer.Option(
            "--paper-version",
            "-p",
            help="Check against this Paper version instead of the project's.",
        ),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Machine-readable output.")] = False,
    offline: Annotated[bool, typer.Option(help="Don't contact PaperMC.")] = False,
) -> None:
    """Check that every tool mcflow needs is installed, and say exactly how to fix what isn't."""
    ctx = _doctor_context(paper_version, offline)
    results = doctor.run_checks(SystemEnv(), ctx)
    if as_json:
        payload = [{**dataclasses.asdict(r), "status": r.status.value} for r in results]
        print(json.dumps(payload, indent=2))
    else:
        doctor.render(results, console)
    if any(r.status is doctor.Status.FAIL for r in results):
        raise typer.Exit(1)


def _not_yet(command: str, stage: str) -> None:
    err.print(f"`mcflow {command}` isn't available yet. It's planned for {stage}.", soft_wrap=True)
    raise typer.Exit(3)


@app.command()
def update() -> None:
    """Update skills, agents and the knowledge base without touching your project files."""
    _not_yet("update", "a later release (Stage 6)")


@kb_app.command("pull")
def kb_pull() -> None:
    """Merge approved entries from the shared knowledge base into knowledge/."""
    _not_yet("kb pull", "a later release (Stage 6)")


@kb_app.command("push")
def kb_push() -> None:
    """Open a pull request that shares your new knowledge entries."""
    _not_yet("kb push", "a later release (Stage 6)")
