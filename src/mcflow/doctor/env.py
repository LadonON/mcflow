"""The slice of the operating system that doctor checks look at.

Checks only touch the system through this class, so tests can swap in a fake.
"""

import os
import shutil
import subprocess
from pathlib import Path

from mcflow.platforms import current_machine, current_os


class SystemEnv:
    def __init__(self) -> None:
        self.os_name = current_os()
        self.machine = current_machine()
        self.environ = dict(os.environ)
        self.home = Path.home()

    def which(self, name: str) -> str | None:
        return shutil.which(name)

    def run(self, args: list[str], timeout: float = 20) -> tuple[int, str]:
        """Run a command and return (exit code, stdout+stderr). Missing programs return 127."""
        try:
            done = subprocess.run(
                args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except FileNotFoundError:
            return 127, ""
        except subprocess.TimeoutExpired:
            return 124, f"timed out after {timeout}s"
        return done.returncode, (done.stdout or "") + (done.stderr or "")

    def read_text(self, path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    def subdirs(self, path: Path) -> list[Path]:
        try:
            return sorted(p for p in path.iterdir() if p.is_dir())
        except OSError:
            return []
