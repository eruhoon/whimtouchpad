# WhimPad 개발 계획서

**RGDS 등 듀얼 스크린 Linux(Rocknix / PortMaster 환경) 보조 스크린 터치패드 & 커스텀 가상 키패드 런처**

---

## 1. 프로젝트 개요 및 배경

- **배경**: RGDS 등 듀얼 디스플레이를 탑재한 리눅스 기반 휴대용 게임기(Rocknix 등)에서 PortMaster 게임 구동 시, 보조 화면(하단 스크린)이 활용되지 않고 비활성화 상태로 방치되는 문제가 있음.
- **목표**:
  - 기존 PortMaster 게임의 실행 스크립트(`.sh`)에 간단한 주입(인젝션) 구문만 추가하여 하단 스크린에 **마우스 터치패드** 또는 **커스텀 보조 가상 키패드(핫키, 단축키, F키 등)** UI를 띄움.
  - 사용자의 하단 터치 입력을 리눅스 커널 가상 입력 장치(`/dev/uinput` 등)를 통해 메인 시스템의 마우스/키보드 이벤트로 변환 주입.
  - **최소 리소스 목표**: 게임 구동에 영향을 주지 않도록 메모리와 CPU 점유율을 극도로 낮춘 최적의 런타임/엔진 구성.
  - **버전 관리 규칙**: `Major.Minor.Patch.Revision` 4자리 체계(예: `v0.1.0.0`)를 사용하며, **마이너(Minor) 업데이트 시(`v0.X.0.0`) GitHub Release 자동 빌드/배포**.
  - **패키지 관리**: `pnpm` 기반으로 빌드 스크립트 실행, 최종 아티팩트는 `dist/`에 패키징.

---

## 2. 런타임 및 엔진 기술 검토

- 메인 화면의 PortMaster 게임이 CPU/GPU/RAM을 원활하게 쓸 수 있도록 보조 스크린 프로세스는 **최소한의 오버헤드**를 목표로 함.
- **초경량 네이티브 (C + uinput / evdev 독점 grab)**:
  - 메모리 사용량 수 MB 단위, 즉각적인 이벤트 처리로 최우선 후보.
- **SDL2 하드웨어 가속 렌더러**:
  - 텍스처 캐싱을 적용하여 60fps 부드러운 UI 렌더링 및 초저지연 터치 응답 달성.
- 빌드/패키징 오케스트레이션 및 릴리즈 번들링은 `pnpm`과 Node.js 스크립트로 일관되게 관리.

---

## 3. 핵심 아키텍처 및 동작 원리

1. **하단 디스플레이 타겟팅 및 Sway 매핑**:
   - Wayland / Sway 환경에서 `app_id="whimpad"` 창을 감지하여 보조 커넥터(`DSI-1`)로 전체 화면(`fullscreen enable`) 자동 이동.
2. **입력 캡처 및 에뮬레이션 (`uinput`)**:
   - 하단 디스플레이의 터치스크린 입력 장치를 `fe5e0000` I2C 경로로 단독 매칭하여 독점 캡처(`EVIOCGRAB`).
   - **트랙패드 모드**:
     - 1점 드래그 ➔ 마우스 커서 부드러운 이동 (커서 가속 지원)
     - 1점 탭 ➔ 마우스 좌클릭 (`BTN_LEFT`)
     - 1점 더블 탭 후 홀드 ➔ 마우스 드래그 (`BTN_LEFT` 유지)
     - 2점 드래그 ➔ 마우스 휠 스크롤 (`REL_WHEEL`)
   - **가상 키패드 모드**:
     - 화면에 렌더링된 버튼 영역 클릭 시 Linux `uinput`으로 `KEY_ESC`, `KEY_F1~F12`, `KEY_ENTER`, `KEY_SPACE` 등 즉시 발송.
3. **상단 퀵 제어**:
   - `[설정 (⚙)]`: 톱니바퀴 아이콘 터치 시 마우스 감도, 스크롤 방향, 화면 보호 시간 조절.
   - `[슬립 (🌙)]`: 초승달 아이콘 터치 시 하단 화면 즉시 블랙아웃(화면 숨김), 화면 재터치 시 오클릭 없이 깨우기.

