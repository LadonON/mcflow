import os
import subprocess
from pathlib import Path

import pytest

from mcflow import humanize

REPORT = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="dev.mcflow.menu.MenuPluginTest" tests="3">
  <testcase name="menuOpens()" classname="dev.mcflow.menu.MenuPluginTest" time="0.1"/>
  <testcase name="sneakCloses()" classname="dev.mcflow.menu.MenuPluginTest" time="0.1">
    <failure message="expected SURVIVAL">trace</failure>
  </testcase>
  <testcase name="later()" classname="dev.mcflow.menu.MenuPluginTest" time="0"><skipped/></testcase>
</testsuite>
"""

JAVAP = """Compiled from "MenuPlugin.java"
public class dev.mcflow.menu.MenuPlugin extends org.bukkit.plugin.java.JavaPlugin {
  public dev.mcflow.menu.MenuPlugin();
  public void onEnable();
  public boolean onCommand(org.bukkit.command.CommandSender, String, String[]);
}
Compiled from "Glyphs.java"
final class dev.mcflow.menu.Glyphs {
}
"""


def test_parses_junit_reports(tmp_path):
    (tmp_path / "TEST-x.xml").write_text(REPORT, encoding="utf-8")
    assert humanize.parse_test_results(tmp_path) == {
        "dev.mcflow.menu.MenuPluginTest#menuOpens()": "passed",
        "dev.mcflow.menu.MenuPluginTest#sneakCloses()": "failed",
        "dev.mcflow.menu.MenuPluginTest#later()": "skipped",
    }


def test_parses_javap_public_output():
    api = humanize.parse_javap(JAVAP)
    cls = "public class dev.mcflow.menu.MenuPlugin extends org.bukkit.plugin.java.JavaPlugin"
    assert api[cls] == [
        "public boolean onCommand(org.bukkit.command.CommandSender, String, String[])",
        "public dev.mcflow.menu.MenuPlugin()",
        "public void onEnable()",
    ]
    assert api["final class dev.mcflow.menu.Glyphs"] == []


def snap(tests=None, api=None, build_ok=True):
    return humanize.Snapshot(
        tests=tests if tests is not None else {"A#a()": "passed", "A#b()": "failed"},
        api=api if api is not None else {"class A": ["public void a()"]},
        build_ok=build_ok,
    )


def test_identical_snapshots_are_unchanged():
    assert humanize.compare(snap(), snap()).ok


def test_a_broken_or_missing_test_fails():
    r = humanize.compare(snap(), snap(tests={"A#a()": "failed", "A#b()": "failed"}))
    assert not r.ok and r.broken_tests == ["A#a()"]
    r = humanize.compare(snap(), snap(tests={"A#b()": "failed"}))
    assert not r.ok and r.missing_tests == ["A#a()"]


def test_a_test_that_already_failed_may_stay_failing_and_new_tests_are_fine():
    r = humanize.compare(
        snap(), snap(tests={"A#a()": "passed", "A#b()": "failed", "A#c()": "passed"})
    )
    assert r.ok and r.new_tests == ["A#c()"]


def test_public_api_changes_fail():
    r = humanize.compare(snap(), snap(api={"class A": ["public void renamed()"]}))
    assert not r.ok
    assert r.api_changes == [
        "removed from class A: public void a()",
        "added to class A: public void renamed()",
    ]
    assert humanize.compare(snap(), snap(api={})).api_changes == ["removed: class A"]


def test_a_failed_build_fails():
    r = humanize.compare(snap(), snap(build_ok=False))
    assert not r.ok and r.broken_tests == ["(the build failed)"]


def fake_project(tmp_path: Path) -> Path:
    project = tmp_path / "menu"
    project.mkdir()
    (project / ("gradlew.bat" if os.name == "nt" else "gradlew")).write_text("", encoding="utf-8")
    return project


def fake_gradle(report: str, compile_ok: bool = True):
    """A runner standing in for Gradle and javap: writes a test report and compiled classes."""

    def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if "test" in cmd:
            if compile_ok:
                classes = cwd / "build" / "classes" / "java" / "main" / "dev"
                classes.mkdir(parents=True, exist_ok=True)
                (classes / "MenuPlugin.class").write_bytes(b"\xca\xfe\xba\xbe")
                (classes / "MenuPlugin$1.class").write_bytes(
                    b"\xca\xfe\xba\xbe"
                )  # anonymous: skipped
                results = cwd / "build" / "test-results" / "test"
                results.mkdir(parents=True, exist_ok=True)
                (results / "TEST-x.xml").write_text(report, encoding="utf-8")
            out = "" if compile_ok else "> Task :compileJava FAILED"
            return subprocess.CompletedProcess(cmd, 0 if compile_ok else 1, out, "")
        assert not any(arg.endswith("MenuPlugin$1.class") for arg in cmd)
        return subprocess.CompletedProcess(cmd, 0, JAVAP, "")

    return run


def test_snapshot_then_check_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(humanize.shutil, "which", lambda _: "javap")
    project = fake_project(tmp_path)
    before = humanize.take(project, run=fake_gradle(REPORT))
    assert (
        before.build_ok and before.tests["dev.mcflow.menu.MenuPluginTest#menuOpens()"] == "passed"
    )
    path = humanize.snapshot_path(tmp_path, "menu")
    humanize.save(path, before)
    loaded = humanize.load(path)
    assert humanize.compare(loaded, humanize.take(project, run=fake_gradle(REPORT))).ok

    broken = REPORT.replace('time="0.1"/>', 'time="0.1"><failure/></testcase>', 1)
    assert humanize.compare(
        loaded, humanize.take(project, run=fake_gradle(broken))
    ).broken_tests == ["dev.mcflow.menu.MenuPluginTest#menuOpens()"]


def test_compile_failure_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(humanize.shutil, "which", lambda _: "javap")
    snap_ = humanize.take(fake_project(tmp_path), run=fake_gradle(REPORT, compile_ok=False))
    assert not snap_.build_ok


def test_check_without_a_snapshot_says_what_to_do(tmp_path):
    with pytest.raises(humanize.HumanizeError, match="mcflow humanize snapshot"):
        humanize.load(tmp_path / "none.json")
