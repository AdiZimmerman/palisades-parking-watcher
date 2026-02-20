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

- `src/palisades_parking_watch.py`: watcher script
- `install_palisades_parking_cron.sh`: cron installer
- `tests/test_cron_scripts.py`: cron installer tests
- `tests/test_palisades_parking_watch.py`: unit tests
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
.venv/bin/python3 src/palisades_parking_watch.py --target-date 2026-02-21 --location ALPINE
```

## Install Cron (Every Minute)

```bash
# every 1 minute (default)
bash install_palisades_parking_cron.sh --target-date 2026-02-21 --location ALPINE

# every 5 minutes
bash install_palisades_parking_cron.sh --target-date 2026-02-21 --location PALISADES --interval-minutes 5
```

This installs a single cron line tagged with `# palisades-parking-watch`.

Cadence notes:
- `--interval-minutes N` runs every N minutes (`N` from 1 to 59).

## Verify Cron

```bash
crontab -l
tail -n 20 logs/palisades_parking_watch.log
```

## Uninstall Cron

Remove the line containing `# palisades-parking-watch` from `crontab -l`.

## Portability

The source scripts resolve paths from their own file location, so the project can be moved anywhere on your machine.
If you move the repo, reinstall cron from the new path:

```bash
bash install_palisades_parking_cron.sh --target-date YYYY-MM-DD --location ALPINE
```

## Run Tests

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```
