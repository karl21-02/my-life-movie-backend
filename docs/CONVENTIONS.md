# Backend Development Conventions

이 문서는 My Life Movie 백엔드 저장소의 협업 기준을 정의한다. 기능 개발, 버그 수정, 문서 작업, 배포 준비는 이 기준을 기본 규칙으로 따른다.

## 1. 기본 원칙

- `develop` 기준으로 이슈를 만들고, 이슈 번호 기반 브랜치에서 작업한다.
- 라우터는 HTTP 계약만 담당하고, 비즈니스 로직은 service, DB 접근은 repository로 분리한다.
- 예외 응답은 Problem Details 스타일로 통일한다.
- 로그는 구조화 로그로 남기고, 원문 사용자 입력과 토큰은 남기지 않는다.
- 운영에서 필요한 설정은 `.env.example`에 문서화하되 실제 secret은 커밋하지 않는다.
- 주석, 문서, 사용자에게 보이는 메시지는 한국어로 작성한다.

## 2. Git Workflow

| Branch | Purpose | Rule |
| --- | --- | --- |
| `main` | 배포 가능한 안정 버전 | 직접 push 금지, PR merge만 허용 |
| `develop` | 다음 배포를 위한 통합 브랜치 | 기능 브랜치의 기본 base |
| `feature/*` | 신규 기능 개발 | `develop`에서 분기하고 `develop`으로 PR |
| `fix/*` | 일반 버그 수정 | `develop`에서 분기하고 `develop`으로 PR |
| `hotfix/*` | 운영 긴급 수정 | `main`에서 분기하고 `main`, `develop`에 반영 |
| `release/*` | 릴리스 안정화 | `develop`에서 분기하고 최종적으로 `main`에 merge |
| `docs/*` | 문서 변경 | 변경 범위에 따라 `develop` 또는 관련 브랜치로 PR |
| `chore/*` | 설정, 의존성, 빌드 작업 | 기능 변경과 분리 |

브랜치 이름은 소문자 kebab-case를 사용한다.

```text
<type>/<issue-number>-<short-description>
```

예시:

```text
feature/43-video-prompt-quality
fix/31-refresh-token-rotation
docs/45-backend-conventions
chore/52-update-ci
```

## 3. 커밋 컨벤션

커밋 메시지는 Conventional Commits 형식을 유지하되, 제목은 한국어로 작성한다.

```text
<type>(<scope>): <한국어 제목>
```

권장 scope:

```text
api, auth, config, db, docs, docker, errors, logging, movie, music, recommendation, storage, test, video, worker
```

예시:

```text
feat(video): 영상 생성 상태 조회 추가
fix(auth): refresh token 재사용 탐지 보정
docs(db): ERD 문서 정리
test(movie): 추천 영화 저장소 테스트 추가
```

규칙:

- 제목은 한국어로 72자 이내로 작성한다.
- 마침표로 끝내지 않는다.
- 한 커밋에는 하나의 목적만 담는다.
- 변경 이유가 중요하면 본문에 `왜`와 `영향`을 적는다.
- 이슈 연결은 footer에 `Closes #12`, `Refs #18` 형식으로 적는다.

## 4. Pull Request Rules

- PR 제목은 커밋 컨벤션과 유사한 형식을 사용한다.
- 관련 이슈를 반드시 연결한다.
- 변경 사항, 검증 방법, 영향 범위를 적는다.
- API 계약이 바뀌면 Swagger 설명, README, 관련 문서를 함께 수정한다.
- DB 스키마가 바뀌면 Alembic migration과 migration 테스트를 포함한다.
- CI가 통과한 뒤 리뷰 요청을 보낸다.
- 리뷰어 최소 1명의 승인을 받은 뒤 merge한다.
- 기본 전략은 일반 merge commit이다.
- merge 후 원격 feature 브랜치는 삭제한다.

## 5. 아키텍처 패턴

| Layer | 위치 | 책임 |
| --- | --- | --- |
| Router | `app/routers`, `app/api/*/router.py` | HTTP 요청/응답, Depends, status code, schema 연결 |
| Schema | `app/schemas`, `app/api/*/schemas.py` | Pydantic 요청/응답 계약 |
| Service | `app/services` | 비즈니스 규칙, 외부 provider 조합, 상태 전이 |
| Repository | `app/repositories` | DB 조회/저장, Redis 저장소 접근 |
| Model | `app/models` | SQLAlchemy 테이블 정의 |
| Worker | `app/workers`, `app/services/*worker*` | 비동기 Job 처리 |
| Core | `app/core` | 설정, 인증 dependency, 공통 예외, 로깅, middleware |

