#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import io
import json
import os
import pathlib
import subprocess
import sys
import time

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")

URL = "https://reservenski.parkpalisadestahoe.com/select-parking"
ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"
STATE_FILE = LOG_DIR / "palisades_parking_watch_state.json"
RUN_LOG = LOG_DIR / "palisades_parking_watch.log"
LOCK_FILE = LOG_DIR / "palisades_parking_watch.lock"
DEBUG_SNAPSHOT = LOG_DIR / "palisades_parking_watch_last_page.txt"
PLAYWRIGHT_PROFILE_DIR = ROOT / ".playwright-profile-stealth"
STEALTH_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
MAX_FETCH_ATTEMPTS = 3
RETRYABLE_BACKOFF_SECONDS = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Palisades parking availability")
    parser.add_argument(
        "--target-date",
        required=True,
        help="Target date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--location",
        default="ALPINE",
        type=str.upper,
        choices=["ALPINE", "PALISADES"],
        help="Parking location to monitor",
    )
    return parser.parse_args()


def parse_target_date(value: str) -> dt.date:
    return dt.datetime.strptime(value, "%Y-%m-%d").date()


def target_label(target_date: dt.date) -> str:
    return (
        f"{target_date.strftime('%A')}, "
        f"{target_date.strftime('%B')} {target_date.day}, {target_date.year}"
    )


def now_iso() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def month_name_to_number(name: str) -> int:
    return dt.datetime.strptime(name[:3], "%b").month


def classify_day_style(style: str | None, aria_disabled: str | None) -> tuple[bool, str]:
    style_text = (style or "").lower()
    is_disabled = (aria_disabled or "").lower() == "true"
    if "49, 200, 25" in style_text:
        return (True, "Calendar day color is green (available)")
    if "247, 205, 212" in style_text:
        return (False, "No availability for target day")
    if is_disabled:
        return (False, "Target day is disabled in calendar")
    if style_text:
        return (False, f"Unrecognized calendar style for target day: {style}")
    return (False, "Target day has no availability style")


def fetch_calendar_status_once(target_date: dt.date, location: str) -> tuple[bool, str, str]:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError("playwright is not installed") from exc

    PLAYWRIGHT_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    target_day_label = target_label(target_date)

    try:
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                str(PLAYWRIGHT_PROFILE_DIR),
                headless=True,
                viewport={"width": 1428, "height": 1008},
                user_agent=STEALTH_UA,
                locale="en-US",
                timezone_id="America/Los_Angeles",
                args=["--disable-blink-features=AutomationControlled"],
            )
            try:
                context.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(URL, wait_until="domcontentloaded", timeout=90000)
                page.wait_for_timeout(5000)

                body_text = page.inner_text("body")
                if "Something went wrong" in body_text:
                    raise RuntimeError("Rendered page shows error state")

                location_choice = page.get_by_text(location, exact=True)
                if location_choice.count() == 0:
                    raise RuntimeError(f"{location} selector not found")
                location_choice.first.click(timeout=8000)
                page.wait_for_timeout(1500)

                date_cell = page.locator(f'[aria-label="{target_day_label}"]')
                for _ in range(16):
                    if date_cell.count() > 0:
                        break
                    month = (
                        page.locator(
                            '.custom-nav button[data-index="0"] .mbsc-calendar-month'
                        )
                        .first.inner_text()
                        .strip()
                    )
                    year = int(
                        page.locator(
                            '.custom-nav button[data-index="0"] .mbsc-calendar-year'
                        )
                        .first.inner_text()
                        .strip()
                    )
                    current = dt.date(year, month_name_to_number(month), 1)
                    target = dt.date(target_date.year, target_date.month, 1)
                    if current < target:
                        page.locator('button[aria-label="Next page"]').first.click(
                            timeout=5000
                        )
                    elif current > target:
                        page.locator('button[aria-label="Previous page"]').first.click(
                            timeout=5000
                        )
                    else:
                        break
                    page.wait_for_timeout(500)
                    date_cell = page.locator(f'[aria-label="{target_day_label}"]')

                if date_cell.count() == 0:
                    raise RuntimeError(f"Target day cell not found: {target_day_label}")

                day = date_cell.first
                style = day.get_attribute("style")
                aria_disabled = day.get_attribute("aria-disabled")
                is_available, reason = classify_day_style(style, aria_disabled)
                snapshot = (
                    f"target={target_day_label}\n"
                    f"style={style}\n"
                    f"aria_disabled={aria_disabled}\n"
                    "-----\n"
                    f"{page.inner_text('body')[:50000]}\n"
                )
                params = (
                    f"--target-date {target_date.isoformat()} "
                    f"--location {location}"
                )
                return (is_available, f"{reason} ({params})", snapshot)
            finally:
                context.close()
    except PlaywrightTimeoutError as exc:
        raise RuntimeError(f"Playwright timeout: {exc}") from exc


