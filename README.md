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

## PortMaster 연동 및 설치 가이드 (공통 런타임 방식)

WhimPad는 **공통 런타임 공유 방식**으로 배포되어, 게임마다 무거운 바이너리와 폰트를 중복 복사할 필요 없이 기기에 **단 1회만 설치**하면 모든 게임에서 공유할 수 있습니다.

```text
/roms/ports/
├── whimpad/                          # [공통 런타임: 기기당 1회 설치]
│   ├── whimpad_backend
│   ├── whim_hook.sh
│   ├── whim_cleanup.sh
│   └── ...
├── StardewValley.sh                  # 게임 런처 (공통 훅 연동)
└── stardewvalley/
    └── whimpad.xml                   # [게임별 단축키 레이아웃: 선택 사항]
```

---

### 1단계: WhimPad 공통 런타임 설치 (기기당 1회)

릴리즈 페이지에서 `whimpad-v*.zip`을 다운로드하여 기기의 `/roms/ports/`에 압축 해제합니다.

```bash
# [예시] Mac/PC 터미널에서 RGDS 기기로 복사 시
scp dist/whimpad-v*.zip root@<기기_IP>:/roms/ports/
# 기기 SSH 접속 후 압축 해제 및 실행 권한 부여
cd /roms/ports && unzip whimpad-v*.zip
chmod +x /roms/ports/whimpad/whim_hook.sh
chmod +x /roms/ports/whimpad/whim_cleanup.sh
chmod +x /roms/ports/whimpad/whimpad_backend
```

> **버전 업데이트 시**: 새 버전 ZIP을 `/roms/ports/`에 덮어쓰기만 하면 설치된 모든 게임에 즉시 최신 WhimPad가 적용됩니다.

---

### 2단계: 게임 실행 스크립트(`.sh`) 연동

원하는 게임의 런처 스크립트(예: `/roms/ports/StardewValley.sh`)를 열어 실행 직전과 직후에 훅을 추가합니다.

#### ① 게임 바이너리 실행 직전:
```bash
# === [WhimPad Hook Start] ===
WHIMPAD_DIR="/roms/ports/whimpad"
[ -d "$WHIMPAD_DIR" ] || [ ! -d "/roms2/ports/whimpad" ] || WHIMPAD_DIR="/roms2/ports/whimpad"
if [ -f "$WHIMPAD_DIR/whim_hook.sh" ]; then
  source "$WHIMPAD_DIR/whim_hook.sh"
fi
# === [WhimPad Hook End] ===
```

#### ② 게임 실행 종료 직후 (`exit 0` 바로 윗줄):
```bash
# === [WhimPad Cleanup] ===
if [ -f "$WHIMPAD_DIR/whim_cleanup.sh" ]; then
  source "$WHIMPAD_DIR/whim_cleanup.sh"
fi
# =========================
```

*(자세한 예시는 `/roms/ports/whimpad/templates/game_hook_snippet.sh` 참고)*

---

### 3단계 (선택): 게임별 커스텀 단축키 레이아웃 구성

특정 게임에 맞춘 전용 단축키 패널을 추가하고 싶다면, 게임 디렉토리(예: `/roms/ports/stardewvalley/whimpad.xml`)에 XML 파일을 배치하기만 하면 됩니다. WhimPad가 이를 자동 인식하여 상단 5번째 탭에 게임 전용 버튼들을 로드합니다.

- 템플릿 파일: `/roms/ports/whimpad/templates/custom_layout.sample.xml` 복사 후 편집.

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
