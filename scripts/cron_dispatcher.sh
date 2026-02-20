#!/usr/bin/env bash
set -euo pipefail

INTERVAL_SECONDS=""
PYTHON_BIN=""
WATCH_SCRIPT=""
TARGET_DATE=""
LOCATION=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --interval-seconds)
      INTERVAL_SECONDS="${2:-}"
      shift 2
      ;;
    --python-bin)
      PYTHON_BIN="${2:-}"
      shift 2
      ;;
    --watch-script)
      WATCH_SCRIPT="${2:-}"
      shift 2
      ;;
    --target-date)
      TARGET_DATE="${2:-}"
      shift 2
      ;;
    --location)
      LOCATION="${2:-}"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1"
      exit 2
      ;;
  esac
done

if [[ -z "$INTERVAL_SECONDS" || -z "$PYTHON_BIN" || -z "$WATCH_SCRIPT" || -z "$TARGET_DATE" || -z "$LOCATION" ]]; then
  echo "Missing required arguments"
  exit 2
fi

if ! [[ "$INTERVAL_SECONDS" =~ ^[0-9]+$ ]] || [[ "$INTERVAL_SECONDS" -le 0 ]]; then
  echo "--interval-seconds must be a positive integer"
  exit 2
fi

run_once() {
  "$PYTHON_BIN" "$WATCH_SCRIPT" --target-date "$TARGET_DATE" --location "$LOCATION"
}

if (( INTERVAL_SECONDS < 60 )); then
  elapsed=0
  while (( elapsed < 60 )); do
    run_once
    elapsed=$((elapsed + INTERVAL_SECONDS))
    if (( elapsed < 60 )); then
      sleep "$INTERVAL_SECONDS"
    fi
  done
  exit 0
fi

if (( INTERVAL_SECONDS == 60 )); then
  run_once
  exit 0
fi

epoch_now="$(date +%s)"
if (( epoch_now % INTERVAL_SECONDS == 0 )); then
  run_once
else
  echo "SKIP cadence interval_seconds=${INTERVAL_SECONDS} epoch=${epoch_now}"
fi

