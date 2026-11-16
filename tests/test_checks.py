import pytest

from mcflow.doctor import checks
from mcflow.doctor.checks import DoctorContext, Status
from mcflow.paper import PaperVersion

PAPER_26_3 = PaperVersion("26.3", java_minimum=25, supported=True)
PAPER_1_21_11 = PaperVersion("1.21.11", java_minimum=21, supported=False)
PAPER_1_17 = PaperVersion("1.17", java_minimum=16, supported=False)


def ctx(paper=PAPER_26_3):
    return DoctorContext(paper=paper, paper_source="live")


# --- Paper version ---


def test_paper_supported_is_ok(fake_env):
    assert checks.check_paper_version(fake_env, ctx()).status is Status.OK


def test_paper_unsupported_by_papermc_is_only_a_warning(fake_env):
    result = checks.check_paper_version(fake_env, ctx(PAPER_1_21_11))
    assert result.status is Status.WARN
    assert "no longer ships fixes" in result.summary


def test_paper_outside_project_warns(fake_env):
    assert checks.check_paper_version(fake_env, DoctorContext(paper=None)).status is Status.WARN


def test_paper_mentions_offline_cache(fake_env):
    result = checks.check_paper_version(fake_env, DoctorContext(paper=PAPER_26_3))
    assert "cached" in result.summary


# --- Java ---


def test_java_ok_when_default_meets_minimum(fake_env):
    home = fake_env.add_jdk(fake_env.root / "jdk25", "25.0.2")
    fake_env.environ["JAVA_HOME"] = str(home)
    result = checks.check_java(fake_env, ctx())
    assert result.status is Status.OK
    assert "Java 25+" in result.summary


def test_java_warns_when_java_home_points_at_old_jdk(fake_env):
    old = fake_env.add_jdk(fake_env.root / "jdk23", "23.0.2")
    new = fake_env.add_jdk(fake_env.home / ".jdks" / "jdk25", "25.0.2")
    fake_env.environ["JAVA_HOME"] = str(old)
    result = checks.check_java(fake_env, ctx())
    assert result.status is Status.WARN
    assert "JAVA_HOME points to Java 23" in result.summary
    assert str(new) in result.fix


def test_java_warning_picks_lowest_suitable_jdk(fake_env):
    fake_env.add_jdk(fake_env.home / ".jdks" / "jdk25", "25.0.2")
    fake_env.add_jdk(fake_env.home / ".jdks" / "jdk21", "21.0.5")
    result = checks.check_java(fake_env, ctx(PAPER_1_21_11))
    assert result.status is Status.WARN
    assert "jdk21" in result.fix


def test_java_fails_with_install_command_for_recommended_lts(make_env):
    env = make_env("windows")
    env.add_jdk(env.home / ".jdks" / "jdk11", "11.0.2")
    result = checks.check_java(env, ctx(PAPER_1_17))
    assert result.status is Status.FAIL
    assert "winget install EclipseAdoptium.Temurin.17.JDK" in result.fix


@pytest.mark.parametrize(
    ("os_name", "expected"),
    [
        ("windows", "winget install EclipseAdoptium.Temurin.25.JDK"),
        ("macos", "brew install --cask temurin@25"),
        ("linux", "openjdk-25-jdk"),
    ],
)
def test_java_install_hint_per_os(make_env, os_name, expected):
    result = checks.check_java(make_env(os_name), ctx())
    assert result.status is Status.FAIL
    assert expected in result.fix


def test_java_outside_project_lists_jdks(fake_env):
    fake_env.add_jdk(fake_env.home / ".jdks" / "jdk21", "21.0.5")
    result = checks.check_java(fake_env, DoctorContext(paper=None))
    assert result.status is Status.WARN
    assert "21" in result.summary


# --- Node ---


@pytest.mark.parametrize(
    ("output", "status"),
    [
        ("v22.18.0\n", Status.OK),
        ("v22.0.0", Status.OK),
        ("v20.11.1", Status.FAIL),
        ("garbage", Status.FAIL),
    ],
)
def test_node_versions(fake_env, output, status):
    fake_env.programs[("node", "--version")] = (0, output)
    assert checks.check_node(fake_env, ctx()).status is status


def test_node_missing(fake_env):
    result = checks.check_node(fake_env, ctx())
    assert result.status is Status.FAIL and result.fix


# --- universal-ctags ---


