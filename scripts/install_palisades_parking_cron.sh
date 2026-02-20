#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WATCH_SCRIPT="$ROOT/scripts/palisades_parking_watch.py"
DISPATCH_SCRIPT="$ROOT/scripts/cron_dispatcher.sh"
CRON_LOG="$ROOT/logs/palisades_parking_watch.cron.log"
MARKER="# palisades-parking-watch"
TARGET_DATE=""
LOCATION="ALPINE"
INTERVAL_MINUTES=""
INTERVAL_SECONDS=""

usage() {
  cat <<EOF
Usage:
  $0 --target-date YYYY-MM-DD [--location ALPINE|PALISADES] [--interval-minutes N | --interval-seconds N]

Examples:
  $0 --target-date 2026-02-21
  $0 --target-date 2026-02-21 --location PALISADES --interval-minutes 5
  $0 --target-date 2026-02-21 --location ALPINE --interval-seconds 30
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-date)
      TARGET_DATE="${2:-}"
      shift 2
      ;;
    --location)
      LOCATION="${2:-}"
      shift 2
      ;;
    --interval-minutes)
      INTERVAL_MINUTES="${2:-}"
      shift 2
      ;;
    --interval-seconds)
      INTERVAL_SECONDS="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$TARGET_DATE" ]]; then
  echo "--target-date is required"
  usage
  exit 2
fi

if [[ "$LOCATION" != "ALPINE" && "$LOCATION" != "PALISADES" ]]; then
  echo "--location must be ALPINE or PALISADES"
  exit 2
fi

if [[ -n "$INTERVAL_MINUTES" && -n "$INTERVAL_SECONDS" ]]; then
  echo "Use either --interval-minutes or --interval-seconds, not both"
  exit 2
fi

if [[ -z "$INTERVAL_MINUTES" && -z "$INTERVAL_SECONDS" ]]; then
  INTERVAL_MINUTES="1"
fi

if [[ -n "$INTERVAL_MINUTES" ]]; then
  if ! [[ "$INTERVAL_MINUTES" =~ ^[0-9]+$ ]] || [[ "$INTERVAL_MINUTES" -le 0 ]]; then
    echo "--interval-minutes must be a positive integer"
    exit 2
  fi
  INTERVAL_SECONDS="$((INTERVAL_MINUTES * 60))"
fi

if ! [[ "$INTERVAL_SECONDS" =~ ^[0-9]+$ ]] || [[ "$INTERVAL_SECONDS" -le 0 ]]; then
  echo "--interval-seconds must be a positive integer"
  exit 2
fi

PYTHON_BIN="/usr/bin/env python3"
if [[ -x "$ROOT/.venv/bin/python3" ]]; then
  PYTHON_BIN="$ROOT/.venv/bin/python3"
fi
CRON_LINE="* * * * * '$DISPATCH_SCRIPT' --interval-seconds '$INTERVAL_SECONDS' --python-bin '$PYTHON_BIN' --watch-script '$WATCH_SCRIPT' --target-date '$TARGET_DATE' --location '$LOCATION' >> '$CRON_LOG' 2>&1 $MARKER"

mkdir -p "$ROOT/logs"
chmod +x "$WATCH_SCRIPT"
chmod +x "$DISPATCH_SCRIPT"

tmpfile="$(mktemp)"
if crontab -l >/dev/null 2>&1; then
  crontab -l | grep -v "$MARKER" | grep -v "# alpine-parking-watch" >"$tmpfile" || true
else
  : >"$tmpfile"
fi

echo "$CRON_LINE" >>"$tmpfile"
crontab "$tmpfile"
rm -f "$tmpfile"

echo "Installed cron watcher:"
echo "$CRON_LINE"
echo "Log file: $CRON_LOG"
