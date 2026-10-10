# WhimTouchpad 🎮

RGDS 등 듀얼 스크린 Linux(Rocknix / PortMaster 환경) 휴대용 게임기에서 하단 보조 스크린을 마우스 터치패드 또는 가상 키패드로 활용할 수 있게 해주는 초경량 백그라운드 오버레이 데몬입니다.

---

## 주요 특징

- **초경량 네이티브 코어**: C/SDL2 기반으로 설계되어 메모리 점유율(수 MB 수준)과 CPU 사용량을 극도로 낮추어 메인 게임 성능에 영향을 주지 않습니다.
- **PortMaster 런처 훅 지원**: 기존 게임 `.sh` 파일 상단에 몇 줄의 훅 스크립트만 추가하면 게임 실행 시 백그라운드로 보조 화면에 자동 활성화됩니다.
- **다양한 모드**:
  - `touchpad`: 보조 화면을 마우스 트랙패드로 전환 (터치 드래그 커서 이동, 탭 클릭 등).
  - `keypad`: 게임에 부족한 단축키(ESC, TAB, ENTER, F1~F12 등)를 화면 터치 버튼으로 지원.
- **리눅스 uinput 연동**: `/dev/uinput` 커널 드라이버를 통해 실제 물리 입력과 동일한 가상 마우스/키보드 이벤트를 전송합니다.

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

## PortMaster 게임 연동 방법

PortMaster 게임 실행 쉘 스크립트(예: `Game.sh`)에 아래와 같이 훅을 추가합니다:

```bash
# === [WhimTouchpad Hook Start] ===
if [ -f "$controlfolder/whimtouchpad/whimtouchpad.sh" ]; then
  "$controlfolder/whimtouchpad/whimtouchpad.sh" --mode=touchpad --screen=1 &
  WHIM_PID=$!
fi
# === [WhimTouchpad Hook End] ===

# 메인 게임 실행
$GAMEDIR/game.bin ...

# 게임 종료 후 보조 패드 프로세스 종료
if [ -n "$WHIM_PID" ]; then
  kill -TERM "$WHIM_PID" 2>/dev/null
fi
```

---

## 버전 관리 및 자동 릴리즈 룰

- 버전 체계: `Major.Minor.Patch.Revision` 4자리 체계 (자세한 내용은 [GEMINI.md](file:///Users/whimsicott/Documents/GitHub/eruhoon/whimtouchpad/GEMINI.md) 참고)
- **마이너(Minor) 버전(`v0.X.0.0`)** 태그가 푸시되면 GitHub Actions를 통해 `dist/whimtouchpad-v*.zip`이 자동 빌드 및 릴리즈됩니다.
