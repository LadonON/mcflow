"""A guard for the code-humanizer: proof that a cleanup didn't change what a plugin does.

`snapshot` builds the plugin, runs its tests, and records which tests passed and the public API
of its compiled classes (`javap -public`). `check` does the same after the cleanup and compares:
every test that passed must still pass, none may disappear, and no public class, method or field
may change. It can't prove two programs equivalent, but it catches what a cleanup most often
breaks: a renamed public member, a deleted test, a behaviour a test pins.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

Runner = Callable[[list[str], Path], subprocess.CompletedProcess[str]]


class HumanizeError(Exception):
    pass


@dataclass
class Snapshot:
    tests: dict[str, str]  # "Class#method" -> "passed" | "failed" | "skipped"
    api: dict[str, list[str]]  # class -> sorted public member signatures
    build_ok: bool = True


@dataclass
class Comparison:
    ok: bool
    broken_tests: list[str] = field(default_factory=list)
    missing_tests: list[str] = field(default_factory=list)
    api_changes: list[str] = field(default_factory=list)
    new_tests: list[str] = field(default_factory=list)


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


def parse_test_results(results_dir: Path) -> dict[str, str]:
    """JUnit XML reports (Gradle's build/test-results/test) -> {"Class#method": status}."""
    tests: dict[str, str] = {}
    for report in sorted(results_dir.glob("*.xml")):
        for case in ET.parse(report).getroot().iter("testcase"):
            name = f"{case.get('classname')}#{case.get('name')}"
            if case.find("failure") is not None or case.find("error") is not None:
                tests[name] = "failed"
            elif case.find("skipped") is not None:
                tests[name] = "skipped"
            else:
                tests[name] = "passed"
    return tests


def parse_javap(output: str) -> dict[str, list[str]]:
    """`javap -public` output -> {class: sorted member signatures}, skipping lambda classes."""
    api: dict[str, list[str]] = {}
    current: str | None = None
    for raw in output.splitlines():
        line = raw.strip()
        if not line or line.startswith("Compiled from"):
            continue
        if line.endswith("{") and (
            "class " in line or "interface " in line or "record " in line or "enum " in line
        ):
            current = line[:-1].strip()
            api[current] = []
        elif line == "}":
            current = None
        elif current is not None:
            api[current].append(line.rstrip(";"))
    return {cls: sorted(members) for cls, members in api.items() if "$$Lambda" not in cls}


def compare(before: Snapshot, after: Snapshot) -> Comparison:
    if not after.build_ok:
        return Comparison(ok=False, broken_tests=["(the build failed)"])
    broken = sorted(
        t
        for t, s in before.tests.items()
        if s == "passed" and after.tests.get(t) not in (None, "passed")
    )
    missing = sorted(t for t in before.tests if t not in after.tests)
    new = sorted(t for t in after.tests if t not in before.tests)
    changes: list[str] = []
    for cls in sorted(set(before.api) | set(after.api)):
        b, a = set(before.api.get(cls, [])), set(after.api.get(cls, []))
        if cls not in after.api:
            changes.append(f"removed: {cls}")
        elif cls not in before.api:
            changes.append(f"added: {cls}")
        else:
            changes += [f"removed from {cls}: {m}" for m in sorted(b - a)]
            changes += [f"added to {cls}: {m}" for m in sorted(a - b)]
    return Comparison(
        ok=not broken and not missing and not changes,
        broken_tests=broken,
        missing_tests=missing,
        api_changes=changes,
        new_tests=new,
    )


def _javap_for(java_home: Path | None) -> str:
    if java_home:
        candidate = java_home / "bin" / ("javap.exe" if os.name == "nt" else "javap")
        if candidate.is_file():
            return str(candidate)
    found = shutil.which("javap")
    if not found:
        raise HumanizeError("No javap found. Install a JDK, or set JAVA_HOME to one.")
    return found


def take(project_dir: Path, java_home: Path | None = None, run: Runner = _run) -> Snapshot:
    """Build and test with the Gradle wrapper; read the test results and the public API."""
    wrapper = project_dir / ("gradlew.bat" if os.name == "nt" else "gradlew")
    if not wrapper.is_file():
        raise HumanizeError(f"No Gradle wrapper in {project_dir}.")
    results = project_dir / "build" / "test-results" / "test"
    if results.is_dir():
        shutil.rmtree(results)  # stale reports would hide tests that no longer run
    build = run([str(wrapper), "test", "classes", "--console=plain"], project_dir)
    classes = project_dir / "build" / "classes" / "java" / "main"
    if not classes.is_dir():
        return Snapshot(tests={}, api={}, build_ok=False)
    files = sorted(
        str(p)
        for p in classes.rglob("*.class")
        if "$" not in p.name or not p.name.split("$")[-1][:1].isdigit()
    )
    api: dict[str, list[str]] = {}
    for i in range(0, len(files), 50):  # keep command lines short on Windows
        out = run([_javap_for(java_home), "-public", *files[i : i + 50]], project_dir)
        api.update(parse_javap(out.stdout))
    tests = parse_test_results(results) if results.is_dir() else {}
    # Failing tests also fail the Gradle run; only a compile failure leaves nothing to compare.
    compile_failed = "compileJava FAILED" in build.stdout + build.stderr
    return Snapshot(tests=tests, api=api, build_ok=not compile_failed)


def snapshot_path(root: Path, project: str) -> Path:
    return root / ".mcflow" / "humanize" / f"{project}.json"


def save(path: Path, snap: Snapshot) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(snap), indent=2, sort_keys=True), encoding="utf-8")


def load(path: Path) -> Snapshot:
    if not path.is_file():
        raise HumanizeError(
            "No snapshot yet. Run `mcflow humanize snapshot <project>` before the cleanup."
        )
    return Snapshot(**json.loads(path.read_text(encoding="utf-8")))
