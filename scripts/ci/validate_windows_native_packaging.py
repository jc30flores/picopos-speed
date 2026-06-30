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
WINDOWS_INVALID_CHARS = set('<>:"|?*')
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


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


def windows_path_errors(path: Path) -> list[str]:
    errors: list[str] = []
    for part in str(path).replace("\\", "/").split("/"):
        if not part:
            continue
        if any(char in WINDOWS_INVALID_CHARS for char in part):
            errors.append("invalid character")
        if part.endswith(" ") or part.endswith("."):
            errors.append("trailing space/dot")
        if part.split(".")[0].upper() in WINDOWS_RESERVED_NAMES:
            errors.append("reserved device name")
    return sorted(set(errors))


def validate_windows_safe_git_paths() -> None:
    offenders = []
    for path in git_ls_files():
        errors = windows_path_errors(path)
        if errors:
            offenders.append(f"{path} ({', '.join(errors)})")
    if offenders:
        fail("Windows-incompatible git paths found: " + "; ".join(offenders[:50]))
    print("git paths are Windows-safe")


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
    if "DTE_MONITOR_ENABLED=true" not in text:
        fail("DTE_MONITOR_ENABLED=true missing from .env.windows.example")
    if "DTE_OUTBOX_WORKER_ENABLED=true" not in text:
        fail("DTE_OUTBOX_WORKER_ENABLED=true missing from .env.windows.example")
    for name, expected in {
        "PICO_BOOTSTRAP_ADMIN_ENABLED": "true",
        "PICO_BOOTSTRAP_ADMIN_USERNAME": "admin",
        "PICO_BOOTSTRAP_ADMIN_PASSWORD": "000000",
    }.items():
        match = re.search(rf"(?m)^{name}=(.*)$", text)
        if not match or match.group(1).strip() != expected:
            fail(f"{name}={expected} missing from .env.windows.example")
    print("DTE example placeholders are non-empty and external")


