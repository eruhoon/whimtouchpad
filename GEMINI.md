# 프로젝트 규칙 (Project Rules)

## 패키지 매니저 규칙
- 이 프로젝트의 기본 패키지 매니저는 **`pnpm`**입니다.
- 패키지 설치(`pnpm install`, `pnpm add`), 스크립트 실행(`pnpm run build`, `pnpm test`) 등 모든 종속성 및 태스크 실행은 `npm` 대신 `pnpm`을 우선 사용합니다.

---

## 버전 관리 및 커밋 규칙 (`Major.Minor.Patch.Revision`)

이 프로젝트는 `Major.Minor.Patch.Revision` (4자리 체계, 예: `v0.1.0.0`) 버전 관리 규칙을 따릅니다.

### 1. 버전 체계 및 트리거

| 자리 | 이름 | 트리거 (올리는 시점) | 하위 버전 리셋 룰 |
| :--- | :--- | :--- | :--- |
| **1 (Major)** | **Major** | 대규모 아키텍처 개편, 하위 호환성 단절 등 | Minor, Patch, Revision ➔ `0` |
| **2 (Minor)** | **Minor** | **새로운 세션 시작 / 핵심 기능 단위 작업** (깃허브 태그 자동 릴리즈 대상) | Patch, Revision ➔ `0` |
| **3 (Patch)** | **Patch** | **사용자가 직접 "커밋해줘"라고 명시적 요청 시** | Revision ➔ `0` |
| **4 (Revision)** | **Revision** | **프로젝트 내 코드 변경 발생 시 무조건 커밋 및 Revision +1 (`x.x.x.+1`)** | 다음 Patch/Minor 시 리셋 |

---

### 2. 커밋 메시지 및 단일 커밋 규칙

- **언어 규칙**: 커밋 메시지는 **영어(English)**로 작성합니다.
- **버전 노출 규칙**: 내부적으로는 4자리(`Major.Minor.Patch.Revision`, 예: `0.2.0.1`) 체계를 사용하지만, **평소 외부 노출(커밋 메시지, Git 릴리즈 태그, 아티팩트명)에는 패치까지만 3자리(`vMajor.Minor.Patch`, 예: `v0.2.0`)로 노출**합니다.
- 커밋 메시지 제목에는 별도의 `[vX.Y.Z]` 태그를 붙이지 않고 Conventional Commits 형식을 깔끔하게 유지합니다.

#### 코드 변경 시 커밋 규칙 (Revision 증가 & 단일 커밋)
- **무조건 커밋 원칙**: 프로젝트 내에 코드나 파일 변경이 발생하면 **무조건 커밋**을 진행합니다.
- **Revision 버전 증가**: 커밋 전 `package.json`의 version에서 Revision 값을 1 올립니다 (`x.x.x.+1`).
- **단일 커밋(Single Commit)**: 커밋을 나누지 않고, **코드 변경 사항과 버전 갱신(`package.json`)을 반드시 하나의 커밋으로 묶어서 진행**합니다.
- **형식**: `<type>: <description in English>`
- **예시**: `fix: handle missing touch release event`

#### 사용자가 직접 "커밋해줘" 요청 시 (Patch)
- 사용자가 명시적으로 "커밋해줘" 요청 시 Patch 버전을 증가시키며(`x.x.+1.0`, Revision은 0으로 리셋), 마찬가지로 변경 사항과 버전 갱신을 분리하지 않고 **하나의 커밋**으로 처리합니다.
- 형식: `<type>: <description in English>`

---

### 3. 프로젝트 메타데이터 연동 및 자동 릴리즈

- `package.json`의 `version` 필드는 코드 변경 시마다 Revision이 반영되어 함께 갱신됩니다 (내부 4자리 `0.X.Y.Z` 유지).
- **마이너(Minor) 버전이 갱신되는 경우 (`v0.X.0`)**, Git 태그(`v0.X.0`)가 생성되어 GitHub Actions를 통해 `dist/` 산출물이 포함된 GitHub Release가 자동 빌드 및 배포됩니다.
