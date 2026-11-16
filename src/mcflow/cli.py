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
humanize_app = typer.Typer(
    help="Prove a code cleanup changed no behaviour (tests and public API).", no_args_is_help=True
)
app.add_typer(humanize_app, name="humanize")
tools_app = typer.Typer(
    help="Install the indexing tools (TokToken, universal-ctags).", no_args_is_help=True
)
app.add_typer(tools_app, name="tools")

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


def _humanize_target(project: str) -> tuple[Path, Path, Path | None]:
    from mcflow.testserver import local

    root, _ = _require_project()
    project_dir = root / "plugins" / project
    if not project_dir.is_dir():
        err.print(f"[red]No plugin project at plugins/{project}/.[/]")
        raise typer.Exit(1)
    settings = local.load(root)
    java_home = Path(settings.java).parent.parent if settings else None
    return root, project_dir, java_home


@humanize_app.command("snapshot")
def humanize_snapshot(
    project: Annotated[str, typer.Argument(help="Folder name under plugins/")],
) -> None:
    """Before a cleanup: build, test, and record passing tests and the public API."""
    from mcflow import humanize

    root, project_dir, java_home = _humanize_target(project)
    try:
        snap = humanize.take(project_dir, java_home)
    except humanize.HumanizeError as e:
        err.print(f"[red]{e}[/]")
        raise typer.Exit(1) from None
    if not snap.build_ok:
        err.print("[red]The build fails, so there's nothing to compare against. Fix it first.[/]")
        raise typer.Exit(1)
    failing = [t for t, s in snap.tests.items() if s == "failed"]
    humanize.save(humanize.snapshot_path(root, project), snap)
    console.print(
        f"Snapshot saved: {sum(s == 'passed' for s in snap.tests.values())} passing tests, "
        f"{len(snap.api)} public classes."
    )
    if failing:
        console.print(f"[yellow]{len(failing)} tests already fail; they aren't held to passing.[/]")


@humanize_app.command("check")
def humanize_check(
    project: Annotated[str, typer.Argument(help="Folder name under plugins/")],
) -> None:
    """After a cleanup: rebuild, retest and compare with the snapshot. Exits 1 on a difference."""
    from mcflow import humanize

    root, project_dir, java_home = _humanize_target(project)
    try:
        before = humanize.load(humanize.snapshot_path(root, project))
        after = humanize.take(project_dir, java_home)
    except humanize.HumanizeError as e:
        err.print(f"[red]{e}[/]")
        raise typer.Exit(1) from None
    result = humanize.compare(before, after)
    for label, items in (
        ("Tests that passed before and don't now", result.broken_tests),
        ("Tests that no longer exist", result.missing_tests),
        ("Public API changes", result.api_changes),
    ):
        for item in items:
            console.print(f"[red]{label}:[/] {item}")
    if result.new_tests:
        console.print(f"{len(result.new_tests)} new tests (fine).")
    if not result.ok:
        raise typer.Exit(1)
    console.print("[green]Unchanged:[/] every test still passes and the public API is the same.")


