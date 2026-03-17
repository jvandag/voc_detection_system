#!/usr/bin/env python3
"""
Standalone watchdog for chamber readings files.

It scans raspberry_pi_src/data for files matching:
    chamber_{any_string}_readings.csv

If a file has data and the last timestamp is older than 10 minutes,
it sends a Discord alert through send_discord_alert_webhook.
"""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path
from typing import Optional
from .DiscordAlerts import send_discord_alert_webhook

SCRIPT_DIR = Path(__file__).resolve().parent


FILENAME_PATTERN = re.compile(r"^chamber_([a-zA-Z0-9]+)_readings\.csv$")
DEFAULT_MAX_AGE_SECONDS = 10 * 60


def extract_chamber_key(file_path: Path) -> Optional[str]:
    match = FILENAME_PATTERN.match(file_path.name)
    if not match:
        return None
    return match.group(1)


def read_last_epoch_timestamp(csv_path: Path) -> Optional[int]:
    """
    Return the first-column epoch timestamp from the last non-empty row.
    """
    last_line: Optional[str] = None
    with csv_path.open("r", encoding="utf-8") as file_obj:
        for line in file_obj:
            stripped = line.strip()
            if stripped:
                last_line = stripped

    if not last_line:
        return None

    first_column = last_line.split(",", 1)[0].strip()
    if not first_column:
        return None

    try:
        return int(float(first_column))
    except ValueError:
        print(f"[WARN] Could not parse epoch timestamp in {csv_path}: '{first_column}'")
        return None


def run_check(data_dir: Path, max_age_seconds: int) -> int:
    now_epoch = int(time.time())
    candidate_files = sorted(data_dir.glob("chamber_*_readings.csv"))
    files = [file_path for file_path in candidate_files if extract_chamber_key(file_path) is not None]
    if not files:
        print(f"[INFO] No files matching the correct naming scheme found in {data_dir}. Exiting.")
        return 0

    print(f"[START] Watching {len(files)} file(s):")
    for file_path in files:
        print(f"  - {file_path.name}")

    failed_alerts = 0
    alerts_sent = 0

    for file_path in files:
        chamber_key = extract_chamber_key(file_path)

        last_timestamp = read_last_epoch_timestamp(file_path)
        if last_timestamp is None:
            print(f"[INFO] {file_path.name}: no rows found, skipping")
            continue

        age_seconds = now_epoch - last_timestamp
        if age_seconds <= max_age_seconds:
            print(f"[OK] {file_path.name}: last update {age_seconds}s ago")
            continue

        error_message = (
            f"is not sending data (last update was {age_seconds // 60} minutes ago)"
        )
        success =  send_discord_alert_webhook(chamber_key, error_message) if chamber_key is not None else False
        if success:
            alerts_sent += 1
            print(f"[ALERT] Sent stale-data alert for chamber '{chamber_key}'")
        else:
            failed_alerts += 1
            print(f"[ERROR] Failed to send alert for chamber '{chamber_key}'")

    print(
        f"[DONE] Files checked: {len(files)}, alerts sent: {alerts_sent}, alert failures: {failed_alerts}"
    )
    return 1 if failed_alerts else 0


def main() -> int:
    project_root = SCRIPT_DIR.parent.parent.parent
    parser = argparse.ArgumentParser(
        description="Watch chamber readings files and send stale-data Discord alerts."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=project_root / "data",
        help="Path to chamber readings directory (default: raspberry_pi_src/data)",
    )
    parser.add_argument(
        "--max-age-seconds",
        type=int,
        default=DEFAULT_MAX_AGE_SECONDS,
        help=f"Max allowed age in seconds (default: {DEFAULT_MAX_AGE_SECONDS})",
    )

    args = parser.parse_args()
    data_dir = args.data_dir.resolve()

    if not data_dir.exists() or not data_dir.is_dir():
        print(f"[ERROR] Data directory does not exist: {data_dir}")
        return 1

    return run_check(data_dir=data_dir, max_age_seconds=args.max_age_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
