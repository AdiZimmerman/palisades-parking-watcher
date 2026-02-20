# Palisades Parking Watcher

Monitors Palisades parking availability for a target date and location (`ALPINE` or `PALISADES`) and logs status on a configurable cadence.

## Features

- Uses Playwright DOM interaction (not direct backend API calls)
- Clicks selected location (`ALPINE` or `PALISADES`), opens the date calendar, and reads the target day style
- Classifies:
  - green day tile -> `available`
  - pink day tile -> `not_available` (sold out)
- Writes run logs and state to `logs/`
- Sends a macOS notification when status transitions to `available`

## Repository Layout

- `src/main.py`: watcher script
- `install.sh`: cron installer
- `tests/test_install.py`: cron installer tests
- `tests/test_main.py`: unit tests
- `logs/`: runtime outputs (ignored except `.gitkeep`)

## Requirements

- macOS
- Python 3.9+
- `cron`

Install dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
PLAYWRIGHT_BROWSERS_PATH=0 .venv/bin/playwright install chromium
```

## Run Once

```bash
.venv/bin/python3 src/main.py --target-date <YYYY-MM-DD> --location <ALPINE|PALISADES>
```

## Turn Cron On (Install Cron)

```bash
# every 1 minute (default)
bash install.sh --target-date <YYYY-MM-DD> --location <ALPINE|PALISADES>

# every N minutes (1-59)
bash install.sh --target-date <YYYY-MM-DD> --location <ALPINE|PALISADES> --interval-minutes <N>
```

This installs a single cron line tagged with `# palisades-parking-watch`.

Cadence notes:
- `--interval-minutes N` runs every N minutes (`N` from 1 to 59).

## Verify Cron

```bash
crontab -l
tail -n 20 logs/palisades_parking_watch.log
```

## Turn Cron Off

Remove the line containing `# palisades-parking-watch` from `crontab -l` (no-op if it is not installed).

```bash
tmpfile="$(mktemp)"
crontab -l | grep -v "# palisades-parking-watch" > "$tmpfile" || true
crontab "$tmpfile"
rm -f "$tmpfile"
```

## Run Tests

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```
