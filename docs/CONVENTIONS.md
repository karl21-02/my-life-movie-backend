# Backend Development Conventions

이 문서는 My Life Movie 백엔드 저장소의 협업 기준을 정의한다. 모든 팀원은 기능 개발, 버그 수정, 문서 작업, 배포 준비 시 이 기준을 기본 규칙으로 따른다.

## 1. Git Workflow

### Branch Roles

| Branch | Purpose | Rule |
|---|---|---|
| `main` | 배포 가능한 안정 버전 | 직접 push 금지, PR merge만 허용 |
| `develop` | 다음 배포를 위한 통합 브랜치 | 기능 브랜치의 기본 base |
| `feature/*` | 신규 기능 개발 | `develop`에서 분기하고 `develop`으로 PR |
| `fix/*` | 일반 버그 수정 | `develop`에서 분기하고 `develop`으로 PR |
| `hotfix/*` | 운영 긴급 수정 | `main`에서 분기하고 `main`, `develop`에 반영 |
| `release/*` | 릴리스 안정화 | `develop`에서 분기하고 최종적으로 `main`에 merge |
| `docs/*` | 문서 변경 | 변경 범위에 따라 `develop` 또는 관련 브랜치로 PR |
| `chore/*` | 설정, 의존성, 빌드 작업 | 기능 변경과 분리 |

### Branch Naming

브랜치 이름은 소문자 kebab-case를 사용한다. 공백, 한글, 특수문자는 사용하지 않는다.

```text
<type>/<issue-number>-<short-description>
```

예시:

```text
feature/12-file-upload-api
fix/18-health-check-status
docs/21-backend-conventions
chore/24-update-ci
hotfix/31-openai-timeout
```

이슈가 없는 작은 작업이라도 가능하면 이슈를 먼저 만들고 연결한다. 정말 단순한 오탈자 수정만 예외로 둘 수 있다.

## 2. Commit Convention

커밋 메시지는 Conventional Commits 형식을 따른다.

```text
<type>(<scope>): <subject>
```

### Commit Types

| Type | Usage |
|---|---|
| `feat` | 사용자에게 보이는 신규 기능 |
| `fix` | 버그 수정 |
| `docs` | 문서 변경 |
| `style` | 포맷팅, 세미콜론 등 동작 변경 없는 수정 |
| `refactor` | 동작 변경 없는 구조 개선 |
| `test` | 테스트 추가 또는 수정 |
| `chore` | 기타 관리 작업 |
| `build` | 빌드 시스템, 패키지 변경 |
| `ci` | GitHub Actions 등 CI 설정 |
| `perf` | 성능 개선 |
| `revert` | 이전 커밋 되돌림 |

### Backend Scopes

권장 scope:

```text
api, app, config, ci, docs, deps, health, parser, ai, spotify, openai, test
```

예시:

```text
feat(api): add movie generation endpoint
fix(health): return stable health response
docs(docs): add backend development conventions
ci(test): run pytest in pull requests
chore(deps): update fastapi dependency
```

규칙:

- subject는 72자 이내로 작성한다.
- 마침표로 끝내지 않는다.
- 한 커밋에는 하나의 목적만 담는다.
- 변경 이유가 중요하면 본문에 `why`와 `impact`를 적는다.
- 이슈 연결은 footer에 `Closes #12`, `Refs #18` 형식으로 적는다.

## 3. Pull Request Rules

PR은 리뷰 가능한 크기로 유지한다. 기능 구현, 리팩터링, 문서 변경, 의존성 변경은 가능하면 별도 PR로 분리한다.

PR 작성 기준:

- PR 제목은 커밋 컨벤션과 비슷한 형식을 권장한다.
- 관련 이슈를 반드시 연결한다.
- 변경 사항, 검증 방법, 영향 범위를 적는다.
- API 계약이 바뀌면 README 또는 API 문서도 함께 수정한다.
- CI가 통과한 뒤 리뷰 요청을 보낸다.
- 리뷰어 최소 1명의 승인을 받은 뒤 merge한다.