라우터 규칙:

- 라우터 안에서 복잡한 provider 호출, ranking, 파일 저장 로직을 직접 작성하지 않는다.
- `Depends(get_current_user)`로 인증을 통일한다.
- 소유권 검사는 repository 조회 후 service 또는 공통 helper에서 명시적으로 처리한다.
- 응답 모델은 가능한 한 `response_model`로 고정한다.
- Swagger summary/description은 한국어로 명시한다.

Service 규칙:

- 상태 전이가 있는 로직은 service에서 처리한다.
- provider 연동은 interface 또는 adapter로 감싼다.
- OpenAI, TMDB, Spotify, S3 호출 실패는 명확한 실패 정책을 둔다.
- 가짜 성공 데이터를 반환해 실패를 숨기지 않는다.

Repository 규칙:

- repository는 DB 쿼리와 영속화만 담당한다.
- HTTPException, Request, Response를 repository에 넘기지 않는다.
- 다중 row 교체 작업은 transaction 경계를 고려한다.

## 6. API와 에러 응답

에러 응답은 Problem Details 스타일을 유지한다.

```json
{
  "type": "auth_required",
  "title": "Authentication Required",
  "status": 401,
  "detail": "Bearer access token이 필요합니다.",
  "instance": "/api/movies",
  "code": "AUTH_REQUIRED",
  "request_id": "req_123",
  "errors": []
}
```

상태 코드 기준:

- 인증 실패: `401 AUTH_REQUIRED`
- 권한 없음: `403 *_FORBIDDEN`
- 리소스 없음: `404 *_NOT_FOUND`
- 상태 충돌: `409 *_CONFLICT`
- validation 실패: `422 VALIDATION_ERROR`
- 예상하지 못한 서버 오류: `500 INTERNAL_SERVER_ERROR`

## 7. Logging Standard

백엔드 로그는 장애 분석, provider 추적, 요청 흐름 확인을 위해 남긴다. 개인정보와 원본 사용자 데이터 보호를 최우선으로 한다.

| Level | Usage |
| --- | --- |
| `DEBUG` | 로컬 개발용 상세 상태. 운영 기본 비활성화 |
| `INFO` | 앱 시작, 요청 완료, 주요 정상 흐름 |
| `WARNING` | validation 실패, 인증 실패, 재시도 가능 오류, fallback 처리 |
| `ERROR` | 외부 API 실패, 처리 불가 요청, 핸들링된 서버 오류 |
| `CRITICAL` | 앱 기동 불가, 필수 설정 누락, 서비스 지속 불가 장애 |

구조화 로그 예시:

```json
{
  "timestamp": "2026-05-13T12:00:00Z",
  "level": "INFO",
  "service": "my-life-movie-backend",
  "environment": "production",
  "event": "request_completed",
  "request_id": "req_123",
  "path": "/api/movies/1/generation",
  "method": "GET",
  "status_code": 200,
  "duration_ms": 42.3
}
```

외부 API 로그는 provider, operation, duration_ms, status/result, retry_count, error_code 중심으로 남긴다.

로그 금지 정보:

- access token, refresh token, API key, client secret
- password, password_hash
- 이메일, 전화번호, 주소 등 직접 식별자
- 업로드 파일 원문, PDF/OCR 전문, 영상/이미지 바이너리
- AI 프롬프트 전문, 사용자 인생 이야기 원문
- S3 presigned URL 전체 문자열

이벤트 이름은 snake_case로 작성한다.

```text
app_started
request_completed
auth_login_succeeded
refresh_token_rotated
movie_generation_requested
video_generation_started
video_generation_progress_updated
video_generation_failed
movie_recommendation_created
external_api_failed
```

`print()`는 사용하지 않는다. 프로젝트 공통 logger를 사용한다.

## 8. DB와 Migration

