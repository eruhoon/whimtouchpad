#!/bin/bash
# ==============================================================================
# WhimPad Cleanup Hook for Rocknix / Dual-Screen Handhelds
# ==============================================================================
export SWAYSOCK="${SWAYSOCK:-/var/run/0-runtime-dir/sway-ipc.0.sock}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-1}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/var/run/0-runtime-dir}"

WHIMPAD_RUNTIME_DIR="/run/whimpad"

# 1. 프로세스 종료 (환경변수 PID 또는 pidfile)
if [ -n "$WHIM_BACKEND_PID" ]; then
  kill "$WHIM_BACKEND_PID" 2>/dev/null || true
fi
if [ -n "$WHIM_UI_PID" ]; then
  kill "$WHIM_UI_PID" 2>/dev/null || true
fi

if [ -f "$WHIMPAD_RUNTIME_DIR/backend.pid" ]; then
  kill "$(cat "$WHIMPAD_RUNTIME_DIR/backend.pid")" 2>/dev/null || true
  rm -f "$WHIMPAD_RUNTIME_DIR/backend.pid"
fi
if [ -f "$WHIMPAD_RUNTIME_DIR/ui.pid" ]; then
  kill "$(cat "$WHIMPAD_RUNTIME_DIR/ui.pid")" 2>/dev/null || true
  rm -f "$WHIMPAD_RUNTIME_DIR/ui.pid"
fi

# Fallback: 혹시 남아있을 수 있는 백그라운드 프로세스 정리
pkill -f "python3.*ui.py" 2>/dev/null || true
pkill -f "whimpad_backend" 2>/dev/null || true

# 2. 하단 보조화면 전원 끄기 (동적 감지된 커넥터 지원)
BOTTOM_OUT="$WHIMPAD_BOTTOM_OUTPUT"
if [ -z "$BOTTOM_OUT" ] && [ -f "$WHIMPAD_RUNTIME_DIR/bottom_output" ]; then
  BOTTOM_OUT="$(cat "$WHIMPAD_RUNTIME_DIR/bottom_output" 2>/dev/null)"
fi
BOTTOM_OUT="${BOTTOM_OUT:-DSI-1}"
swaymsg output "$BOTTOM_OUT" power off >/dev/null 2>&1 || true

# 3. 런타임 임시 디렉토리 정리
rm -rf "$WHIMPAD_RUNTIME_DIR" 2>/dev/null || true

echo "[whimpad] Overlay cleaned up successfully."
