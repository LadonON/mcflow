import json
from pathlib import Path

import pytest

from mcflow.doctor.env import SystemEnv

FIXTURES = Path(__file__).parent / "fixtures"


class FakeEnv(SystemEnv):
    """A machine made of a temp folder plus scripted command output.

    `programs` maps a command's argv (as a tuple) to (exit code, output); a program is "on PATH"
    when any argv starting with its name is listed. Filesystem reads outside the temp folder see
    nothing, so a developer's real JDKs never leak into tests.
    """

    def __init__(self, root: Path, os_name: str = "linux", machine: str = "x86_64"):
        self.root = root
        self.os_name = os_name
        self.machine = machine
        self.home = root / "home"
        self.environ: dict[str, str] = {"ProgramFiles": str(root / "pf")}
        self.programs: dict[tuple[str, ...], tuple[int, str]] = {}

    def which(self, name: str) -> str | None:
        return f"/fake/bin/{name}" if any(argv[0] == name for argv in self.programs) else None

    def run(self, args: list[str], timeout: float = 20) -> tuple[int, str]:
        return self.programs.get(tuple(args), (127, ""))

    def _inside(self, path: Path) -> bool:
        return path.is_relative_to(self.root)

    def read_text(self, path: Path) -> str | None:
        return super().read_text(path) if self._inside(path) else None

    def subdirs(self, path: Path) -> list[Path]:
        return super().subdirs(path) if self._inside(path) else []

    def add_jdk(self, home: Path, version: str) -> Path:
        home.mkdir(parents=True, exist_ok=True)
        (home / "release").write_text(f'IMPLEMENTOR="Test"\nJAVA_VERSION="{version}"\n')
        return home

    def put_java_on_path(self, home: Path) -> None:
        self.programs[("java", "-XshowSettings:properties", "-version")] = (
            0,
            f"Property settings:\n    java.home = {home}\n    java.vendor = Test\n",
        )


@pytest.fixture
def fake_env(tmp_path: Path) -> FakeEnv:
    return FakeEnv(tmp_path)


@pytest.fixture
def make_env(tmp_path: Path):
    def make(os_name: str = "linux", machine: str = "x86_64") -> FakeEnv:
        return FakeEnv(tmp_path, os_name=os_name, machine=machine)

    return make


@pytest.fixture
def fill_response() -> dict:
    return json.loads((FIXTURES / "fill_versions.json").read_text(encoding="utf-8"))
