#!/usr/bin/env python3
"""Run Django migrations twice against a clean PostgreSQL database."""

from __future__ import annotations

import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import textwrap
import uuid
from pathlib import Path

import psycopg2
from psycopg2 import sql


REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
LOG_DIR = Path(os.environ.get("MIGRATION_TEST_LOG_DIR", REPO / "artifacts" / "django-migrations-postgres"))


def log(message: str) -> None:
    print(f"[django-migrations-postgres] {message}", flush=True)


def admin_config() -> dict[str, str]:
    return {
        "host": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        "port": os.environ.get("POSTGRES_PORT", "5432"),
        "dbname": os.environ.get("POSTGRES_ADMIN_DB", "postgres"),
        "user": os.environ.get("POSTGRES_ADMIN_USER", os.environ.get("USER", "postgres")),
        "password": os.environ.get("POSTGRES_ADMIN_PASSWORD", ""),
    }


def connect_admin():
    cfg = admin_config()
    kwargs = {
        "host": cfg["host"],
        "port": cfg["port"],
        "dbname": cfg["dbname"],
        "user": cfg["user"],
    }
    if cfg["password"]:
        kwargs["password"] = cfg["password"]
    conn = psycopg2.connect(**kwargs)
    conn.autocommit = True
    return conn


def run_manage(name: str, args: list[str], env_file: Path, temp_root: Path) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stdout_path = LOG_DIR / f"{name}.stdout.log"
    stderr_path = LOG_DIR / f"{name}.stderr.log"
    env = os.environ.copy()
    env.update(
        {
            "DJANGO_ENV_FILE": str(env_file),
            "DOTENV_OVERRIDE": "false",
            "DJANGO_SETTINGS_MODULE": "config.settings",
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PICO_INSTALLER_PREFLIGHT": "1",
            "PICO_CI_TEMP_ROOT": str(temp_root),
        }
    )
    cmd = [sys.executable, "manage.py", *args]
    log(f"RUN {name}: {' '.join(cmd)}")
    proc = subprocess.run(
        cmd,
        cwd=BACKEND,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    stdout_path.write_text(proc.stdout, encoding="utf-8")
    stderr_path.write_text(proc.stderr, encoding="utf-8")
    log(f"EXIT {name}: {proc.returncode} stdout={stdout_path} stderr={stderr_path}")
    if proc.returncode != 0:
        raise RuntimeError(f"{name} failed with exit code {proc.returncode}; see {stdout_path} and {stderr_path}")


def write_env_file(path: Path, *, db_name: str, db_user: str, db_password: str, temp_root: Path) -> None:
    media_root = temp_root / "media"
    static_root = temp_root / "static"
    dte_log_dir = temp_root / "dte_logs"
    for directory in [media_root, static_root, dte_log_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    cfg = admin_config()
    app_port = os.environ.get("APP_HTTP_PORT", "9282")
    content = f"""
    DJANGO_CONFIG_MODE=strict
    DOTENV_OVERRIDE=false
    DJANGO_DEBUG=false
    DJANGO_SECRET_KEY=django-insecure-ci-{secrets.token_urlsafe(48)}

    DB_HOST={cfg["host"]}
    DB_PORT={cfg["port"]}
    DB_NAME={db_name}
    DB_USER={db_user}
    DB_PASSWORD={db_password}

    ALLOWED_HOSTS=localhost,127.0.0.1
    CORS_ALLOWED_ORIGINS=http://127.0.0.1:{app_port}
    CSRF_TRUSTED_ORIGINS=http://127.0.0.1:{app_port}

    DJANGO_MEDIA_ROOT={media_root}
    DJANGO_STATIC_ROOT={static_root}
    DTE_LOG_DIR={dte_log_dir}

    DTE_BACKGROUND_MODE=external
    DTE_BASE_URL=https://dte.invalid
    DTE_API_TOKEN=placeholder-ci-token
    DTE_API_AUTH_HEADER=Authorization
    DTE_API_AUTH_PREFIX=Bearer
    DTE_MONITOR_ENABLED=true
    DTE_OUTBOX_WORKER_ENABLED=true
    DTE_SENTINEL_ENABLED=true
    DTE_MAX_RETRIES=5
    DTE_PENDING_BATCH_SIZE=25

    PICO_BOOTSTRAP_ADMIN_ENABLED=false
    PICO_BOOTSTRAP_ADMIN_USERNAME=admin
    PICO_BOOTSTRAP_ADMIN_PASSWORD=placeholder-ci-only
    """
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


def create_temp_database(conn, db_name: str, db_user: str, db_password: str) -> None:
    with conn.cursor() as cur:
        cur.execute(sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD %s").format(sql.Identifier(db_user)), [db_password])
        cur.execute(sql.SQL("CREATE DATABASE {} OWNER {} ENCODING 'UTF8'").format(sql.Identifier(db_name), sql.Identifier(db_user)))
    log(f"created temporary database {db_name}")


def drop_temp_database(conn, db_name: str, db_user: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
            [db_name],
        )
        cur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(db_name)))
        cur.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(db_user)))
    log(f"dropped temporary database {db_name}")


