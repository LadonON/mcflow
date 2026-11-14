import pytest

from mcflow.doctor import java


@pytest.mark.parametrize(
    ("version", "major"),
    [("25.0.2", 25), ("21", 21), ("17.0.13+11", 17), ("1.8.0_382", 8), ("16.0.2", 16)],
)
def test_java_major(version, major):
    assert java.java_major(version) == major


def test_finds_scanned_jdks_on_linux(fake_env):
    fake_env.add_jdk(fake_env.home / ".sdkman" / "candidates" / "java" / "21.0.5-tem", "21.0.5")
    fake_env.add_jdk(fake_env.home / ".jdks" / "temurin-17", "17.0.13")
    found = java.find_jdks(fake_env)
    assert [j.major for j in found] == [21, 17]
    assert all(j.origins == ["scan"] for j in found)


def test_finds_windows_machine_and_per_user_installs(make_env, tmp_path):
    env = make_env("windows")
    env.environ["LOCALAPPDATA"] = str(tmp_path / "local")
    env.add_jdk(tmp_path / "pf" / "Java" / "jdk-25.0.2", "25.0.2")
    env.add_jdk(tmp_path / "local" / "Programs" / "Eclipse Adoptium" / "jdk-23.0.2.7", "23.0.2")
    assert sorted(j.major for j in java.find_jdks(env)) == [23, 25]


def test_reads_macos_bundle_home(make_env):
    env = make_env("macos")
    bundle = env.home / "Library" / "Java" / "JavaVirtualMachines" / "temurin-21.jdk"
    env.add_jdk(bundle / "Contents" / "Home", "21.0.5")
    (found,) = java.find_jdks(env)
    assert found.home == bundle / "Contents" / "Home"


def test_merges_origins_for_the_same_jdk(fake_env):
    home = fake_env.add_jdk(fake_env.home / ".jdks" / "jdk-21", "21.0.5")
    fake_env.environ["JAVA_HOME"] = str(home)
    fake_env.put_java_on_path(home)
    (found,) = java.find_jdks(fake_env)
    assert found.origins == ["JAVA_HOME", "PATH", "scan"]


def test_active_jdk_prefers_java_home_over_path(fake_env):
    old = fake_env.add_jdk(fake_env.root / "old", "17.0.1")
    new = fake_env.add_jdk(fake_env.root / "new", "25.0.2")
    fake_env.environ["JAVA_HOME"] = str(old)
    fake_env.put_java_on_path(new)
    assert java.active_jdk(java.find_jdks(fake_env)).major == 17


def test_ignores_folders_without_a_release_file(fake_env):
    (fake_env.home / ".jdks" / "not-a-jdk").mkdir(parents=True)
    assert java.find_jdks(fake_env) == []