@app.command()
def tags(
    paths: Annotated[
        list[str] | None,
        typer.Argument(help="Files or folders (default: resourcepacks/ and plugin resources)"),
    ] = None,
    query: Annotated[
        str | None,
        typer.Option("--query", "-q", help="Only symbols whose name or scope contains this"),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Machine-readable output")] = False,
) -> None:
    """Symbols in pack JSON, .mcmeta, GLSL shaders and YAML configs (files TokToken can't index)."""
    from mcflow import tags as tagmod

    root, _ = _require_project()
    try:
        found = tagmod.run(root, paths or [], query)
    except tagmod.TagsError as e:
        err.print(f"[red]{e}[/]")
        raise typer.Exit(1) from None
    if as_json:
        print(json.dumps([dataclasses.asdict(t) for t in found], indent=2))
        return
    for t in found:
        scope = f" in {t.scope}" if t.scope else ""
        console.print(f"{t.path}:{t.line}  [bold]{t.name}[/] ({t.kind}{scope})")
    console.print(f"{len(found)} symbols")


@tools_app.command("install")
def tools_install(
    directory: Annotated[
        Path | None, typer.Option("--dir", help="Where to put them (default: ~/.local/bin)")
    ] = None,
) -> None:
    """Download TokToken (and universal-ctags on Windows) from official releases, checked."""
    from mcflow import platforms, tools

    dest = directory or tools.default_dir()
    try:
        result = tools.install(dest, platforms.current_os(), platforms.current_machine())
    except (tools.ToolsError, OSError) as e:
        err.print(f"[red]{e}[/]")
        raise typer.Exit(1) from None
    for path in result.installed:
        console.print(f"[green]Installed[/] {path}")
    for item in result.skipped:
        console.print(f"Skipped {item}")
    for note in result.notes:
        console.print(f"[yellow]{note}[/]")


@app.command()
def update(
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show what would change; write nothing.")
    ] = False,
    take: Annotated[
        list[str] | None,
        typer.Option(
            "--take", help="Replace this file you edited with mcflow's new version (repeatable)."
        ),
    ] = None,
    kb: Annotated[
        bool, typer.Option("--kb/--no-kb", help="Also pull approved knowledge-base entries.")
    ] = True,
) -> None:
    """Update skills, agents and workflow files, then the knowledge base. Your files stay put.

    Files you've edited are never overwritten: the diff to the new version is shown instead.
    To get a newer mcflow first: pipx upgrade mcflow-cli
    """
    from mcflow import update as updater

    root, config = _require_project()
    result = updater.run(root, config, set(take or []), dry_run=dry_run)
    prefix = "Would " if dry_run else ""
    for label, items in (
        ("add", result.added),
        ("update", result.updated),
        ("replace (--take)", result.taken),
        ("remove (no longer shipped)", result.removed),
    ):
        for path in items:
            text = prefix + label if dry_run else label.capitalize()
            console.print(f"[green]{text}[/] {path}")
    for e in result.edited:
        console.print(
            f"\n[yellow]You've edited {e.path}; left as it is.[/] The new version differs:"
        )
        console.print(e.diff, markup=False, highlight=False)
        console.print(f"To take the new version: mcflow update --take {e.path}")
    for path in result.deleted_by_user:
        console.print(f"Left deleted: {path} (you removed it; --take {path} brings it back)")
    for path in result.kept_removed:
        console.print(f"[yellow]Kept {path}[/]: mcflow no longer ships it, but you've edited it.")
    console.print(
        f"\n{result.changes} change(s), {len(result.unchanged)} up to date, "
        f"{len(result.edited)} edited by you."
    )
    if kb and not dry_run:
        console.print("")
        kb_pull()


def _print_pull(result) -> None:
    for name in result.added:
        console.print(f"[green]Added[/] knowledge/{name}")
    for name in result.updated:
        console.print(f"[green]Updated[/] knowledge/{name}")
    for name in result.kept_local:
        console.print(f"Kept your edit: knowledge/{name} (share it with `mcflow kb push`)")
    for name, saved in result.conflicts:
        console.print(
            f"[yellow]Conflict:[/] knowledge/{name} changed here and in the shared repo. "
            f"Yours is untouched; the shared version is at {saved}. Merge them by hand."
        )
    for name in result.deleted_here:
        console.print(f"Left deleted: knowledge/{name} (you removed it)")
    for name in result.removed_upstream:
        console.print(f"[yellow]knowledge/{name} was removed from the shared repo[/]; kept here.")
    for name, errors in result.invalid_upstream:
        console.print(f"[red]Skipped invalid shared entry {name}:[/] {'; '.join(errors)}")
    console.print(
        f"{len(result.added)} added, {len(result.updated)} updated, "
        f"{len(result.conflicts)} conflicts, {len(result.unchanged)} already up to date."
    )


