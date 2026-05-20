#!/usr/bin/env python3
"""Pre-production readiness checks for RELAY237."""

from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.error
import urllib.request
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "delivr_core.settings")


class Preflight:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.warnings: list[str] = []

    def ok(self, message: str) -> None:
        print(f"[OK] {message}")

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        print(f"[WARN] {message}")

    def fail(self, message: str) -> None:
        self.failures.append(message)
        print(f"[FAIL] {message}")

    def section(self, title: str) -> None:
        print(f"\n== {title} ==")

    def exit_code(self) -> int:
        return 1 if self.failures else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run RELAY237 pre-production readiness checks."
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("PREFLIGHT_BASE_URL", ""),
        help="Optional deployed base URL, for example https://staging.relay237.com",
    )
    parser.add_argument(
        "--require-production",
        action="store_true",
        help="Fail unless DJANGO_ENV=production and DEBUG=False.",
    )
    parser.add_argument(
        "--skip-static",
        action="store_true",
        help="Skip collectstatic dry-run.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="HTTP timeout in seconds for deployed health checks.",
    )
    return parser.parse_args()


def setup_django(preflight: Preflight):
    preflight.section("Django bootstrap")
    started = time.monotonic()
    try:
        import django

        django.setup()
    except Exception as exc:  # pragma: no cover - this is the point of preflight
        preflight.fail(f"Django failed to start: {exc}")
        return None

    preflight.ok(f"Django started in {time.monotonic() - started:.2f}s")
    from django.conf import settings

    return settings


def check_environment(preflight: Preflight, settings, require_production: bool) -> None:
    preflight.section("Environment")
    django_env = getattr(settings, "DJANGO_ENV", "")
    debug = bool(getattr(settings, "DEBUG", True))

    preflight.ok(f"DJANGO_ENV={django_env}")
    preflight.ok(f"DEBUG={debug}")

    if require_production and django_env != "production":
        preflight.fail("DJANGO_ENV must be production")
    if require_production and debug:
        preflight.fail("DEBUG must be False")

    public_domain = getattr(settings, "PUBLIC_DOMAIN", "")
    allowed_hosts = list(getattr(settings, "ALLOWED_HOSTS", []))
    csrf_origins = list(getattr(settings, "CSRF_TRUSTED_ORIGINS", []))
    cors_origins = list(getattr(settings, "CORS_ALLOWED_ORIGINS", []))

    preflight.ok(f"PUBLIC_DOMAIN={public_domain}")
    preflight.ok(f"ALLOWED_HOSTS={','.join(allowed_hosts)}")
    preflight.ok(f"CSRF_TRUSTED_ORIGINS={','.join(csrf_origins)}")
    preflight.ok(f"CORS_ALLOWED_ORIGINS={','.join(cors_origins)}")

    if public_domain and public_domain not in allowed_hosts and require_production:
        preflight.fail("PUBLIC_DOMAIN is not present in ALLOWED_HOSTS")
    if any(origin.startswith("http://") for origin in cors_origins) and require_production:
        preflight.fail("CORS_ALLOWED_ORIGINS contains plain HTTP origins")
    if not csrf_origins and require_production:
        preflight.fail("CSRF_TRUSTED_ORIGINS is empty")


def run_django_checks(preflight: Preflight) -> None:
    preflight.section("Django checks")
    from django.core.management import call_command

    try:
        call_command("check", verbosity=0)
        preflight.ok("manage.py check")
    except Exception as exc:
        preflight.fail(f"manage.py check failed: {exc}")

    output = StringIO()
    try:
        with redirect_stdout(output), redirect_stderr(output):
            call_command("check", deploy=True, verbosity=1)
        preflight.ok("manage.py check --deploy")
    except Exception as exc:
        preflight.fail(f"manage.py check --deploy failed: {exc}")

    deploy_output = output.getvalue().strip()
    if deploy_output:
        preflight.warn("check --deploy produced warnings; review output in CI logs")


def check_database(preflight: Preflight) -> None:
    preflight.section("Database")
    from django.db import connection
    from django.db.models import Count
    from django.db.migrations.executor import MigrationExecutor
    from finance.models import Transaction, TransactionStatus, TransactionType

    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        preflight.ok("database connection")
    except Exception as exc:
        preflight.fail(f"database connection failed: {exc}")
        return

    executor = MigrationExecutor(connection)
    targets = executor.loader.graph.leaf_nodes()
    plan = executor.migration_plan(targets)
    if plan:
        pending = ", ".join(f"{migration.app_label}.{migration.name}" for migration, _ in plan)
        preflight.fail(f"pending migrations: {pending}")
    else:
        preflight.ok("no pending migrations")

    duplicates = (
        Transaction.objects.filter(
            delivery__isnull=False,
            status=TransactionStatus.COMPLETED,
            transaction_type__in=[
                TransactionType.COMMISSION,
                TransactionType.DELIVERY_CREDIT,
            ],
        )
        .values("delivery_id", "user_id", "transaction_type")
        .annotate(tx_count=Count("id"))
        .filter(tx_count__gt=1)
    )
    duplicate_count = duplicates.count()
    if duplicate_count:
        sample = list(duplicates[:5])
        preflight.fail(
            "duplicate completed delivery wallet transactions "
            f"({duplicate_count} groups, sample={sample})"
        )
    else:
        preflight.ok("unique_completed_delivery_wallet_tx precheck")


def check_staticfiles(preflight: Preflight, skip_static: bool) -> None:
    preflight.section("Static files")
    if skip_static:
        preflight.warn("collectstatic dry-run skipped")
        return

    from django.core.management import call_command

    try:
        call_command("collectstatic", dry_run=True, interactive=False, verbosity=0)
        preflight.ok("collectstatic dry-run")
    except Exception as exc:
        preflight.fail(f"collectstatic dry-run failed: {exc}")


def check_deployed_health(preflight: Preflight, base_url: str, timeout: int) -> None:
    preflight.section("Deployed health")
    if not base_url:
        preflight.warn("No --base-url provided; skipped HTTP health checks")
        return

    base_url = base_url.rstrip("/")
    for path in ("/health/", "/health/ready/"):
        url = f"{base_url}{path}"
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                status = response.status
                if 200 <= status < 300:
                    preflight.ok(f"{url} -> {status}")
                else:
                    preflight.fail(f"{url} -> {status}")
        except urllib.error.URLError as exc:
            preflight.fail(f"{url} failed: {exc}")

    if base_url.startswith("https://"):
        host = base_url.removeprefix("https://")
        preflight.ok(f"expected WebSocket scheme: wss://{host}/ws/...")
    else:
        preflight.fail("base URL must use HTTPS for pre-prod/prod")


def main() -> int:
    args = parse_args()
    preflight = Preflight()

    settings = setup_django(preflight)
    if settings is None:
        return preflight.exit_code()

    check_environment(preflight, settings, args.require_production)
    run_django_checks(preflight)
    check_database(preflight)
    check_staticfiles(preflight, args.skip_static)
    check_deployed_health(preflight, args.base_url, args.timeout)

    preflight.section("Summary")
    if preflight.failures:
        preflight.fail(f"{len(preflight.failures)} blocking issue(s)")
    else:
        preflight.ok("no blocking issue")
    if preflight.warnings:
        preflight.warn(f"{len(preflight.warnings)} warning(s)")

    return preflight.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
