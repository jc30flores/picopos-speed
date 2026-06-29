#!/usr/bin/env python3
"""Static checks for the native Windows packaging workflow.

The script intentionally avoids reading real .env files. It validates only
repository metadata, examples, templates, and generated release payloads when
they exist locally.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
NATIVE = REPO / "deploy" / "windows-native"
WORKFLOW = REPO / ".github" / "workflows" / "windows-native-installer.yml"


def fail(message: str) -> None:
    raise AssertionError(message)


def git_ls_files(*paths: str) -> list[Path]:
    try:
        output = subprocess.check_output(
            ["git", "ls-files", *paths],
            cwd=REPO,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        files: list[Path] = []
        for root in paths:
            base = REPO / root
            if base.is_file():
                files.append(base.relative_to(REPO))
            elif base.exists():
                files.extend(p.relative_to(REPO) for p in base.rglob("*") if p.is_file())
        return files
    return [Path(line) for line in output.splitlines() if line.strip()]


def read_text_safe(path: Path) -> str:
    if path.name in {".env", ".env.windows", ".env.docker"}:
        fail(f"Refusing to read real env file: {path}")
    return path.read_text(encoding="utf-8")


def validate_yaml() -> None:
    try:
        import yaml  # type: ignore
    except Exception as exc:
        fail(f"PyYAML unavailable; cannot parse workflow YAML: {exc}")
    with WORKFLOW.open(encoding="utf-8") as fh:
        yaml.safe_load(fh)
    print(f"yaml parsed {WORKFLOW.relative_to(REPO)}")


def validate_json_examples() -> None:
    for path in [
        NATIVE / "vendor" / "runtime-manifest.example.json",
        NATIVE / "manifest.example.json",
    ]:
        json.loads(path.read_text(encoding="utf-8"))
        print(f"json parsed {path.relative_to(REPO)}")

    real_manifest = NATIVE / "vendor" / "runtime-manifest.json"
    if real_manifest.exists():
        json.loads(real_manifest.read_text(encoding="utf-8"))
        print(f"json parsed {real_manifest.relative_to(REPO)}")


def validate_inno_setup_script() -> None:
    path = NATIVE / "installer" / "PicoDeGallo.iss"
    content = path.read_text(encoding="utf-8")
    if r"\"" in content:
        fail(f"{path.relative_to(REPO)} uses backslash-escaped quotes; Inno Setup requires doubled quotes")
    print(f"inno script linted {path.relative_to(REPO)}")


def validate_xml_templates() -> None:
    for path in sorted((NATIVE / "service-templates").glob("*.xml")):
        ET.parse(path)
        print(f"xml parsed {path.relative_to(REPO)}")


def validate_no_versioned_native_binaries() -> None:
    forbidden_suffixes = {".exe", ".dll", ".msi", ".zip"}
    offenders = [
        p for p in git_ls_files("deploy/windows-native", ".github")
        if p.suffix.lower() in forbidden_suffixes
    ]
    if offenders:
        fail("versioned native binary found: " + ", ".join(str(p) for p in offenders[:10]))
    print("no versioned native binaries")


def validate_no_real_env_in_native_scope() -> None:
    offenders = []
    for path in git_ls_files("deploy/windows-native", ".github"):
        if path.name in {".env", ".env.windows", ".env.docker"}:
            offenders.append(path)
    if offenders:
        fail("real env file in native scope: " + ", ".join(str(p) for p in offenders))
    print("no real env files in native scope")


def validate_no_versioned_node_dirs_in_native_scope() -> None:
    node_dir = "node" + "_modules"
    offenders = [p for p in git_ls_files("deploy/windows-native", ".github") if node_dir in p.parts]
    if offenders:
        fail("versioned frontend dependency directory in native scope: " + ", ".join(str(p) for p in offenders[:10]))
    print("no versioned frontend dependency directories in native scope")


def validate_dte_examples() -> None:
    env_example = NATIVE / ".env.windows.example"
    text = read_text_safe(env_example)
    for name in ["DTE_BASE_URL", "DTE_API_TOKEN"]:
        match = re.search(rf"(?m)^{name}=(.*)$", text)
        if not match:
            fail(f"{name} missing from {env_example.relative_to(REPO)}")
        value = match.group(1).strip()
        if not value:
            fail(f"{name} is empty in {env_example.relative_to(REPO)}")
        if value.lower() in {"false", "disabled"}:
            fail(f"{name} has unsafe value in {env_example.relative_to(REPO)}")
    if "DTE_BACKGROUND_MODE=external" not in text:
        fail("DTE_BACKGROUND_MODE=external missing from .env.windows.example")
    print("DTE example placeholders are non-empty and external")


def should_scan_text(path: Path) -> bool:
    parts = set(path.parts)
    if path.name in {".env", ".env.windows", ".env.docker"}:
        return False
    if {"media", "venv", "__pycache__", "release", "runtime-cache"} & parts:
        return False
    if path.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pyc", ".pyo", ".exe", ".dll", ".zip"}:
        return False
    return path.suffix.lower() in {
        ".py",
        ".ps1",
        ".xml",
        ".json",
        ".yml",
        ".yaml",
        ".md",
        ".txt",
        ".example",
        ".template",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".css",
        ".html",
    } or path.name.startswith("Caddyfile")


def validate_forbidden_references() -> None:
    patterns = [
        re.compile(r"cliente debe clonar", re.I),
        re.compile(r"git clone.*cliente", re.I),
        re.compile(r"Docker Desktop es obligatorio", re.I),
        re.compile(r"requiere Docker Desktop para clientes", re.I),
        re.compile(r"APP_OPERATING_MODE"),
        re.compile(r"modo interno", re.I),
        re.compile(r"POS interno", re.I),
        re.compile(r"Ticket interno", re.I),
        re.compile(r"Comprobante interno", re.I),
        re.compile(r"DTE_ENABLED=false", re.I),
    ]
    roots = ["deploy", "docs", "backend", "frontend", ".github"]
    offenders: list[str] = []
    for rel in git_ls_files(*roots):
        path = REPO / rel
        if not should_scan_text(rel):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in patterns:
            if pattern.search(text):
                offenders.append(f"{rel}: {pattern.pattern}")
    if offenders:
        fail("forbidden references found: " + "; ".join(offenders[:20]))
    print("no forbidden native/DTE references")


def validate_local_release_if_present() -> None:
    release = REPO / "release" / "windows-native"
    if not release.exists():
        print("release/windows-native absent; local release payload check skipped")
        return

    node_dir = "node" + "_modules"
    pg_admin = "pg" + "Admin"
    yarn_state = ".yarn" + "-state.yml"
    forbidden_dirs = {node_dir, pg_admin, "StackBuilder", ".git", ".github"}
    for path in release.rglob("*"):
        if path.is_dir() and path.name in forbidden_dirs:
            fail(f"forbidden directory in local release: {path.relative_to(REPO)}")
        if path.is_file() and (path.name == yarn_state or node_dir in path.parts):
            fail(f"forbidden file in local release: {path.relative_to(REPO)}")
    print("local release payload safety subset OK")


def main() -> int:
    checks = [
        validate_yaml,
        validate_json_examples,
        validate_inno_setup_script,
        validate_xml_templates,
        validate_no_versioned_native_binaries,
        validate_no_real_env_in_native_scope,
        validate_no_versioned_node_dirs_in_native_scope,
        validate_dte_examples,
        validate_forbidden_references,
        validate_local_release_if_present,
    ]
    for check in checks:
        check()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