---

## 4. PortMaster 게임 런처 연동 방식 (.sh 주입)

```bash
# === [WhimPad Hook Start] ===
if [ -f "$GAMEDIR/whimpad/whim_hook.sh" ]; then
  source "$GAMEDIR/whimpad/whim_hook.sh"
fi
# === [WhimPad Hook End] ===

# 메인 게임 실행
$GAMEDIR/game.bin ...

# === [WhimPad Cleanup] ===
if [ -n "$WHIM_BACKEND_PID" ]; then kill $WHIM_BACKEND_PID 2>/dev/null || true; fi
if [ -n "$WHIM_GESTURE_PID" ]; then kill $WHIM_GESTURE_PID 2>/dev/null || true; fi
if [ -n "$WHIM_UI_PID" ]; then kill $WHIM_UI_PID 2>/dev/null || true; fi
swaymsg output DSI-1 power off >/dev/null 2>&1 || true
# =========================
```

---

## 5. 프로젝트 구조 및 버전/릴리즈 규칙

### 5.1 디렉토리 구조
```text
whimtouchpad/
├── .github/
│   └── workflows/
│       └── release.yml          # 마이너 버전(v*.X.0.0) 태그 푸시 시 dist 자동 빌드 & GitHub Release
├── src/                         # 보조패드 코어 소스
├── scripts/
│   ├── build.mjs               # pnpm build 실행기 (산출물 패키징)
│   └── clean.mjs               # 정리 스크립트
├── template/
│   ├── conf/config.json        # 기본 설정 (민감도, 키 매핑)
│   └── whimtouchpad.sh         # PortMaster 런처 훅 스크립트
├── GEMINI.md                    # 4자리 버전 및 커밋 룰
├── package.json
├── pnpm-lock.yaml
└── README.md
```

### 5.2 버전 체계 및 자동 릴리즈 규칙
- **4자리 버전 관리 체계**: `Major.Minor.Patch.Revision` (예: `v0.1.0.0`)
  - **1 (Major)**: 대규모 아키텍처 개편, 하위 호환성 단절 등 (하위 전부 `0` 리셋)
  - **2 (Minor)**: **새로운 세션 시작 / 핵심 기능 단위 작업 (깃허브 태그 자동 릴리즈 대상)**
  - **3 (Patch)**: 사용자가 직접 "커밋해줘"라고 명시적 요청 시
  - **4 (Revision)**: 에이전트(AI)가 자체 판단하여 작업 후 커밋 시
- **GitHub Actions 자동 릴리즈**:
  - 마이너 버전 태그(`v*.X.0.0`)가 푸시되면 워크플로우가 트리거되어 `pnpm run build` 실행 ➔ `dist/whimtouchpad-v*.zip` 생성 ➔ GitHub Releases에 자동 배포.

---

## 6. 개발 로드맵

| 단계 | 목표 | 주요 작업 내용 |
| :--- | :--- | :--- |
| **Phase 1** | **프로젝트 기본 세팅 & CI/CD** | - `package.json`, `pnpm` 환경 구성<br>- `GEMINI.md` 버전 규칙 적용<br>- `scripts/build.mjs`, `clean.mjs`<br>- 마이너 태그 전용 GitHub Actions `release.yml` 작성 |
| **Phase 2** | **초경량 렌더링 & UI 프로토타입** | - SDL2 또는 Framebuffer 기반 렌더링 루프 구현 (RAM < 15MB 타겟)<br>- 트랙패드 모드 및 키패드 그리드 모드 구현<br>- `config.json` 매핑 파서 |
| **Phase 3** | **Linux uinput 가상 입력 엔진** | - `/dev/uinput` 마우스 상대이동/클릭 및 키보드 신호 방출 구현<br>- PortMaster 훅 스크립트(`whimtouchpad.sh`) 작성 |
| **Phase 4** | **빌드 자동화 및 패키징 검증** | - `dist/whimtouchpad.zip` 생성 검증<br>- 마이너 버전 태그 자동 빌드/릴리즈 테스트 |
