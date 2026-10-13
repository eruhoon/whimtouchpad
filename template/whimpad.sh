#!/bin/bash
# ==============================================================================
# WhimPad - Secondary Screen Touchpad & Virtual Keypad (Standalone Runner)
# ==============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cleanup() {
  echo "[whimpad] Shutting down WhimPad..."
  if [ -f "$SCRIPT_DIR/whim_cleanup.sh" ]; then
    source "$SCRIPT_DIR/whim_cleanup.sh"
  fi
  exit 0
}

trap cleanup INT TERM EXIT

echo "[whimpad] Starting WhimPad standalone overlay..."
source "$SCRIPT_DIR/whim_hook.sh"

echo "[whimpad] Running... (Press Ctrl+C to stop)"
if [ -n "$WHIM_UI_PID" ]; then
  wait "$WHIM_UI_PID" 2>/dev/null || sleep infinity
else
  sleep infinity
fi