def validate_native_installer_contract() -> None:
    required_scripts = [
        NATIVE / "scripts" / "open-kiosk.ps1",
        NATIVE / "scripts" / "install-services.ps1",
        NATIVE / "scripts" / "status.ps1",
    ]
    for path in required_scripts:
        if not path.exists():
            fail(f"required native script missing: {path.relative_to(REPO)}")

    common = read_text_safe(NATIVE / "scripts" / "common.ps1")
    if "New-Object byte[] $Bytes" in common:
        fail("common.ps1 still uses New-Object byte[] for New-RandomSecret")
    if "[byte[]]::new($Bytes)" not in common:
        fail("common.ps1 does not use [byte[]]::new($Bytes) in New-RandomSecret")

    install = read_text_safe(NATIVE / "scripts" / "install-services.ps1")
    if "Servicio previsto" in install:
        fail("install-services.ps1 still contains placeholder service logic")
    for token in [
        "winsw.exe",
        'Command "install"',
        "Start-WinSWService",
        "Wait-TcpPort",
        "POSTGRES_DATA_DIR",
        "migrate",
        "collectstatic",
        "bootstrap_initial_admin",
        "/api/health/live/",
        "/api/health/ready/",
        "postgres-foreground-test",
        "POSTGRES_FOREGROUND_STDERR_TAIL",
        "postgres.exe --version",
        "initdb.exe --version",
        "psql.exe --version",
    ]:
        if token not in install:
            fail(f"install-services.ps1 missing required token: {token}")
    if "postgres.exe" not in install:
        fail("install-services.ps1 must reference postgres.exe")
    if "stderr" not in install.lower():
        fail("install-services.ps1 must capture/read stderr for PostgreSQL diagnostics")
    for token in [
        "Invoke-InstallStep",
        "Write-InstallException",
        "INSTALL_SERVICES_FAILED",
        "install-services-error.log",
        "STEP_BEGIN",
        "STEP_SUCCESS",
        "STEP_ERROR",
    ]:
        if token not in install:
            fail(f"install-services.ps1 missing top-level logging token: {token}")
    if not re.search(r"try\s*\{[\s\S]*Invoke-InstallMain[\s\S]*\}\s*catch\s*\{", install):
        fail("install-services.ps1 must wrap Invoke-InstallMain in a top-level try/catch")
    for token in [
        "PicoDeGalloSvc",
        "New-SecureRandomPassword",
        "Ensure-PicoServiceAccount",
        "Grant-PicoServiceAccountPermissions",
        "Invoke-AsPicoServiceAccount",
        "Install-WinSWServiceWithAccount",
        "S-1-5-32-544",
        "S-1-5-32-545",
        "Get-LocalizedBuiltinGroupNameBySid",
    ]:
        if token not in install:
            fail(f"install-services.ps1 missing PostgreSQL service-account token: {token}")
    for forbidden in ["Admin" + "istrators", "Us" + "ers"]:
        if forbidden in install:
            fail(f"install-services.ps1 must not depend on English builtin group name: {forbidden}")
    if not re.search(r"Start-Process\s+@startParams", install) or "Credential = $Credential" not in install:
        fail("install-services.ps1 must start PostgreSQL commands with a PSCredential")
    invoke_start = install.find("function Invoke-AsPicoServiceAccount")
    invoke_end = install.find("function Escape-XmlText", invoke_start)
    if invoke_start < 0 or invoke_end < 0:
        fail("install-services.ps1 missing Invoke-AsPicoServiceAccount body")
    invoke_body = install[invoke_start:invoke_end]
    for token in [
        ".exitcode",
        "EXIT_CODE_SENTINEL",
        "RUN_AS_BEGIN",
        "RUN_AS_DONE",
        "RUN_AS_ERROR",
        "Set-Content -LiteralPath `$exitCodePath",
    ]:
        if token not in invoke_body:
            fail(f"Invoke-AsPicoServiceAccount missing robust exit-code sentinel token: {token}")
    if "$process.ExitCode" in invoke_body:
        fail("Invoke-AsPicoServiceAccount must not depend on Start-Process -Credential process.ExitCode")
    for token in ["PasswordNeverExpires", "PasswordExpires=False", "PICO_SERVICE_ACCOUNT_PASSWORD_NEVER_EXPIRES_OK"]:
        if token not in install:
            fail(f"install-services.ps1 missing service account password-expiry guard: {token}")
    description_match = re.search(r'\$description\s*=\s*"([^"]+)"', install)
    if not description_match:
        fail("install-services.ps1 must set PicoDeGalloSvc description explicitly")
    if len(description_match.group(1)) > 48:
        fail("PicoDeGalloSvc description must be 48 characters or shorter")
    for token in ["PG_VERSION", "postgresql.conf", "pg_hba.conf", "Test-PostgresDataDirectoryInitialized"]:
        if token not in install:
            fail(f"install-services.ps1 missing PostgreSQL data-dir idempotency guard: {token}")
    for token in ["SERVICE_FILES_READY", "Assert-WinSWServiceFilesForAll", "CADDYFILE_RENDERED"]:
        if token not in install:
            fail(f"install-services.ps1 missing service/Caddyfile readiness marker: {token}")
    if "POSTGRES_FOREGROUND_TEST_RUN_AS" not in install:
        fail("install-services.ps1 must log the foreground PostgreSQL account")
    if re.search(r"PICO_SERVICE_ACCOUNT_PASSWORD\s*=\s*[^{}\s][^\r\n]*", install):
        fail("install-services.ps1 contains a literal PICO service account password assignment")
    for token in [
        'Join-Path $serviceDir "$ServiceId.exe"',
        'Join-Path $serviceDir "$ServiceId.xml"',
        "Copy-Item -LiteralPath $winswSource -Destination $targetExe",
        "Render-Template -Source $template -Destination $targetXml",
        "Assert-WinSWServiceFiles",
        'Command "install"',
        "No se genero Caddyfile final",
        "Caddyfile final contiene placeholders",
    ]:
        if token not in install:
            fail(f"install-services.ps1 missing service rendering/install guard: {token}")

    status = read_text_safe(NATIVE / "scripts" / "status.ps1")
    for token in ["VERSION=", "PICO_SERVICE_ACCOUNT=", "PasswordExpires", "POSTGRES_DATA=", "SERVICE_FILES=", "CADDYFILE=", "RUNAS_LAST_EXITCODE=", "StartName=", "POSTGRES_XML_SERVICEACCOUNT"]:
        if token not in status:
            fail(f"status.ps1 missing diagnostic token: {token}")

    diagnostics = read_text_safe(NATIVE / "scripts" / "diagnostics.ps1")
    for token in ["service-account.txt", "PasswordExpires", "postgres-data.txt", "service-files.txt", "caddyfile.txt", "runas-files.txt", "runas-last-exitcode.txt", "service-xml-", "acls.txt", "install-services-error.log"]:
        if token == "install-services-error.log":
            if token not in install and token not in diagnostics:
                fail(f"diagnostics coverage missing token: {token}")
            continue
        if token not in diagnostics:
            fail(f"diagnostics.ps1 missing diagnostic token: {token}")

    package = read_text_safe(NATIVE / "package-release.ps1")
    for token in ["postgres.exe --version", "initdb.exe --version", "psql.exe --version"]:
        if token not in package:
            fail(f"package-release.ps1 missing PostgreSQL runtime validation token: {token}")

    inno = read_text_safe(NATIVE / "installer" / "PicoDeGallo.iss")
    for token in ["install-services.ps1", "open-kiosk.ps1", "{autodesktop}\\Pico de Gallo.url", "InternetShortcut", "ExecOrFail"]:
        if token not in inno:
            fail(f"PicoDeGallo.iss missing required token: {token}")
    if re.search(r'(?im)^Name:\s*"\{autodesktop\}\\Pico de Gallo";\s*Filename:\s*"powershell\.exe"', inno):
        fail("desktop shortcut opens visible PowerShell instead of a browser URL")

    for path in sorted((NATIVE / "service-templates").glob("*.xml")):
        text = read_text_safe(path)
        if "runserver" in text:
            fail(f"service template uses runserver: {path.relative_to(REPO)}")
    backend_template = read_text_safe(NATIVE / "service-templates" / "PicoDeGallo-Backend.xml")
    if "-m waitress --listen=127.0.0.1:8000 config.wsgi:application" not in backend_template:
        fail("backend service template does not use python -m waitress")
    postgres_template = read_text_safe(NATIVE / "service-templates" / "PicoDeGallo-PostgreSQL.xml")
    if "pg_ctl" in postgres_template or "runservice" in postgres_template:
        fail("PostgreSQL service template must not use pg_ctl runservice under WinSW")
    if "postgres.exe" not in postgres_template:
        fail("PostgreSQL service template must execute postgres.exe directly")
    if "{{POSTGRES_DATA_DIR}}" not in postgres_template:
        fail("PostgreSQL service template must use POSTGRES_DATA_DIR")
    if "<serviceaccount>" not in postgres_template and "PICO_SERVICE_ACCOUNT_XML" not in postgres_template:
        fail("PostgreSQL service template must include a WinSW serviceaccount block or placeholder")
    if "<autoRefresh>false</autoRefresh>" not in postgres_template:
        fail("PostgreSQL service template must disable WinSW autoRefresh for password-free final XML")
    if re.search(r"(?i)LocalSystem|NT AUTHORITY\\SYSTEM", postgres_template):
        fail("PostgreSQL service template must not force LocalSystem/SYSTEM")
    if re.search(r"PICO_SERVICE_ACCOUNT_PASSWORD\s*=\s*[^{}\s][^\r\n]*", postgres_template):
        fail("PostgreSQL service template contains a literal service account password")

    print("native installer contract OK")


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
        re.compile("APP_" + "OPERATING_MODE"),
        re.compile("modo " + "interno", re.I),
        re.compile("POS " + "interno", re.I),
        re.compile("Ticket " + "interno", re.I),
        re.compile("Comprobante " + "interno", re.I),
        re.compile("DTE_" + "ENABLED=false", re.I),
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
        validate_windows_safe_git_paths,
        validate_yaml,
        validate_json_examples,
        validate_inno_setup_script,
        validate_xml_templates,
        validate_no_versioned_native_binaries,
        validate_no_real_env_in_native_scope,
        validate_no_versioned_node_dirs_in_native_scope,
        validate_dte_examples,
        validate_native_installer_contract,
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