- DB 스키마 변경은 반드시 Alembic migration으로 반영한다.
- migration 파일명은 변경 목적이 드러나게 작성한다.
- model 변경과 migration을 같은 PR에 포함한다.
- 운영 배포 전에는 RDS 대상으로 `alembic upgrade head`를 실행한다.
- 서버 시작만으로 DB 스키마가 자동 반영된다고 가정하지 않는다.

검증:

```bash
uv run pytest tests/integration/db/test_alembic_migrations.py
uv run python -m compileall -q app migrations tests
```

## 9. 인증과 보안

- refresh token 원문은 저장하지 않고 hash만 저장한다.
- refresh token은 rotation 방식으로 운영한다.
- 이미 회전/폐기/만료된 token 재사용은 보안 이벤트로 취급한다.
- access token TTL, refresh token TTL은 설정값으로 관리한다.
- 인증 cookie는 `HttpOnly`, `SameSite=Lax`, 운영 `Secure=true` 기준을 따른다.
- 운영 secret은 `.env`, GitHub, Slack, PR 본문에 노출하지 않는다.

## 10. 영상 생성과 Worker

- API 서버는 생성 요청을 Job으로 저장하고 즉시 응답한다.
- 실제 provider 호출은 worker가 처리한다.
- Job 상태는 `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELED`를 사용한다.
- `movies.status`는 화면용 대표 상태이고, 정확한 생성 원장은 `video_generation_jobs`다.
- provider 실패는 `error_code`, `error_message`에 저장한다.
- 긴 영상은 단일 Job을 무리하게 늘리지 말고 scene job 구조를 새로 설계한다.

## 11. Storage

- 로컬 개발은 `STORAGE_PROVIDER=local`을 사용할 수 있다.
- 운영은 `STORAGE_PROVIDER=s3`를 기본으로 한다.
- 대용량 영상 다운로드는 presigned URL 또는 CDN을 우선 고려한다.
- DB에는 다운로드 응답에 필요한 URL 또는 key만 저장한다.
- presigned URL 전체는 로그에 남기지 않는다.

## 12. 테스트 기준

기본 검증:

```bash
uv run pytest
uv run python -m compileall -q app migrations tests
git diff --check
```

| 유형 | 위치 | 기준 |
| --- | --- | --- |
| unit | `tests/unit` | service, repository, provider adapter 단위 검증 |
| integration | `tests/integration` | DB migration, API 계약, 주요 flow 검증 |
| legacy/simple | `tests/test_*.py` | 기존 테스트 유지, 점진적으로 unit/integration으로 이동 |

새 기능 최소 테스트:

- 정상 케이스 1개
- 권한/소유권 실패 1개
- 외부 provider 실패 또는 timeout 1개
- DB 저장/상태 전이 검증 1개

## 13. 안티 패턴

금지 또는 지양한다.

- 라우터 함수 안에 긴 비즈니스 로직을 직접 작성
- DB query를 여러 라우터에 복붙
- `print()`로 운영 로그 작성
- broad `except Exception` 후 조용히 성공 응답 반환
- provider 실패를 빈 추천/가짜 데이터로 숨기기
- token, password, prompt 전문, presigned URL을 로그에 남기기
- migration 없이 model만 수정
- 테스트에서 실제 OpenAI/TMDB/S3를 기본 호출
- `.env` 실제 값을 커밋하거나 PR 본문에 붙여넣기
- Docker local DB 기준 값을 운영 RDS 설정으로 착각
- `movies.status`만 보고 최신 생성 Job 상태라고 가정
- 하드코딩된 provider payload를 service 곳곳에 흩뿌리기

## 14. Definition of Done

- 요구사항이 구현되었다.
- 예외 케이스와 권한 케이스가 처리되었다.
- 필요한 테스트가 추가 또는 수정되었다.
- `uv run pytest`, `compileall`, `git diff --check`가 통과한다.
- API 변경 시 Swagger와 문서가 갱신되었다.
- DB 변경 시 migration과 migration 검증이 포함되었다.
- PR 템플릿 체크리스트가 충족되었다.
- 이슈에 작업 결과와 검증 내역을 최신화했다.

## 15. CI Standard

백엔드 CI는 최소한 다음을 검증해야 한다.

```text
uv sync --frozen
uv run pytest
uv run python -m compileall -q app migrations tests
git diff --check
```

테스트 실패를 `echo`나 `|| true`로 무시하지 않는다.