@kb_app.command("pull")
def kb_pull() -> None:
    """Merge approved entries from the shared knowledge base into knowledge/."""
    from mcflow.knowledge import sync

    root, config = _require_project()
    try:
        result = sync.pull(root, config.knowledge_repo)
    except sync.KbError as e:
        err.print(f"[red]Couldn't pull the knowledge base ({config.knowledge_repo}).[/] {e}")
        raise typer.Exit(1) from None
    _print_pull(result)
    if result.conflicts:
        raise typer.Exit(1)


@kb_app.command("push")
def kb_push(
    names: Annotated[
        list[str] | None,
        typer.Argument(help="Entries to share (default: every new or changed one)."),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes", help="Open the pull request without asking. Only after the user has said yes."
        ),
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="List what would be proposed; open nothing.")
    ] = False,
) -> None:
    """Open a pull request that shares your new knowledge entries. Never pushes directly."""
    from mcflow.knowledge import sync

    root, config = _require_project()
    url, slug = sync.resolve_remote(config.knowledge_repo)
    if slug is None:
        err.print(f"[red]kb push needs a GitHub repo (owner/name); mcflow.toml has {url}.[/]")
        raise typer.Exit(1)

    def confirm(plan: sync.PushPlan) -> bool:
        for name in plan.new:
            console.print(f"  new      knowledge/{name}")
        for name in plan.changed:
            console.print(f"  updated  knowledge/{name}")
        if dry_run:
            return False
        return yes or typer.confirm(f"Open a pull request on {slug} with these entries?")

    try:
        result = sync.push(root, url, slug, config.name, names or None, confirm=confirm)
    except sync.KbError as e:
        err.print(f"[red]{e}[/]")
        raise typer.Exit(1) from None
    plan = result.plan
    for name in plan.already_proposed:
        console.print(f"Already in an open pull request: knowledge/{name}")
    for name in plan.behind:
        console.print(
            f"[yellow]knowledge/{name} is older than the shared copy.[/] Run `mcflow kb pull`."
        )
    if result.url:
        console.print(f"[green]Pull request opened:[/] {result.url}")
        console.print("A reviewer merges it; then `mcflow kb pull` on every install picks it up.")
    elif not plan.to_send:
        console.print("Nothing new to share.")
    elif dry_run:
        console.print("Dry run: nothing was sent.")
    else:
        console.print("Cancelled: nothing was sent.")


@kb_app.command("validate")
def kb_validate(
    paths: Annotated[
        list[Path] | None, typer.Argument(help="Entry files or folders (default: knowledge/).")
    ] = None,
) -> None:
    """Check each entry's frontmatter (title, versions, proof, sources, date). Exits 1 on errors."""
    from mcflow.knowledge import entry

    if not paths:
        root, _ = _require_project()
        paths = [root / "knowledge"]
    raise typer.Exit(entry.main([str(p) for p in paths]))


@kb_app.command("list")
def kb_list(
    pack_format: Annotated[
        int | None,
        typer.Option(help="This version's resource-pack format, read from the server jar."),
    ] = None,
    version: Annotated[
        str | None,
        typer.Option(help="Match against this Minecraft version instead of the project's."),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Machine-readable output")] = False,
) -> None:
    """List entries and whether each one applies to this project's version and pack format."""
    from mcflow.knowledge import entry

    root, config = _require_project()
    target = version or config.paper_version
    rows = []
    for path in entry.entry_files(root / "knowledge"):
        e = entry.load(path)
        m = entry.applies(e, target, pack_format)
        rows.append({"file": path.name, "title": e.title, "applies": m.applies, "reason": m.reason})
    if as_json:
        print(json.dumps(rows, indent=2))
        return
    for r in rows:
        mark = "[green]applies[/]" if r["applies"] else "[yellow]lead only[/]"
        console.print(f"{mark}  {r['file']}  {r['title']} ({r['reason']})")
    console.print(f"{sum(r['applies'] for r in rows)} of {len(rows)} entries apply to {target}.")
