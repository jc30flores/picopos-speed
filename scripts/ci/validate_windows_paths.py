#!/usr/bin/env python3
"""Fail when tracked git paths cannot be checked out on Windows."""

from __future__ import annotations

import subprocess
import sys


WINDOWS_INVALID_CHARS = set('<>:"|?*')
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
GITHUB_ACCIDENTAL_FILES = {
    ":GITHUB_OUTPUT",
    ":GITHUB_ENV",
    ":GITHUB_PATH",
    ":GITHUB_STEP_SUMMARY",
}


def git_ls_files() -> list[str]:
    output = subprocess.check_output(["git", "ls-files", "-z"], text=False)
    return [item.decode("utf-8", errors="replace") for item in output.split(b"\0") if item]


def windows_path_errors(path: str) -> list[str]:
    errors: list[str] = []
    for part in path.replace("\\", "/").split("/"):
        if not part:
            continue
        if part in GITHUB_ACCIDENTAL_FILES:
            errors.append("accidental GitHub env/output file")
        if any(char in WINDOWS_INVALID_CHARS for char in part):
            errors.append("invalid Windows character")
        if part.endswith(" ") or part.endswith("."):
            errors.append("trailing space/dot")
        if part.split(".")[0].upper() in WINDOWS_RESERVED_NAMES:
            errors.append("reserved Windows device name")
    return sorted(set(errors))


def main() -> int:
    offenders = []
    for path in git_ls_files():
        errors = windows_path_errors(path)
        if errors:
            offenders.append(f"{path} ({', '.join(errors)})")

    if offenders:
        print("Windows-incompatible git paths found:", file=sys.stderr)
        for offender in offenders:
            print(f"  - {offender}", file=sys.stderr)
        return 1

    print("git paths are Windows-safe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