Merge 기준:

- `main`, `develop` 직접 push 금지
- 기본 전략은 squash merge
- merge 후 원격 feature 브랜치 삭제
- 충돌 해결 시 기존 변경을 임의로 되돌리지 않는다

## 4. Logging Standard

백엔드 로그는 장애 분석, 외부 API 추적, 데이터 처리 상태 확인을 위해 남긴다. 개인정보와 원본 사용자 데이터 보호를 최우선으로 한다.

### Log Levels

| Level | Usage |
|---|---|
| `DEBUG` | 로컬 개발용 상세 상태. 운영 환경 기본 비활성화 |
| `INFO` | 정상적인 주요 처리 흐름 |
| `WARNING` | 복구 가능한 문제, 재시도, 비정상 입력 |
| `ERROR` | 요청 실패, 외부 API 실패, 처리 불가 예외 |
| `CRITICAL` | 서비스 지속이 어려운 장애 |

### Required Fields

운영 로그는 가능한 한 구조화된 형태로 남긴다.

```json
{
  "timestamp": "2026-05-07T12:00:00Z",
  "level": "INFO",
  "service": "my-life-movie-backend",
  "environment": "dev",
  "request_id": "req_123",
  "event": "movie_generation_started",
  "module": "app.api.movie",
  "status_code": 200,
  "duration_ms": 320
}
```

필수 기준:

- `timestamp`는 UTC ISO 8601 형식을 사용한다.
- 요청 단위 추적을 위해 `request_id`를 포함한다.
- 외부 API 호출은 provider, endpoint, duration, retry_count, result만 남긴다.
- 예외 로그에는 error type, error code, stack trace를 포함하되 민감정보는 제거한다.

### Sensitive Data Rules

아래 정보는 로그에 남기지 않는다.

- 업로드된 이력서 원문, PDF OCR 전문
- 카카오톡 대화 원문
- Spotify OAuth token, refresh token
- OpenAI API key, Spotify client secret
- 사용자 이메일, 전화번호, 주소 등 직접 식별자
- 개인 데이터가 포함된 전체 프롬프트

필요하면 해시 또는 마스킹을 사용한다.

```text
user_id_hash=sha256(user_id)
email=ki***@example.com
```

### Event Naming

이벤트 이름은 snake_case 동사형으로 작성한다.

```text
app_started
request_received
file_upload_received
resume_parse_completed
chat_parse_failed
movie_generation_started
movie_generation_completed
external_api_retry
external_api_failed
```

`print()`는 사용하지 않는다. Python 표준 `logging` 또는 프로젝트 공통 logger를 사용한다.

## 5. Issue and Label Rules

기본 라벨:

| Label | Meaning |
|---|---|
| `bug` | 버그 |
| `enhancement` | 기능 개선 또는 신규 기능 |
| `docs` | 문서 |
| `backend` | 백엔드 관련 |
| `api` | API 계약 관련 |
| `ai` | AI 분석, 프롬프트, 모델 관련 |
| `infra` | CI, 배포, 환경 설정 |

이슈는 문제 배경, 기대 결과, 완료 조건을 포함해야 한다. 버그 이슈는 재현 절차와 실제 결과를 포함한다.

## 6. Definition of Done

작업 완료 기준:

- 요구사항이 구현되었다.
- 예외 케이스가 처리되었다.
- 필요한 테스트가 추가 또는 수정되었다.
- `uv run pytest` 또는 합의된 검증 명령이 통과한다.
- API 변경 시 문서가 갱신되었다.
- PR 템플릿 체크리스트가 충족되었다.

## 7. CI Standard

백엔드 CI는 최소한 다음을 검증해야 한다.

```text
uv sync
uv run pytest
uv run python -m py_compile app/main.py
```

테스트가 없는 상태를 장기간 허용하지 않는다. 테스트 스캐폴드가 추가된 뒤에는 테스트 실패를 `echo`로 무시하지 않는다.
