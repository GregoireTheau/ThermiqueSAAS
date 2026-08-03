#!/usr/bin/env python3
"""Trigger the SaaS backup endpoint from a Railway cron service."""

from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> int:
    backup_url = os.environ.get("THERMAL_BACKUP_TRIGGER_URL", "").strip()
    admin_token = os.environ.get("THERMAL_SAAS_ADMIN_TOKEN", "").strip()
    if not backup_url or not admin_token:
        print(
            "THERMAL_BACKUP_TRIGGER_URL and THERMAL_SAAS_ADMIN_TOKEN are required.",
            file=sys.stderr,
        )
        return 2

    request = Request(
        backup_url,
        data=b"",
        headers={"X-Thermal-Admin-Token": admin_token},
        method="POST",
    )
    try:
        with urlopen(request, timeout=180) as response:  # noqa: S310 - configured URL
            payload = json.load(response)
    except HTTPError as exc:
        print(f"Backup failed with HTTP {exc.code}.", file=sys.stderr)
        return 1
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)
        return 1

    if payload.get("status") != "ok":
        print("Backup endpoint returned an unexpected response.", file=sys.stderr)
        return 1

    backup = payload.get("backup", {})
    print(
        "Backup completed:",
        backup.get("bucket", "unknown bucket"),
        backup.get("key", "unknown key"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
