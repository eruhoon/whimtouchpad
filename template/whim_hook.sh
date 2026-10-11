#!/bin/bash
# ==============================================================================
# WhimPad Launcher Hook for Rocknix / Dual-Screen Handhelds
# ==============================================================================
export SWAYSOCK="${SWAYSOCK:-/var/run/0-runtime-dir/sway-ipc.0.sock}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-1}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/var/run/0-runtime-dir}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export WHIMPAD_RUNTIME_DIR="/run/whimpad"
mkdir -p "$WHIMPAD_RUNTIME_DIR"

# 1. 하단 보조화면 DSI-1 전원 켜기 및 Sway 전체화면 규칙 설정
swaymsg output DSI-1 power on >/dev/null 2>&1
swaymsg 'no_focus [app_id="whimpad"]' >/dev/null 2>&1 || true
swaymsg 'for_window [app_id="whimpad"] floating enable' >/dev/null 2>&1 || true
swaymsg 'for_window [app_id="whimpad"] move container to output DSI-1' >/dev/null 2>&1 || true
swaymsg 'for_window [app_id="whimpad"] fullscreen enable' >/dev/null 2>&1 || true

# 2. 고속 C 백엔드 데몬 실행 (하단 터치 독점 grab & uinput 장치 등록)
BACKEND_BIN="$SCRIPT_DIR/whimtouchpad_backend"
if [ -x "$BACKEND_BIN" ]; then
  "$BACKEND_BIN" "$WHIMPAD_RUNTIME_DIR" >/dev/null 2>&1 &
  export WHIM_BACKEND_PID=$!
fi

# 3. 아름다운 가상 키패드 & 트랙패드 SDL2 그래픽 UI 실행 (타이틀 'whimpad' -> DSI-1 전체화면)
export SDL_VIDEODRIVER=wayland
export SDL_VIDEO_WAYLAND_WMCLASS=whimpad
export SDL_APP_ID=whimpad

python3 "$SCRIPT_DIR/ui.py" >/dev/null 2>&1 &
export WHIM_UI_PID=$!

# 창이 뜬 후 하단 DSI-1 전체화면으로 확실하게 확장
(
  for i in $(seq 1 10); do
    sleep 0.2
    if swaymsg '[app_id="whimpad"] move container to output DSI-1; [app_id="whimpad"] fullscreen enable' >/dev/null 2>&1; then
      break
    fi
  done
) &

echo "[whimpad] Overlay online (Backend: $WHIM_BACKEND_PID, UI: $WHIM_UI_PID)"