def fetch_calendar_status(target_date: dt.date, location: str) -> tuple[bool, str, str]:
    last_error: RuntimeError | None = None
    for attempt in range(1, MAX_FETCH_ATTEMPTS + 1):
        try:
            return fetch_calendar_status_once(target_date, location)
        except RuntimeError as exc:
            if "playwright is not installed" in str(exc).lower():
                raise
            last_error = exc
            if attempt < MAX_FETCH_ATTEMPTS:
                time.sleep(RETRYABLE_BACKOFF_SECONDS * attempt)
    if last_error is None:
        raise RuntimeError("Calendar fetch failed for an unknown reason")
    raise RuntimeError(
        f"{last_error} (after {MAX_FETCH_ATTEMPTS} attempts)"
    ) from last_error


def save_debug_snapshot(page_text: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = (
        f"timestamp={now_iso()}\n"
        f"text_length={len(page_text)}\n"
        "-----\n"
        f"{page_text[:50000]}\n"
    )
    DEBUG_SNAPSHOT.write_text(snapshot, encoding="utf-8")


def acquire_lock() -> io.TextIOWrapper | None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    lock_handle = LOCK_FILE.open("w", encoding="utf-8")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_handle.close()
        return None
    return lock_handle


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(state: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def append_log(line: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with RUN_LOG.open("a", encoding="utf-8") as f:
        f.write(f"{line}\n")


def notify(message: str) -> None:
    safe_message = message.replace('"', '\\"')
    script = (
        f'display notification "{safe_message}" '
        'with title "Palisades Parking Watcher"'
    )
    subprocess.run(["osascript", "-e", script], check=False)


def format_result_line(is_available: bool, reason: str) -> str:
    if is_available:
        return "Available!"
    return "Not Available!"


def format_run_params(target_date: dt.date, location: str) -> str:
    return f"--target-date {target_date.isoformat()} --location {location}"


def main() -> int:
    args = parse_args()
    try:
        target_date = parse_target_date(args.target_date)
    except ValueError:
        error_message = (
            f"invalid --target-date (expected YYYY-MM-DD): {args.target_date}"
        )
        append_log(
            f"[{now_iso()}] [ERROR] {error_message}"
        )
        print(f"[ERROR] {error_message}", file=sys.stderr)
        return 2

    location = args.location
    run_params = format_run_params(target_date, location)
    label = f"{location}, {target_label(target_date)}"
    lock_handle = acquire_lock()
    if lock_handle is None:
        append_log(
            f"[{now_iso()}] [SKIP] overlapping run ({run_params})"
        )
        print("[SKIP] Skipped! (overlapping run)")
        return 0

    timestamp = now_iso()

    try:
        is_available, reason, snapshot = fetch_calendar_status(target_date, location)
        if not is_available:
            save_debug_snapshot(snapshot)
    except RuntimeError as exc:
        error_message = f"detection: {exc}"
        append_log(
            f"[{timestamp}] [ERROR] {error_message} ({run_params})"
        )
        print(f"[ERROR] {error_message}", file=sys.stderr)
        lock_handle.close()
        return 1
    except Exception as exc:  # noqa: BLE001
        error_message = f"unexpected: {exc}"
        append_log(
            f"[{timestamp}] [ERROR] {error_message} ({run_params})"
        )
        print(f"[ERROR] {error_message}", file=sys.stderr)
        lock_handle.close()
        return 1

    state = load_state()
    previous_status = state.get("status", "unknown")
    if state.get("target_date") != target_date.isoformat():
        previous_status = "unknown"
    if state.get("location") != location:
        previous_status = "unknown"

    current_status = "available" if is_available else "not_available"
    result_line = format_result_line(is_available, reason)
    append_log(
        f"[{timestamp}] [RESULT] {result_line} ({run_params})"
    )

    if is_available and previous_status != "available":
        notify(f"Possible {label} availability found. Check now.")

    state["status"] = current_status
    state["last_run"] = timestamp
    state["last_reason"] = reason
    state["target_date"] = target_date.isoformat()
    state["location"] = location
    save_state(state)
    print(f"[RESULT] {result_line}")
    lock_handle.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