def test_ctags_universal_ok(fake_env):
    fake_env.programs[("ctags", "--version")] = (
        0,
        "Universal Ctags 6.1.0, Copyright (C) 2015-2023 Universal Ctags Team\n",
    )
    assert checks.check_ctags(fake_env, ctx()).status is Status.OK


def test_ctags_exuberant_rejected(fake_env):
    fake_env.programs[("ctags", "--version")] = (
        0,
        "Exuberant Ctags 5.8, Copyright (C) 1996-2009 Darren Hiebert\n",
    )
    result = checks.check_ctags(fake_env, ctx())
    assert result.status is Status.FAIL
    assert "Exuberant" in result.summary


def test_ctags_bsd_ctags_rejected(fake_env):
    fake_env.programs[("ctags", "--version")] = (1, "ctags: illegal option -- -\n")
    assert checks.check_ctags(fake_env, ctx()).status is Status.FAIL


def test_ctags_missing_gives_brew_command_on_macos(make_env):
    result = checks.check_ctags(make_env("macos"), ctx())
    assert "brew install universal-ctags" in result.fix


# --- TokToken ---


def test_toktoken_pinned_version_ok(fake_env):
    fake_env.programs[("toktoken", "--version")] = (0, "toktoken 0.5.0\n")
    assert checks.check_toktoken(fake_env, ctx()).status is Status.OK


def test_toktoken_other_version_warns(fake_env):
    fake_env.programs[("toktoken", "--version")] = (0, "toktoken 0.6.1\n")
    assert checks.check_toktoken(fake_env, ctx()).status is Status.WARN


def test_toktoken_missing_points_at_official_release_with_checksum(make_env):
    result = checks.check_toktoken(make_env("windows"), ctx())
    assert result.status is Status.FAIL
    assert "releases/download/v0.5.0/toktoken-win-x86_64.exe" in result.fix
    assert "4c01fc57b41a99dde533076ebc0b43acdc894c9b246426715b2a8259a1d187ca" in result.fix
    assert "toktoken.exe" in result.fix


def test_toktoken_unsupported_platform_says_so(make_env):
    result = checks.check_toktoken(make_env("windows", machine="aarch64"), ctx())
    assert result.status is Status.FAIL
    assert "no build for windows-aarch64" in result.summary


# --- Claude Code, git, gh ---


def test_claude_ok(fake_env):
    fake_env.programs[("claude", "--version")] = (0, "2.1.157 (Claude Code)\n")
    assert checks.check_claude(fake_env, ctx()).summary == "2.1.157 (Claude Code)"


def test_claude_missing_gives_official_installer(make_env):
    assert "install.ps1" in checks.check_claude(make_env("windows"), ctx()).fix
    assert "install.sh" in checks.check_claude(make_env("linux"), ctx()).fix


def test_gh_not_signed_in_warns(fake_env):
    fake_env.programs[("gh", "auth", "status")] = (1, "You are not logged into any GitHub hosts.")
    result = checks.check_gh(fake_env, ctx())
    assert result.status is Status.WARN
    assert result.fix == "gh auth login"


def test_gh_missing_is_only_a_warning(fake_env):
    assert checks.check_gh(fake_env, ctx()).status is Status.WARN


def test_git_missing_fails(fake_env):
    assert checks.check_git(fake_env, ctx()).status is Status.FAIL


def test_every_failure_comes_with_a_fix(make_env):
    for os_name in ("windows", "macos", "linux"):
        env = make_env(os_name)
        for check in checks.ALL_CHECKS:
            result = check(env, ctx())
            if result.status is Status.FAIL:
                assert result.fix, f"{result.name} on {os_name} failed without a fix"


@pytest.mark.parametrize(
    ("os_name", "machine", "status", "text"),
    [
        ("windows", "x86_64", checks.Status.OK, "tested in CI"),
        ("macos", "aarch64", checks.Status.OK, "tested in CI"),
        ("linux", "aarch64", checks.Status.OK, "not tested in CI"),
        ("windows", "aarch64", checks.Status.WARN, "no code indexing"),
        ("linux", "riscv64", checks.Status.WARN, "no code indexing"),
    ],
)
def test_platform_check_names_the_limits(make_env, os_name, machine, status, text):
    result = checks.check_platform(make_env(os_name, machine), checks.DoctorContext(paper=None))
    assert result.status is status
    assert text in result.summary


def test_windows_arm_mentions_ctags_emulation():
    assert any("x64 emulation" in limit for limit in checks.platform_limits("windows", "aarch64"))
