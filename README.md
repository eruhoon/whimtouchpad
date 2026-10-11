# WhimPad 🎮

RGDS 등 듀얼 스크린 Linux(Rocknix / PortMaster 환경) 휴대용 게임기에서 하단 보조 스크린을 **마우스 트랙패드** 또는 **가상 키보드**로 활용할 수 있게 해주는 초경량 오버레이입니다.

---

## 주요 기능

- **초경량 네이티브 & 하드웨어 가속 UI**: 
  - 리눅스 커널 `/dev/uinput` 및 독점 터치 이벤트(`EVIOCGRAB`)를 전담하는 고속 C 백엔드 데몬.
  - SDL2 하드웨어 가속 렌더러와 나눔고딕 TTF 텍스처 캐싱을 적용해 CPU/메모리 부하 없이 부드러운 60fps UI 제공.
- **다양한 제스처 및 레이아웃**:
  - **트랙패드 모드 (`Pad`)**:
    - 손가락 1개 드래그: 마우스 커서 부드러운 이동 (커서 가속 지원)
    - 손가락 1개 탭: 좌클릭
    - 손가락 1개 더블 탭 후 홀드: **마우스 드래그 (창/아이템 끌기)**
    - 손가락 2개 드래그: 상/하 휠 스크롤
    - 하단 고정 터치 버튼: `[좌클릭]`, `[휠 스크롤바]`, `[우클릭]`
  - **가상 키보드 모드 (`Keys`)**:
    - 상단 `[키보드로 전환]` 터치 시 Esc, F1~F12, 숫자/특수문자, 방향키, 한/영 입력이 가능한 풀 화상 키보드 지원.
  - **상단 퀵 메뉴**:
    - `[설정 (⚙)]`: 톱니바퀴 아이콘 터치 시 마우스 감도, 스크롤 방향, 화면 보호 시간 조절.
    - `[슬립 (🌙)]`: 초승달 아이콘 터치 시 하단 화면 즉시 블랙아웃(화면 숨김), 화면을 다시 탭하면 오클릭 없이 깨우기.
- **PortMaster 게임 런처 연동**: 기존 게임 `.sh` 파일 상단/하단에 간단한 훅 스크립트만 추가하면 게임 실행 시 자동 기동 및 게임 종료 시 자동 정리.

---

## PortMaster 게임 연동 가이드

기기에서 실행할 PortMaster 게임(예: `StardewValley` 등)에 WhimPad를 연동하는 2단계 방법입니다.

### 1단계: WhimPad 패키지 복사 및 권한 설정

기기 게임 디렉토리 바로 아래에 `whimpad` 폴더를 생성하고, 패키지의 파일들을 복사합니다.

```bash
# [예시] Mac/PC 터미널에서 RGDS 기기로 복사 시
scp -r template/* root@<기기_IP>:/roms/ports/<게임폴더명>/whimpad/
```

복사 후 기기 터미널(SSH)에서 실행 권한을 부여합니다:
```bash
chmod +x /roms/ports/<게임폴더명>/whimpad/whim_hook.sh
chmod +x /roms/ports/<게임폴더명>/whimpad/whimtouchpad_backend
```

---

### 2단계: 게임 실행 스크립트(`.sh`) 수정

게임의 실행 스크립트(예: `/roms/ports/StardewValley.sh`)를 열어 아래 2곳에 코드를 추가합니다.

#### ① 게임 실행 직전 (`$GAMEDIR/game.bin` 또는 게임 런처 실행 바로 윗줄):
```bash
# === [WhimPad Hook Start] ===
if [ -f "$GAMEDIR/whimpad/whim_hook.sh" ]; then
  source "$GAMEDIR/whimpad/whim_hook.sh"
fi
# === [WhimPad Hook End] ===
```

#### ② 게임 실행 직후 (스크립트 맨 끝 `exit 0` 바로 윗줄):
```bash
# === [WhimPad Cleanup] ===
if [ -n "$WHIM_BACKEND_PID" ]; then kill $WHIM_BACKEND_PID 2>/dev/null || true; fi
if [ -n "$WHIM_GESTURE_PID" ]; then kill $WHIM_GESTURE_PID 2>/dev/null || true; fi
if [ -n "$WHIM_UI_PID" ]; then kill $WHIM_UI_PID 2>/dev/null || true; fi
swaymsg output DSI-1 power off >/dev/null 2>&1 || true
# =========================
```

---

## 프로젝트 빌드 & 패키징

이 프로젝트는 **pnpm**을 패키지 매니저로 사용합니다.

```bash
# 종속성 설치
pnpm install

# 빌드 및 dist 패키지 생성 (dist/whimtouchpad-v*.zip)
pnpm run build

# 빌드 산출물 정리
pnpm run clean
```

---

## 버전 관리 및 자동 릴리즈 룰

- 버전 체계: `Major.Minor.Patch.Revision` 4자리 체계 (자세한 내용은 [GEMINI.md](file:///Users/whimsicott/Documents/GitHub/eruhoon/whimtouchpad/GEMINI.md) 참고)
- **마이너(Minor) 버전(`v0.X.0.0`)** 태그가 푸시되면 GitHub Actions를 통해 `dist/whimtouchpad-v*.zip`이 자동 빌드 및 릴리즈됩니다.
