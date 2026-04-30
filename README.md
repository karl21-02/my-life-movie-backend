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
