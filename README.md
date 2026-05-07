<div align="center">

# 🎬 My Life Movie

**내 디지털 흔적을 AI가 분석해서, 나만의 인생 영화를 만들어주는 서비스**

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org/)
[![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com/)

[Features](#-features) • [Tech Stack](#-tech-stack) • [Getting Started](#-getting-started) • [Roadmap](#-roadmap) • [Team](#-team)

</div>

---

## 💡 Vision

> **" 이력서, Spotify, 카카오톡 등 나의 데이터를 AI가 분석하여
> 장르·줄거리·포스터·OST가 담긴 세상에 단 하나뿐인 내 인생을 표현하는 영화를 만들어 드립니다. "**

| | |
|---|---|
| **Product** | My Life Movie (AI 기반 개인 맞춤형 콘텐츠 생성 서비스) |
| **Target Users** | 자신의 이야기를 특별한 콘텐츠로 표현하고 공유하고 싶은 MZ세대, 나의 인생을 내가 아닌 색다르고 다양한 시점으로 바라보고 싶은 사람. |
| **Problem** | 흩어져 있는 자신의 디지털 데이터(이력서, 음악, 대화 등)를 의미 있는 하나의 서사로 모아보고 싶은 흥미. |
| **Key Benefit** | 자신의 인생을 제3자의 시점(영화 장르 및 줄거리)에서 바라보는, 색다른 경험과 시각적 콘텐츠를 제공. |
| **Differentiation** | 단순히 텍스트를 요약하는 것을 넘어, OCR, 감성 분석(KoBERT), 장르 분류(KoELECTRA)를 결합하여, 포스터와 OST까지 포함된 종합적인 영화적 콘텐츠를 자동 생성. |

---

## ✨ Features

### 📊 다중 데이터 소스 분석
이력서 PDF(OCR), Spotify(취향), 카카오톡 내보내기 파일(인간관계) 파싱 및 분석.

### 🧠 AI 를 활용한 감성 & 장르 분류
KoBERT 및 KoELECTRA 모델을 활용하여 삶의 감성을 파악하고, 결과로 내보낼 영화의 장르를 결정.

### 🎨 시각적 & 청각적 이미지 생성
GPT(줄거리) · DALL-E(포스터) · Spotify API(OST) 를 연동하여 하나의 콘텐츠 패키지 완성.

---

## 🎯 Goals & Scope

### Goals
- 데이터 업로드부터 영화 생성 완료까지의 프로세스를 **30초 이내**로 최적화.
- 사용자 데이터 분석의 정확도(감성/장르 일치도)에 대한 정성적 만족도 확보.

### In-Scope
- 다양한 형식(PDF, JSON, TXT 등)의 데이터 전처리 및 파싱 로직 구현.
- FastAPI 기반의 AI 모델 서빙 및 API 구현.
- 외부 생성형 AI API(GPT, DALL-E) 프롬프트 엔지니어링 최적화.

### Out-of-Scope
- 실제 영상 클립 생성 (포스터 및 이미지 기반 결과물에 집중).
- 사용자 트래픽 대응을 위한 인프라 확장성 테스트.

---

## 🛠 Tech Stack

| Category | Technologies |
|----------|-------------|
| **Backend** | Python FastAPI |
| **ML** | KoBERT, KoELECTRA |
| **API** | GPT, DALL-E, Spotify |

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

기본 주소는 `http://localhost:8000`이고, 상태 확인은 `http://localhost:8000/health`에서 할 수 있습니다. Compose 실행 시 `APP_ENV=local`, `LOG_LEVEL=DEBUG`, 프론트 개발 서버용 CORS origin, MySQL 개발 DB가 기본으로 적용됩니다.

| Service | URL |
|---------|-----|
| Backend API | http://localhost:8000 |
| Backend Health Check | http://localhost:8000/health |
| MySQL | localhost:3307 |

### DB 마이그레이션

개발 DB가 실행 중일 때 Alembic으로 테이블을 생성합니다.

```bash
# 로컬에서 실행
uv run alembic upgrade head

# Docker Compose 컨테이너에서 실행
docker compose exec my-life-movie-backend uv run alembic upgrade head
```

현재 기본 스키마는 인증 개발을 위한 `users`, `auth_refresh_tokens` 테이블을 포함합니다.

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

- DB에는 refresh token 원문을 저장하지 않고 `sha256` 해시만 저장합니다.
- refresh token TTL 기본값은 `14일`입니다.
- 성공적으로 회전하면 기존 row는 `ROTATED`, 신규 row는 `ACTIVE` 상태가 됩니다.
- 이미 `ROTATED`, `REVOKED`, `EXPIRED` 상태인 token을 다시 사용하면 `401 REFRESH_TOKEN_REUSED`로 거부합니다.
- 쿠키 이름은 `refresh_token`, 속성은 `HttpOnly`, `SameSite=Lax`, `Path=/auth`입니다. 로컬 환경은 `Secure=false`, 운영 환경은 기본 `Secure=true`로 동작합니다.

## 📚 Docs

- [개발 컨벤션](docs/CONVENTIONS.md): Git 브랜치 전략, 커밋 컨벤션, PR 규칙, 로그 기준

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
| Week 3 | FastAPI 기본 프로젝트 세팅, 클라우드(GCP 등) 개발 환경 구축 |
| Week 4 | 이력서 PDF OCR 분석 모듈 개발, Spotify API 및 카카오톡 대화 내용 파싱 로직 구현 |

### Phase 3: AI 모델 개발 및 연동 (Week 5-6)
| Week | Tasks |
|------|-------|
| Week 5 | KoBERT, KoELECTRA를 활용한 감성/인간관계 분석 모델 학습 및 테스트 (Colab 등 활용) |
| Week 6 | GPT 및 DALL-E API 프롬프트 엔지니어링, 장르/줄거리/포스터 생성 로직 FastAPI에 통합 |

### Phase 4: 서비스 통합 및 기능 구현 (Week 7-8)
| Week | Tasks |
|------|-------|
| Week 7 | 프론트엔드와 백엔드 간의 통신 연동, 사용자 데이터 입력 및 처리 파이프라인 완성 |
| Week 8 | 생성된 영화 데이터(포스터, 줄거리, OST)를 사용자에게 제공하는 프론트엔드 연동 |

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
