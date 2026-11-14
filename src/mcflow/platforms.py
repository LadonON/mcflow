"""Normalised OS and CPU names, so pins and fix-it messages can be keyed consistently."""

import platform
import sys

OS_NAMES = ("windows", "macos", "linux")


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
