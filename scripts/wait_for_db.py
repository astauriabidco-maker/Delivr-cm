#!/usr/bin/env python
"""Wait until Django can open a usable database connection."""

import os
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "delivr_core.settings")

import django
from django.db import OperationalError, connections


def main():
    django.setup()

    timeout = int(os.environ.get("WAIT_FOR_DB_TIMEOUT", "180"))
    interval = float(os.environ.get("WAIT_FOR_DB_INTERVAL", "2"))
    deadline = time.monotonic() + timeout
    last_error = None

    while time.monotonic() < deadline:
        try:
            connections["default"].ensure_connection()
            with connections["default"].cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            print("Database is ready", flush=True)
            return 0
        except OperationalError as exc:
            last_error = exc
            connections["default"].close()
            print(f"Waiting for database: {exc}", flush=True)
            time.sleep(interval)

    print(f"Database did not become ready within {timeout}s: {last_error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
