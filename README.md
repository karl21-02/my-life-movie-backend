<div align="center">

# 🎬 My Life Movie

**내 이야기와 첨부 자료를 AI가 정리해서, 나만의 인생 영화를 만들어주는 서비스**

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org/)
[![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com/)

[Features](#-features) • [Tech Stack](#-tech-stack) • [Getting Started](#-getting-started) • [Roadmap](#-roadmap) • [Team](#-team)

</div>

---

## 💡 Vision

> **" 사용자가 들려준 인생 이야기와 사진·영상·문서를 AI가 정리하여
> 장면, 분위기, 음악 방향이 담긴 나만의 인생 영화 생성 입력으로 만들어 드립니다. "**

| | |
|---|---|
| **Product** | My Life Movie (AI 기반 개인 맞춤형 콘텐츠 생성 서비스) |
| **Target Users** | 자신의 이야기를 특별한 콘텐츠로 표현하고 공유하고 싶은 MZ세대, 나의 인생을 내가 아닌 색다르고 다양한 시점으로 바라보고 싶은 사람. |
| **Problem** | 흩어져 있는 자신의 기억, 사진, 영상, 문서를 의미 있는 하나의 서사로 모아보고 싶은 니즈. |
| **Key Benefit** | 자신의 인생을 제3자의 시점(영화 장르 및 줄거리)에서 바라보는, 색다른 경험과 시각적 콘텐츠를 제공. |
| **Differentiation** | 단순 텍스트 요약이 아니라, 대화 기반 스토리 구조화와 첨부 자산 분석을 결합해 영상 생성용 입력을 표준화. |

---

## ✨ Features

### 📊 다중 입력 소스 분석
사용자 대화, 사진, 영상, 문서, 선택한 테마와 음악을 영상 생성 입력으로 정규화.

### 🧠 AI 기반 스토리 구조화
AI 역질문을 통해 사용자의 인생 이야기를 `story_brief`, `scene_plan`, `generation_prompt`로 정리.

### 🎬 영상 생성 준비 파이프라인
생성 Job, 상태 조회, 표준 `VideoGenerationInput`, DB 큐 worker, fal.ai provider 연동을 기반으로 실제 영상 생성까지 처리.

---

## 🎯 Goals & Scope

### Goals
- 생성 요청부터 Job 접수와 상태 조회까지의 흐름을 안정화.
- 사용자의 이야기가 영상 생성 가능한 장면/스타일/프롬프트로 정리되는 품질 확보.

### In-Scope
- 다양한 형식(JPG, PNG, MP4, MOV, PDF, TXT 등)의 입력 수집 기반 구현.
- FastAPI 기반 인증, 영화 생성 입력, Job 상태 관리 API 구현.
- OpenAI 기반 스토리 구조화와 영상 생성용 프롬프트 정규화.
- 유저 스토리와 첨부 자산을 영상 생성용 입력으로 정규화하는 Job/상태 관리 및 worker 기반 구축.

### Out-of-Scope
- 사용자 트래픽 대응을 위한 인프라 확장성 테스트.

---

## 🛠 Tech Stack

| Category | Technologies |
|----------|-------------|
| **Backend** | Python FastAPI |
| **AI** | OpenAI 기반 스토리 구조화, fal.ai 기반 영상 생성, 영상 생성 입력 정규화 |
| **API** | FastAPI, OpenAI, Spotify 추천 API |

---

## 🚀 Getting Started

```bash
# Clone the repository
git clone https://github.com/karl21-02/my-life-movie-backend.git

# Navigate to project directory
cd my-life-movie-backend

# Install dependencies
uv sync

# Run the server
uv run uvicorn app.main:app --reload
```

### Docker Compose로 실행

```bash
# 환경 변수 예시 파일 복사
cp .env.example .env

# 백엔드 개발 서버 실행
docker compose up --build
```

기본 주소는 `http://localhost:8000`이고, 상태 확인은 `http://localhost:8000/health`에서 할 수 있습니다. Compose 실행 시 `APP_ENV=local`, `LOG_LEVEL=DEBUG`, 프론트 개발 서버용 CORS origin, MySQL 개발 DB, Redis refresh token store가 기본으로 적용됩니다.

| Service | URL |
|---------|-----|
| Backend API | http://localhost:8000 |
| Backend Health Check | http://localhost:8000/health |
| MySQL | localhost:3307 |
| Redis | localhost:6379 |

### 영상 생성 provider

로컬 기본값은 `VIDEO_GENERATION_PROVIDER=auto`입니다. `OPENAI_API_KEY`가 있으면 OpenAI 영상 provider를 우선 사용하고, OpenAI 키가 없고 `FAL_KEY`가 있으면 fal.ai queue API를 사용합니다. 두 키가 모두 비어 있으면 mock provider로 동작합니다.

```env
VIDEO_GENERATION_PROVIDER=auto
OPENAI_API_KEY=your-openai-api-key
OPENAI_VIDEO_MODEL=sora-2
OPENAI_VIDEO_SIZE=1280x720
OPENAI_VIDEO_SECONDS=4
FAL_KEY=your-fal-api-key
FAL_MODEL_ID=fal-ai/wan-alpha
```

worker는 Docker Compose에서 `my-life-movie-video-worker` 서비스로 실행됩니다. 수동 실행이 필요하면 다음 명령을 사용합니다.

```bash
uv run python -m app.workers.video_generation_worker
```

영상 생성 확인 흐름:

1. `POST /api/movies/draft`
2. `POST /api/movies/{movie_id}/chat`
3. `POST /api/movies/{movie_id}/generate`
4. `GET /api/movies/{movie_id}/generation`

### 생성 영상 저장소

개발 기본값은 로컬 저장소입니다. 생성된 영상은 `generated/videos`, 썸네일은 `generated/thumbnails`에 저장되고, 다운로드는 백엔드의 `/api/movies/{movie_id}/download/file` 응답을 통해 처리합니다.

운영에서는 `STORAGE_PROVIDER=s3`를 사용합니다. 이 경우 생성 결과는 S3에 저장되고, 다운로드 요청 시 백엔드는 파일을 직접 스트리밍하지 않고 짧은 만료 시간을 가진 presigned GET URL을 발급합니다. 대용량 영상 다운로드 트래픽은 백엔드가 아니라 S3 또는 CloudFront가 담당합니다.

```env
STORAGE_PROVIDER=s3
AWS_REGION=ap-northeast-2
S3_BUCKET_NAME=your-generated-media-bucket
S3_PUBLIC_BASE_URL=https://cdn.example.com
S3_GENERATED_VIDEO_PREFIX=generated/videos
S3_GENERATED_THUMBNAIL_PREFIX=generated/thumbnails
S3_PRESIGNED_URL_EXPIRE_SECONDS=900
```

로컬 개발에서 IAM role을 쓰지 않는 경우에만 `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`를 설정합니다. 실제 키는 저장소에 커밋하지 않습니다.

### DB 마이그레이션

개발 DB가 실행 중일 때 Alembic으로 테이블을 생성합니다.

```bash
# 로컬에서 실행
uv run alembic upgrade head

# Docker Compose 컨테이너에서 실행
docker compose exec my-life-movie-backend uv run alembic upgrade head
```

현재 기본 스키마는 인증 개발을 위한 `users`, `auth_refresh_tokens` 테이블을 포함합니다.

### API 문서

FastAPI Swagger UI에서 인증 API 계약, 요청/응답 예시, Problem Details 에러 응답, bearer token 및 refresh cookie 사용 방식을 확인할 수 있습니다.

| 문서 | URL |
|------|-----|
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| OpenAPI JSON | http://localhost:8000/openapi.json |

### 테스트

테스트는 현업에서 많이 쓰는 계층 기준으로 분리합니다.

| Path | Purpose |
|------|---------|
| `tests/unit` | 모델, 서비스, 저장소, 순수 유틸 단위 검증 |
| `tests/integration/api` | FastAPI 라우트, 미들웨어, Problem Details 응답 검증 |
| `tests/integration/db` | Alembic 마이그레이션과 DB 스키마 검증 |
| `tests/conftest.py` | 공용 fixture, 테스트 DB 세션, API client override |
| `tests/factories.py` | 테스트 데이터 생성 helper |

```bash
# 전체 테스트
uv run pytest

# 단위 테스트만 실행
uv run pytest -m unit

# 통합 테스트만 실행
uv run pytest -m integration
```

### 인증 API

현재 인증 기능은 이메일/비밀번호 기반 회원가입, 로그인, access token 검증, refresh token 회전/폐기까지 연결되어 있습니다. Access token은 응답 body로 반환하고, refresh token은 `HttpOnly` 쿠키로만 전달합니다.

| Method | Path | Status |
|--------|------|--------|
| POST | `/auth/signup` | 사용자 생성, Argon2 비밀번호 해싱, access token 발급, refresh token 쿠키 설정 |
| POST | `/auth/login` | 비밀번호 검증, access token 발급, refresh token 쿠키 설정 |
| GET | `/auth/me` | `Authorization: Bearer <access_token>` 기반 현재 사용자 조회 |
| POST | `/auth/refresh` | `refresh_token` HttpOnly 쿠키 기반 refresh token 회전, 새 access token 발급, 쿠키 갱신 |
| POST | `/auth/logout` | 현재 refresh token 폐기 및 `refresh_token` 쿠키 삭제 |

### Access Token 정책

- Access token TTL 기본값은 `15분`입니다.
- 알고리즘은 `HS256`이며, 로컬 기본 secret은 개발용입니다. 운영 환경은 `ACCESS_TOKEN_SECRET_KEY`를 반드시 별도로 설정해야 합니다.
- 응답에는 `access_token`, `token_type`, `expires_in`, `user`를 반환합니다.
- `/auth/me`는 `Authorization: Bearer <access_token>` 헤더를 사용합니다.

### Refresh Token 정책

- 저장소에는 refresh token 원문을 저장하지 않고 `sha256` 해시만 저장합니다.
- 저장소는 `REFRESH_TOKEN_STORE`로 선택합니다. 기본값은 `mysql`이고, Docker Compose 로컬 환경은 `redis`를 사용합니다.
- Redis 저장소는 active token 만료 시점 이후에도 재사용 탐지를 위해 `REFRESH_TOKEN_REDIS_RETENTION_SECONDS`만큼 token metadata를 보존합니다.
- refresh token TTL 기본값은 `14일`입니다.
- 성공적으로 회전하면 기존 row는 `ROTATED`, 신규 row는 `ACTIVE` 상태가 됩니다.
- 이미 `ROTATED`, `REVOKED`, `EXPIRED` 상태인 token을 다시 사용하면 `401 REFRESH_TOKEN_REUSED`로 거부합니다.
- 쿠키 이름은 `refresh_token`, 속성은 `HttpOnly`, `SameSite=Lax`, `Path=/auth`입니다. 로컬 환경은 `Secure=false`, 운영 환경은 기본 `Secure=true`로 동작합니다.

## 📚 Docs

- [개발 컨벤션](docs/CONVENTIONS.md): Git 브랜치 전략, 커밋 컨벤션, PR 규칙, 로그 기준
- [영상 생성 Job 개발 계획](docs/video-generation-job-plan.md): 영상 생성 Job, 상태 관리, 입력 정규화, 멀티 분석 에이전트 확장 설계

---

## 🗺 Roadmap

### Phase 1: 기획 및 설계 (Week 1-2)
| Week | Tasks |
|------|-------|
| Week 1 | 요구사항 정의 및 프로젝트 범위(Scope) 확정, 역할 분담 |
| Week 2 | 시스템 아키텍처 설계, API 명세서 작성, UI/UX 와이어프레임 설계, Git 저장소 및 브랜치 전략(Git Flow 등) 초기 세팅 |

### Phase 2: 인프라 구축 및 데이터 수집 (Week 3-4)
| Week | Tasks |
|------|-------|
| Week 3 | FastAPI 기본 프로젝트 세팅, Docker/AWS/Vercel 기반 개발·배포 환경 구축 |
| Week 4 | 사진·영상·문서 업로드 기반, 음악 추천 API, 사용자 입력 수집 흐름 구현 |

### Phase 3: AI 스토리 구조화 및 입력 정규화 (Week 5-6)
| Week | Tasks |
|------|-------|
| Week 5 | AI 역질문 기반 스토리 구조화, `story_brief`, `scene_plan`, `generation_prompt` 생성 |
| Week 6 | 영상 생성용 `VideoGenerationInput` 정규화, Job/상태 관리 API 구축 |

### Phase 4: 서비스 통합 및 기능 구현 (Week 7-8)
| Week | Tasks |
|------|-------|
| Week 7 | 프론트엔드와 백엔드 간의 통신 연동, 사용자 데이터 입력 및 처리 파이프라인 완성 |
| Week 8 | 생성된 영화 데이터(줄거리, OST, 영상 생성 입력/상태)를 사용자에게 제공하는 프론트엔드 연동 |

### Phase 5: 테스트 및 최종 마무리 (Week 9-10)
| Week | Tasks |
|------|-------|
| Week 9 | 통합 테스트 및 디버깅, 성능 최적화, 예외 처리(API 호출 실패, 데이터 분석 오류 등) |
| Week 10 | 최종 배포, 프로젝트 문서화(README 업데이트), 발표 자료(PPT) 준비 및 리허설 |

---

## 👥 Team

| 역할 | 이름 |
|------|------|
| 팀원1 | 김준희 |
| 팀원2 | 양웅진 |
| 팀원3 | 정윤찬 |

---

<div align="center">

**2026 Spring Software Engineering | Team 6**

[🔗 GitHub Repository](https://github.com/karl21-02/my-life-movie-backend)

</div>