def fetch_indexes(db_name: str, db_user: str, db_password: str) -> dict[str, str]:
    cfg = admin_config()
    with psycopg2.connect(
        host=cfg["host"],
        port=cfg["port"],
        dbname=db_name,
        user=db_user,
        password=db_password,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            value = cur.fetchone()[0]
            if value != 1:
                raise RuntimeError(f"SELECT 1 returned {value!r}")
            cur.execute(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename IN ('menu_discount', 'menu_product')
                ORDER BY indexname
                """
            )
            rows = cur.fetchall()
    indexes = {name: definition for name, definition in rows}
    (LOG_DIR / "pg_indexes_menu.log").write_text(
        "\n".join(f"{name}: {definition}" for name, definition in indexes.items()) + "\n",
        encoding="utf-8",
    )
    return indexes


def assert_menu_indexes(indexes: dict[str, str]) -> None:
    required = {
        "menu_produc_categor_2de784_idx": "menu_product",
        "menu_discou_is_acti_673081_idx": "menu_discount",
    }
    missing = [name for name in required if name not in indexes]
    if missing:
        raise RuntimeError(f"missing expected menu indexes: {', '.join(missing)}")

    forbidden = [
        "menu_discount_active__c4f9aa_idx",
        "menu_discou_active_b4fadc_idx",
    ]
    present_forbidden = [name for name in forbidden if name in indexes]
    if present_forbidden:
        raise RuntimeError(f"legacy menu indexes still present: {', '.join(present_forbidden)}")


def main() -> int:
    suffix = uuid.uuid4().hex[:12]
    db_name = f"picopos_mig_{suffix}"
    db_user = f"picopos_mig_{suffix}"
    db_password = secrets.token_urlsafe(24)
    temp_root = Path(tempfile.mkdtemp(prefix="picopos-migrations-"))
    env_file = temp_root / "django.env"
    keep_db = os.environ.get("KEEP_POSTGRES_MIGRATION_TEST_DB") == "1"

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(LOG_DIR, ignore_errors=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    conn = connect_admin()
    try:
        create_temp_database(conn, db_name, db_user, db_password)
        write_env_file(env_file, db_name=db_name, db_user=db_user, db_password=db_password, temp_root=temp_root)

        run_manage("migrate-1", ["migrate", "--noinput"], env_file, temp_root)
        run_manage("migrate-2-idempotent", ["migrate", "--noinput"], env_file, temp_root)
        run_manage("showmigrations-menu", ["showmigrations", "menu"], env_file, temp_root)
        run_manage("showmigrations-plan", ["showmigrations", "--plan"], env_file, temp_root)
        run_manage("check-runtime-config", ["check_runtime_config", "--strict"], env_file, temp_root)
        run_manage("makemigrations-check", ["makemigrations", "--check", "--dry-run"], env_file, temp_root)

        indexes = fetch_indexes(db_name, db_user, db_password)
        assert_menu_indexes(indexes)
        log("PostgreSQL migration fixture OK")
        return 0
    finally:
        if keep_db:
            log(f"keeping temporary database {db_name} because KEEP_POSTGRES_MIGRATION_TEST_DB=1")
        else:
            try:
                drop_temp_database(conn, db_name, db_user)
            finally:
                conn.close()
                shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
