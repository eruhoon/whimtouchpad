#!/bin/bash
# ==============================================================================
# WhimTouchpad - Secondary Screen Touchpad & Keypad Daemon
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$SCRIPT_DIR/whimtouchpad"

MODE="touchpad"
SCREEN=1

while [ $# -gt 0 ]; do
  case "$1" in
    --mode=*)
      MODE="${1#*=}"
      ;;
    --screen=*)
      SCREEN="${1#*=}"
      ;;
  esac
  shift
done

if [ -x "$BIN" ]; then
  exec "$BIN" "--mode=$MODE" "--screen=$SCREEN"
else
  echo "[whimtouchpad] Binary not found or not executable: $BIN" >&2
  exit 1
fi
