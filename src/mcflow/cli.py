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
server_app = typer.Typer(help="Set up the local test server.", no_args_is_help=True)
app.add_typer(server_app, name="server")
client_app = typer.Typer(help="Install mcflow's client mod (required).", no_args_is_help=True)
app.add_typer(client_app, name="client")

console = Console(soft_wrap=True)
err = Console(stderr=True, soft_wrap=True)


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
    root = find_project_root(Path.cwd())
    requested = paper_version
    if requested is None and root is not None:
        requested = load(root).paper_version
    if requested is None:
        return doctor.DoctorContext(paper=None, project_root=root)
    versions, source = paper.available_versions(online=not offline)
    try:
        return doctor.DoctorContext(
            paper=paper.resolve(requested, versions), paper_source=source, project_root=root
        )
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


def _require_project() -> tuple[Path, ProjectConfig]:
    root = find_project_root(Path.cwd())
    if root is None:
        err.print(
            "[red]Not inside an mcflow workspace.[/] Run this from a folder made by `mcflow init`."
        )
        raise typer.Exit(1)
    return root, load(root)


@server_app.command("setup")
def server_setup(
    accept_eula: Annotated[
        bool,
        typer.Option(
            "--accept-eula",
            help="Record that the user accepted the Minecraft EULA (https://aka.ms/MinecraftEULA). "
            "Only pass this after the user has said yes.",
        ),
    ] = False,
) -> None:
    """Check the Paper jar, pick Java, and configure server/ for local-only testing."""
    from mcflow.testserver import setup

    root, config = _require_project()
    try:
        result = setup.run(root, config, accept_eula=accept_eula)
    except setup.SetupError as e:
        err.print(f"[red]{e}[/]")
        raise typer.Exit(1) from None

    s = result.settings
    console.print(f"[green]Test server ready[/] for Paper {result.jar.minecraft_version}.")
    console.print(f"  Paper jar:    server/{result.jar.path.name}")
    console.print(f"  Java:         {result.java_version} ({s.java})")
    console.print(f"  Address:      127.0.0.1:{s.server_port} (offline mode, local only)")
    console.print(f"  RCON:         127.0.0.1:{s.rcon_port}, password in .mcflow/local.toml")
    console.print(f"  Pack server:  http://127.0.0.1:{s.pack_port}/")
    console.print(f"  ViaVersion:   {pins()['viaversion']['version']} ({result.viaversion})")
    if result.viabackwards != "not needed":
        console.print(
            f"  ViaBackwards: {pins()['viabackwards']['version']} ({result.viabackwards})"
        )
    for note in result.notes:
        console.print(f"  [yellow]{note}[/]")
    if not result.eula_accepted:
        console.print(
            "\n[yellow]The server won't start until the Minecraft EULA is accepted.[/] "
            "Read https://aka.ms/MinecraftEULA, then rerun with --accept-eula."
        )


@client_app.command("install")
def client_install(
    path: Annotated[
        Path | None,
        typer.Argument(
            help="Minecraft folder or launcher instance (default: the official launcher's)."
        ),
    ] = None,
    jar: Annotated[
        Path | None, typer.Option(help="Install this locally built mod jar instead of the release.")
    ] = None,
) -> None:
    """Install mcflow's client mod, plus Fabric for the official launcher. Close Minecraft first."""
    from mcflow.client import install as client
    from mcflow.doctor import java

    root, config = _require_project()
    target = (path or client.default_game_dir()).expanduser().resolve()
    jdks = java.find_jdks(SystemEnv())
    java_exe = None
    if jdks:
        home = jdks[0].home
        java_exe = home / "bin" / ("java.exe" if SystemEnv().os_name == "windows" else "java")
    try:
        result = client.install(target, config.paper_version, java_exe, local_jar=jar)
    except client.InstallError as e:
        err.print(f"[red]{e}[/]")
        raise typer.Exit(1) from None
    client.save_state(root, result.layout, config.paper_version)

    console.print(f"[green]Installed[/] {result.mod_jar.name} into {result.mod_jar.parent}")
    console.print(f"  Launcher type: {result.layout.kind}")
    console.print(f"  Fabric Loader: {result.fabric}")
    console.print("\nTo finish:")
    for step in result.steps_for_user:
        console.print(f"  - {step}")
    console.print("  - Sign in with your Microsoft account in the launcher if it asks.")


def _not_yet(command: str, stage: str) -> None:
    err.print(f"`mcflow {command}` isn't available yet. It's planned for {stage}.")
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
