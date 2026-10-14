#!/bin/bash
# ==============================================================================
# WhimPad Launcher Hook for Rocknix / Dual-Screen Handhelds
# ==============================================================================
export SWAYSOCK="${SWAYSOCK:-/var/run/0-runtime-dir/sway-ipc.0.sock}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-1}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/var/run/0-runtime-dir}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export WHIMPAD_RUNTIME_DIR="/run/whimpad"
export GAME_PID="${GAME_PID:-$$}"
mkdir -p "$WHIMPAD_RUNTIME_DIR"

# 게임 폴더 내의 커스텀 whimpad.xml 레이아웃 자동 감지
if [ -z "$WHIMPAD_CUSTOM_LAYOUT" ]; then
  if [ -n "$GAMEDIR" ] && [ -f "$GAMEDIR/whimpad.xml" ]; then
    export WHIMPAD_CUSTOM_LAYOUT="$GAMEDIR/whimpad.xml"
  elif [ -n "$GAMEDIR" ] && [ -f "$GAMEDIR/whimpad/whimpad.xml" ]; then
    export WHIMPAD_CUSTOM_LAYOUT="$GAMEDIR/whimpad/whimpad.xml"
  elif [ -f "$(dirname "$SCRIPT_DIR")/whimpad.xml" ]; then
    export WHIMPAD_CUSTOM_LAYOUT="$(dirname "$SCRIPT_DIR")/whimpad.xml"
  elif [ -f "$SCRIPT_DIR/whimpad.xml" ]; then
    export WHIMPAD_CUSTOM_LAYOUT="$SCRIPT_DIR/whimpad.xml"
  fi
fi

# 디스플레이 자동 탐색 추상화 (Sway IPC 기반 상/하단 커넥터 감지 및 환경변수 주입)
if [ -z "$WHIMPAD_BOTTOM_OUTPUT" ] || [ -z "$WHIMPAD_TOP_OUTPUT" ]; then
  EVAL_OUT=$(python3 - << 'EOF'
import os, socket, struct, json

swaysock = os.environ.get("SWAYSOCK", "/var/run/0-runtime-dir/sway-ipc.0.sock")
bottom_out = os.environ.get("WHIMPAD_BOTTOM_OUTPUT", "")
top_out = os.environ.get("WHIMPAD_TOP_OUTPUT", "")

if (not bottom_out or not top_out) and os.path.exists(swaysock):
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(swaysock)
        s.sendall(b'i3-ipc\x00\x00\x00\x00\x03\x00\x00\x00')
        header = s.recv(14)
        if len(header) == 14 and header[:6] == b'i3-ipc':
            size = struct.unpack('=II', header[6:])[0]
            data = b''
            while len(data) < size:
                chunk = s.recv(size - len(data))
                if not chunk: break
                data += chunk
            outputs = [o for o in json.loads(data.decode()) if o.get('active')]
            if outputs:
                # Sort by y coordinate: top has minimum y, bottom has maximum y
                outputs.sort(key=lambda o: (o.get('rect', {}).get('y', 0), o.get('rect', {}).get('x', 0)))
                if not top_out:
                    top_out = outputs[0].get('name', 'DSI-2')
                if not bottom_out:
                    bottom_out = outputs[-1].get('name', 'DSI-1')
        s.close()
    except Exception:
        pass

if not top_out: top_out = "DSI-2"
if not bottom_out: bottom_out = "DSI-1"

print(f'export WHIMPAD_TOP_OUTPUT="{top_out}"; export WHIMPAD_BOTTOM_OUTPUT="{bottom_out}";')
EOF
  2>/dev/null)
  if [ -n "$EVAL_OUT" ]; then
    eval "$EVAL_OUT"
  fi
fi

export WHIMPAD_BOTTOM_OUTPUT="${WHIMPAD_BOTTOM_OUTPUT:-DSI-1}"
export WHIMPAD_TOP_OUTPUT="${WHIMPAD_TOP_OUTPUT:-DSI-2}"
echo "$WHIMPAD_BOTTOM_OUTPUT" > "$WHIMPAD_RUNTIME_DIR/bottom_output" 2>/dev/null || true
echo "$WHIMPAD_TOP_OUTPUT" > "$WHIMPAD_RUNTIME_DIR/top_output" 2>/dev/null || true

# 1. 하단 보조화면 전원 켜기 및 Sway 전체화면 규칙 설정
swaymsg output "$WHIMPAD_BOTTOM_OUTPUT" power on >/dev/null 2>&1
swaymsg 'no_focus [app_id="whimpad"]' >/dev/null 2>&1 || true
swaymsg 'for_window [app_id="whimpad"] floating enable' >/dev/null 2>&1 || true
swaymsg "for_window [app_id=\"whimpad\"] move container to output $WHIMPAD_BOTTOM_OUTPUT" >/dev/null 2>&1 || true
swaymsg 'for_window [app_id="whimpad"] fullscreen enable' >/dev/null 2>&1 || true

# 2. 고속 C 백엔드 데몬 실행 (하단 터치 독점 grab & uinput 장치 등록)
BACKEND_BIN="$SCRIPT_DIR/whimpad_backend"
if [ -x "$BACKEND_BIN" ]; then
  "$BACKEND_BIN" "$WHIMPAD_RUNTIME_DIR" >/dev/null 2>&1 &
  export WHIM_BACKEND_PID=$!
  echo "$WHIM_BACKEND_PID" > "$WHIMPAD_RUNTIME_DIR/backend.pid" 2>/dev/null || true
fi

# 3. 아름다운 가상 키패드 & 트랙패드 SDL2 그래픽 UI 실행 (타이틀 'whimpad' -> DSI-1 전체화면)
export SDL_VIDEODRIVER=wayland
export SDL_VIDEO_WAYLAND_WMCLASS=whimpad
export SDL_APP_ID=whimpad

python3 "$SCRIPT_DIR/ui.py" >/dev/null 2>&1 &
export WHIM_UI_PID=$!
echo "$WHIM_UI_PID" > "$WHIMPAD_RUNTIME_DIR/ui.pid" 2>/dev/null || true

# 4. 하단 화면 안정화 및 전체화면 유지 백그라운드 가드
# 게임 기동 시점(창 생성, 포커스 전환, Rocknix 기본 절전 등)의 레이스 컨디션을 방지하기 위해
# 일정 시간 동안 DSI-1 전원 및 whimpad 전체화면 배치를 반복 보장합니다.
(
  for i in $(seq 1 20); do
    sleep 0.3
    swaymsg output "$WHIMPAD_BOTTOM_OUTPUT" power on >/dev/null 2>&1
    swaymsg "[app_id=\"whimpad\"] move container to output $WHIMPAD_BOTTOM_OUTPUT" >/dev/null 2>&1 || swaymsg "[title=\"whimpad\"] move container to output $WHIMPAD_BOTTOM_OUTPUT" >/dev/null 2>&1
    swaymsg '[app_id="whimpad"] fullscreen enable' >/dev/null 2>&1 || swaymsg '[title="whimpad"] fullscreen enable' >/dev/null 2>&1
  done
) &

echo "[whimpad] Overlay online (Backend: $WHIM_BACKEND_PID, UI: $WHIM_UI_PID)"
