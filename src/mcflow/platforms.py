"""Normalised OS and CPU names, so pins and fix-it messages can be keyed consistently."""

import platform
import sys

OS_NAMES = ("windows", "macos", "linux")
# The runners GitHub Actions CI tests on (macos-latest is Apple Silicon). Keep in step with ci.yml.
CI_TESTED = {"windows-x86_64", "macos-aarch64", "linux-x86_64"}
LABELS = {"windows": "Windows", "macos": "macOS", "linux": "Linux"}


def current_os() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def current_machine() -> str:
    machine = platform.machine().lower()
    return {
        "amd64": "x86_64",
        "x64": "x86_64",
        "arm64": "aarch64",
        "armv7l": "armv7",
    }.get(machine, machine)
