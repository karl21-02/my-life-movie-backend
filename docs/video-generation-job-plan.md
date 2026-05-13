# 영상 생성 Job 및 상태 관리 개발 계획

## 목표

유저가 영화 생성 버튼을 누르면 백엔드가 영상을 즉시 동기 생성하지 않고, 생성 작업을 `Job`으로 등록한 뒤 상태를 조회할 수 있는 기반을 만든다.

이 이슈는 하나의 작업 이슈 안에서 단계적으로 진행한다. 먼저 MySQL 기반 Job/상태 관리와 기본 `input_snapshot`을 만들고, 같은 이슈의 이후 단계에서 파일 저장, 자산 분석, worker/provider 연동으로 확장한다.

## 현재 상태

- `POST /api/movies/{movie_id}/generate`는 현재 `movies.status`를 `GENERATING`으로만 변경한다.
- 선행 작업에서 `movies`에 `story_brief`, `scene_plan`, `generation_prompt`가 추가됐다.
- 영상 provider에 넘길 기본 텍스트 입력값은 준비됐지만, 첨부 파일 유형별 분석 결과를 통합한 표준 입력과 생성 작업 이력/상태 조회 모델은 아직 없다.

## 구현 범위

### 1. DB 모델과 마이그레이션

`video_generation_jobs` 테이블을 추가한다.

필드 초안:

| 컬럼 | 설명 |
|---|---|
| `id` | Job ID |
| `movie_id` | 대상 영화 ID |
| `user_id` | 요청 사용자 ID |
| `status` | `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELED` |
| `provider` | `mock` 기본값 |
| `provider_job_id` | 외부 provider 작업 ID |
| `progress` | 0~100 진행률 |
| `input_snapshot` | 생성 요청 시점의 표준 영상 생성 입력 |
| `output_url` | 생성 완료 영상 URL |
| `thumbnail_url` | 생성 완료 썸네일 URL |
| `error_code` | 실패 코드 |
| `error_message` | 사용자에게 노출 가능한 실패 메시지 |
| `started_at` | 실행 시작 시각 |
| `completed_at` | 완료/실패/취소 시각 |
| `created_at` | 생성 시각 |
| `updated_at` | 수정 시각 |

인덱스:

- `movie_id`, `status`
- `user_id`, `created_at`
- `provider`, `provider_job_id`

### 2. 영상 생성 입력 정규화 방향

유저 입력은 텍스트, 테마, 음악, 이미지, 영상, 문서처럼 유형이 다르므로 provider에 바로 넘기지 않는다. 생성 요청 시점에는 내부 표준 포맷인 `VideoGenerationInput` 형태로 정규화해 `input_snapshot`에 저장한다.

초기 `VideoGenerationInput` 구조:

```json
{
  "story": {
    "title": "나의 인생 영화",
    "logline": "사용자의 이야기를 한 문장으로 요약",
    "summary": "현재 시나리오 초안",
    "emotions": ["회상", "따뜻함"]
  },
  "style": {
    "theme_id": 1,
    "visual_style": "따뜻한 시네마틱 필름룩",
    "mood": ["잔잔함", "여운"]
  },
  "audio_direction": {
    "music_id": 101
  },
  "assets": {
    "images": [],
    "videos": [],
    "documents": []
  },
  "scenes": [],
  "provider_prompt": "영상 provider에 넘길 최종 프롬프트"
}
```

1단계에서는 실제 첨부 파일 분석을 실행하지 않고, 현재 저장된 `story_brief`, `scene_plan`, `generation_prompt`, `theme_id`, `music_id`, `files`를 위 구조로 스냅샷화한다. 이후 같은 이슈의 단계별 작업으로 파일 저장과 analyzer 실행을 붙인다.

### 3. 분석 파이프라인 확장 설계

같은 이슈의 후반 단계에서는 데이터 유형별 하위 분석기를 두고, 그 결과를 통합해 최종 `VideoGenerationInput`을 만든다.

```text
AssetAnalysisOrchestrator
  ├─ TextStoryAnalyzer
  ├─ ImageAssetAnalyzer
  ├─ VideoAssetAnalyzer
  ├─ DocumentAssetAnalyzer
  ├─ AudioDirectionAnalyzer
  ↓
GenerationInputSynthesizer
  ↓
VideoGenerationInput
```

운영 규칙:

- 각 analyzer는 입력을 받아 분석 결과만 반환하고 DB를 직접 수정하지 않는다.
- 최종 저장은 orchestrator/service가 담당한다.
- 일부 분석이 실패해도 가능한 partial result로 생성 요청을 진행할 수 있게 한다.
- 원문 사용자 입력, 전체 프롬프트, 파일 내용 전문은 로그에 남기지 않는다.

### 4. 멀티 분석 에이전트 고도화 설계

분석 파이프라인은 완전한 자율 에이전트보다는 역할이 명확한 하위 분석기와 통합기로 구성한다. 이렇게 하면 병렬 실행, 실패 격리, 테스트, 비용 제어가 쉽다.

전체 흐름:

```text
GenerationPreparationOrchestrator
  ↓
InputCollector
  ↓
Parallel Analyzers
    ├─ StoryAnalyzer
    ├─ ImageAnalyzer
    ├─ VideoAnalyzer
    ├─ DocumentAnalyzer
    ├─ MusicAnalyzer
  ↓
AnalysisValidator
  ↓
GenerationInputSynthesizer
  ↓
PromptRefiner
  ↓
SafetyReviewer
  ↓
VideoGenerationInput
```

#### InputCollector

역할:

- `movie`, `files`, `theme_id`, `music_id`, `story_brief`, `scene_plan`, `generation_prompt`를 수집한다.
- 입력을 `story`, `image`, `video`, `document`, `music` 유형으로 분류한다.
- 분석 가능한 입력과 아직 분석할 수 없는 입력을 나눈다.

출력 예:

```json
{
  "movie_id": 1,
  "user_id": 1,
  "story_source": {},
  "image_assets": [],
  "video_assets": [],
  "document_assets": [],
  "music_source": {}
}
```

#### StoryAnalyzer

역할:

- 유저 대화, `current_draft`, `story_brief`, `scene_plan`을 분석한다.
- 인물, 시간대, 장소, 사건, 감정선, 장면 후보를 추출한다.

출력 예:

```json
{
  "source": "story",
  "summary": "사용자의 핵심 인생 이야기를 요약",
  "characters": [],
  "timeline": [],
  "locations": [],
  "important_events": [],
  "emotions": [],
  "visual_keywords": []
}
```

#### ImageAnalyzer

역할:

- 업로드 사진의 장소, 분위기, 색감, 인물 수, 주요 사물을 분석한다.
- reference image로 사용할 수 있는지 판단한다.

출력 예:

```json
{
  "source": "image",
  "asset_id": "file_123",
  "description": "햇빛이 들어오는 방 안의 가족 사진",
  "people_count": 3,
  "location_type": "home",
  "mood": ["warm", "nostalgic"],
  "visual_keywords": ["soft light", "family", "home"],
  "usable_for_generation": true
}
```

#### VideoAnalyzer

역할:

- 영상 메타데이터, 장면 전환, 대표 프레임, 프레임별 시각 분석을 수행한다.
- 전체 영상의 분위기와 생성 참고 가능 여부를 요약한다.

출력 예:

```json
{
  "source": "video",
  "asset_id": "file_456",
  "duration_sec": 42.1,
  "scene_count": 6,
  "summary": "가족 여행 장면들이 이어지는 영상",
  "representative_moments": [
    {
      "timestamp_sec": 3.2,
      "description": "바닷가에서 웃는 장면",
      "mood": ["joyful", "summer"],
      "visual_keywords": ["beach", "family", "sunlight"]
    }
  ],
  "usable_for_generation": true
}
```

#### DocumentAnalyzer

역할:

- `pdf`, `txt`에서 추출된 텍스트를 요약한다.
- 중요한 사건, 날짜, 장소, 감정, 내레이션 후보 문장을 추출한다.
- 개인정보와 민감정보는 요약하거나 마스킹한다.

출력 예:

```json
{
  "source": "document",
  "asset_id": "file_789",
  "summary": "대학 시절 편지와 회고",
  "important_events": [],
  "candidate_narrations": [],
  "emotions": [],
  "sensitive_data_detected": false
}
```

#### MusicAnalyzer

역할:

- 현재는 `music_id`, `title`, `file_url` 기반으로 영상의 오디오 방향을 정규화한다.
- tempo, energy, genre 분석은 실제 음원 메타데이터나 외부 분석 API가 붙은 뒤 확장한다.

출력 예:

```json
{
  "source": "music",
  "music_id": 101,
  "mood": ["calm", "warm"],
  "tempo": "slow",
  "genre_hint": "acoustic",
  "editing_pace": "slow"
}
```

#### AnalysisValidator

역할:

- analyzer별 결과 스키마를 검증한다.
- 빈 결과에 기본값을 채운다.
- 서로 충돌하는 분석 결과를 감지한다.

충돌 예:

- story는 어두운 회고인데 theme는 밝은 코미디 톤인 경우
- 이미지 분석은 실내인데 scene plan은 바닷가 중심인 경우
- 음악은 빠른 템포인데 장면 구성은 느린 회상 중심인 경우

출력 예:

```json
{
  "warnings": [],
  "conflicts": [],
  "missing_inputs": [],
  "usable_sources": ["story", "image", "music"]
}
```

#### GenerationInputSynthesizer

역할:

- 모든 분석 결과를 하나의 `VideoGenerationInput`으로 통합한다.
- 어떤 asset을 우선 사용할지 결정한다.
- `single_clip`, `multi_scene`, `image_to_video` 같은 생성 전략을 결정한다.

출력 예:

```json
{
  "selected_assets": [],
  "scene_strategy": "single_clip",
  "provider_mode": "text_to_video",
  "video_generation_input": {}
}
```

#### PromptRefiner

역할:

- `VideoGenerationInput`을 provider별 prompt 제약에 맞게 압축한다.
- text-to-video, image-to-video, multi-scene 생성 방식에 따라 prompt를 다르게 만든다.
- 원문 개인정보, 실명, 연락처, 파일 내용 전문은 제거한다.

#### SafetyReviewer

역할:

- 개인정보, 민감정보, 저작권 위험, 얼굴/미성년자/상표/실명 노출 위험을 확인한다.
- 위험이 있으면 생성 자체를 막기보다 warning을 남기고 안전한 표현으로 치환하는 것을 기본값으로 한다.

출력 예:

```json
{
  "blocked": false,
  "warnings": [],
  "redactions": []
}
```

#### 통합 결과 구조

최종적으로 `input_snapshot`에는 분석 결과와 생성 입력을 함께 저장할 수 있게 한다.

```json
{
  "analysis_results": {
    "story": {},
    "images": [],
    "videos": [],
    "documents": [],
    "music": {}
  },
  "validation": {
    "warnings": [],
    "conflicts": [],
    "missing_inputs": []
  },
  "synthesis": {
    "selected_assets": [],
    "scene_strategy": "single_clip",
    "provider_mode": "text_to_video"
  },
  "safety": {
    "blocked": false,
    "warnings": [],
    "redactions": []
  },
  "video_generation_input": {
    "story": {},
    "style": {},
    "audio_direction": {},
    "assets": {},
    "scenes": [],
    "provider_prompt": ""
  }
}
```

#### 실행 단계

처음부터 분산 에이전트로 만들지 않고 단계적으로 확장한다.

| 단계 | 실행 방식 |
|---|---|
| v1 | 인터페이스만 분리하고 동기 순차 실행 |
| v2 | `asyncio.gather` 기반 병렬 분석 |
| v3 | Redis queue 기반 analyzer 작업 분산 |
| v4 | analyzer별 모델/비용/타임아웃 정책 분리 |

#### 실패 처리 원칙

- story 분석 실패는 기본 `story_brief`와 `generation_prompt`로 fallback한다.
- 이미지/영상/문서 분석 실패는 해당 asset만 제외하고 진행한다.
- SafetyReviewer가 `blocked = true`를 반환한 경우에는 Job을 `FAILED` 처리하고 사용자에게 안전한 실패 메시지를 반환한다.
- analyzer별 timeout은 전체 Job timeout보다 짧게 둔다.

### 5. Analyzer별 기능 고도화 방향

각 analyzer는 원본 데이터를 그대로 전달하지 않고, 영상 생성에 쓸 수 있는 신호로 정규화한다. 모든 analyzer 결과에는 공통적으로 `confidence`, `quality_score`, `usable_for_generation`, `warnings`, `suggested_use`를 포함할 수 있게 설계한다.

공통 결과 필드 예:

```json
{
  "confidence": 0.86,
  "quality_score": 0.74,
  "usable_for_generation": true,
  "warnings": [],
  "suggested_use": "reference_image"
}
```

#### StoryAnalyzer 고도화

기본 추출:

- 주인공
- 핵심 사건
- 시간대
- 장소
- 감정 변화
- 상징물
- 결말 톤

고도화:

- 유저 이야기를 `3-act structure`로 변환한다.
- 장면별 갈등, 전환점, 클라이맥스를 추출한다.
- 내레이션 후보를 생성한다.
- 추상적인 감정 표현을 영상화 가능한 시각 표현으로 변환한다.
- 장면별 visual keyword를 생성한다.

#### ImageAnalyzer 고도화

기본 추출:

- 인물 수
- 장소 타입
- 시간대
- 색감
- 분위기
- 주요 사물
- 구도

고도화:

- 대표 이미지 후보를 선정한다.
- 흐릿함, 어두움, 저해상도 등 품질을 평가한다.
- 얼굴, 미성년자, 민감 요소를 flag 처리한다.
- image-to-video reference로 사용할 수 있는지 점수화한다.
- story/scene과 연결 가능한 visual keyword를 생성한다.

#### VideoAnalyzer 고도화

기본 추출:

- duration
- fps
- resolution
- scene cut
- 대표 프레임
- 프레임별 장소/행동/감정
- 전체 분위기

고도화:

- 장면별 요약을 생성한다.
- 반복 장면을 제거한다.
- 흔들림, 저화질, 어두움 등 품질을 평가한다.
- 하이라이트 구간을 선정한다.
- generation reference로 쓸 장면을 랭킹한다.
- story/scene_plan과 매칭 가능한 구간을 찾는다.

#### DocumentAnalyzer 고도화

기본 추출:

- 중요한 사건
- 날짜/시기
- 사람/장소
- 감정 표현
- 기억에 남는 문장

고도화:

- 개인정보, 연락처, 주소를 마스킹한다.
- 내레이션 후보 문장을 추출한다.
- 영화적 장면으로 바꿀 수 있는 소재를 추출한다.
- 문서 신뢰도와 중복 정보를 평가한다.
- story timeline에 합칠 수 있는 이벤트를 정규화한다.

#### MusicAnalyzer 고도화

현재 가능한 추출:

- mood
- selected track title
- theme 기반 분위기 힌트
- scene pace 기본값

이후 고도화:

- 장면별 음악 매칭 후보를 만든다.
- 편집 템포를 추천한다.
- intro, climax, outro 분위기를 제안한다.
- story emotion과 음악 mood의 충돌을 감지한다.
- 영상 생성 provider가 음악을 직접 받지 못해도 prompt에 반영할 audio direction을 만든다.

#### AnalysisValidator 고도화

고도화:

- analyzer 결과 스키마를 검증한다.
- 누락값에 기본값을 채운다.
- story, theme, music, asset 분석 결과 간 충돌을 감지한다.
- asset 품질 점수 기반으로 사용 여부를 결정한다.
- 위험 요소 warning을 생성한다.
- 분석 실패를 전체 실패로 전파하지 않고 partial result로 낮춘다.

#### GenerationInputSynthesizer 고도화

고도화:

- story 중심 생성인지 asset 중심 생성인지 전략을 선택한다.
- `text_to_video`, `image_to_video`, `multi_scene` 모드를 결정한다.
- scene_plan을 재정렬하거나 압축한다.
- 사용할 asset 우선순위를 결정한다.
- 최종 `VideoGenerationInput`을 생성한다.
- provider가 바뀌어도 유지되는 내부 표준 입력을 보장한다.

#### PromptRefiner 고도화

고도화:

- provider별 prompt 길이 제한을 반영한다.
- 추상적인 문장을 시각적으로 표현 가능한 문장으로 바꾼다.
- 장면별 prompt와 전체 prompt를 분리해 생성한다.
- negative prompt를 생성한다.
- 금지 표현, 민감정보, 실명, 연락처, 파일 원문을 제거한다.

#### SafetyReviewer 고도화

고도화:

- 개인정보 노출 위험을 감지한다.
- 미성년자, 얼굴, 초상권 관련 위험을 감지한다.
- 브랜드, 상표, 저작권 가능성이 있는 이미지/음악 요소를 감지한다.
- 위험 요소를 무조건 차단하지 않고 가능한 경우 안전한 표현으로 redaction한다.
- 차단이 필요한 경우 `blocked = true`와 사용자 노출 가능한 사유를 반환한다.

#### 고도화 우선순위

1. StoryAnalyzer
2. GenerationInputSynthesizer
3. ImageAnalyzer
4. VideoAnalyzer
5. DocumentAnalyzer
6. MusicAnalyzer
7. SafetyReviewer
8. PromptRefiner

초기에는 StoryAnalyzer와 GenerationInputSynthesizer를 우선 고도화한다. 서비스의 핵심이 유저의 인생 이야기이기 때문에, 스토리 품질과 최종 입력 통합 품질이 영상 결과의 기본 품질을 결정한다.

### 6. 영상 파일 분석 정책

영상 파일은 프레임을 고정 5장만 뽑지 않고, 길이와 장면 전환을 기준으로 대표 프레임을 추출한다.

현재 파일 업로드는 원본 저장 URL 없이 `filename`, `type`, `extracted_text`만 저장한다. 따라서 실제 ffprobe/ffmpeg 분석은 파일 저장소 단계가 먼저 완료된 뒤 진행한다.

초기 정책:

| 기준 | 추출 방식 |
|---|---|
| 10초 이하 | 3~5프레임 |
| 10~60초 | 8~16프레임 |
| 1~5분 | scene detection 후 장면별 2~3프레임 |
| 5분 초과 | 최대 분석 길이 제한 후 대표 구간 샘플링 |

기본 파라미터:

```text
max_frames_per_video = 16
fallback_uniform_samples = 8
min_interval_sec = 2
scene_detection_enabled = true
max_video_duration_for_full_analysis_sec = 300
```

이후 구현 흐름:

```text
video file
  → ffprobe metadata 추출
  → scene detection
  → representative frames 추출
  → vision 분석
  → video asset summary 생성
  → VideoGenerationInput.assets.videos에 반영
```

1단계에서는 위 정책을 `input_snapshot` 설계에 반영한다. 파일 저장소가 들어간 뒤 같은 이슈의 이후 커밋에서 실제 ffmpeg/vision 분석을 구현한다.

### 7. Repository / Service

`VideoGenerationJobRepository`를 추가한다.

필요 동작:

- Job 생성
- 영화의 최신 Job 조회
- 진행 중인 Job 조회
- Job 상태 변경
- Job 실패/완료 처리 확장 가능 구조

`VideoGenerationService`를 추가한다.

필요 동작:

- 영화 존재 여부와 소유자 권한 확인
- `generation_prompt` 존재 여부 확인
- 진행 중인 Job이 있으면 중복 생성 방지
- 생성 요청 시 표준화된 `input_snapshot` 저장
- 최초 상태는 `QUEUED`, 진행률은 `0`

### 8. API 계약

기존 API를 Job 생성 방식으로 변경한다.

```text
POST /api/movies/{movie_id}/generate
```

응답:

```json
{
  "movie_id": 1,
  "job_id": 10,
  "status": "QUEUED",
  "progress": 0,
  "message": "영상 생성 요청이 접수되었습니다."
}
```

상태 조회 API를 추가한다.

```text
GET /api/movies/{movie_id}/generation
```

응답:

```json
{
  "movie_id": 1,
  "job_id": 10,
  "status": "QUEUED",
  "progress": 0,
  "output_url": null,
  "thumbnail_url": null,
  "error_code": null,
  "error_message": null
}
```

진행 중인 Job이 없으면 `404 GENERATION_JOB_NOT_FOUND`를 반환한다.

### 9. 상태 규칙

진행 중 상태:

- `QUEUED`
- `RUNNING`

종료 상태:

- `SUCCEEDED`
- `FAILED`
- `CANCELED`

중복 생성 방지:

- 같은 영화에 `QUEUED` 또는 `RUNNING` Job이 있으면 새 Job을 만들지 않는다.
- 이 경우 `409 GENERATION_ALREADY_IN_PROGRESS`를 반환한다.

영화 상태 반영:

- Job 생성 시 `movies.status = GENERATING`
- worker 처리 완료 시 `COMPLETED`, 실패 시 `FAILED`, 취소 시 `DRAFT`로 반영한다.

## 단계별 범위

이 이슈는 하나의 이슈에서 진행하되, 구현은 아래 단계로 분리한다.

| 단계 | 범위 |
|---|---|
| 1단계 | `video_generation_jobs`, generate/status API, 기본 `VideoGenerationInput` snapshot |
| 2단계 | 파일 저장소/S3 기반 원본 파일 URL, metadata 저장 |
| 3단계 | Image/Video/Document/Music analyzer v1 |
| 4단계 | Synthesizer, PromptRefiner, SafetyReviewer |
| 5단계 | DB 큐, worker, mock provider 처리 |
| 6단계 | fal.ai 실제 영상 provider 연동 |
| 7단계 | S3 결과 저장, output_url/thumbnail_url 반영 |

프론트 생성 진행 화면은 백엔드 Job/status API가 안정화된 뒤 프론트 이슈에서 별도로 진행한다.

## 테스트 계획

단위 테스트:

- Job 생성 시 기본 상태가 `QUEUED`인지 확인
- 최신 Job 조회가 최신 생성 순서를 따르는지 확인
- 진행 중 Job이 있으면 중복 생성을 막는지 확인
- 종료 상태 Job은 새 생성 요청을 막지 않는지 확인

통합/API 테스트:

- `POST /api/movies/{movie_id}/generate`가 Job을 생성하고 `QUEUED` 응답을 반환한다.
- 생성 요청 시 `input_snapshot`에 표준화된 `story`, `style`, `audio_direction`, `assets`, `scenes`, `provider_prompt`가 저장된다.
- 같은 영화에 진행 중 Job이 있으면 `409`를 반환한다.
- `GET /api/movies/{movie_id}/generation`이 최신 Job 상태를 반환한다.
- `POST /api/movies/{movie_id}/generation/cancel`이 진행 중 Job을 `CANCELED`로 변경한다.
- worker가 가장 오래된 `QUEUED` Job을 처리한다.
- `FAL_KEY`가 있으면 fal.ai provider를 사용하고, 없으면 mock provider를 사용한다.
- 없는 영화는 `404`를 반환한다.
- 권한 없는 영화는 `403`을 반환한다.
- 기존 `draft/music/input/summary` 테스트가 깨지지 않는다.

검증 명령:

```bash
uv run pytest
uv run python -m compileall -q app migrations tests
git diff --check
```

## 단계별 커밋 계획

1. `feat(ai): 영상 생성 Job 모델 추가`
   - 모델, enum, migration 추가
   - migration 테스트 갱신

2. `feat(api): 영상 생성 Job API 추가`
   - repository/service/API 응답 스키마 추가
   - generate/status API 구현

3. `feat(ai): 영상 생성 입력 스냅샷 정규화 추가`
   - `VideoGenerationInput` builder 추가
   - story/style/audio/assets/scenes/provider_prompt 스냅샷 저장

4. `test(ai): 영상 생성 Job 상태 테스트 추가`
   - 단위 테스트와 통합 테스트 추가

5. `feat(storage): 영화 첨부 파일 저장소 기반 추가`
   - 업로드 원본 URL/storage key/mime/file size 저장
   - analyzer가 접근 가능한 asset 구조 준비

6. `feat(ai): 자산 분석기 v1 추가`
   - Image/Video/Document/Music analyzer 인터페이스와 기본 구현
   - video metadata/frame extraction 정책 반영

7. `feat(ai): 영상 생성 입력 통합기 추가`
   - AnalysisValidator
   - GenerationInputSynthesizer
   - PromptRefiner
   - SafetyReviewer

8. `feat(worker): 영상 생성 worker와 mock provider 추가`
   - DB 큐
   - Job 실행/완료/실패 상태 전이
   - mock output_url/thumbnail_url 반영

9. `feat(ai): 실제 영상 provider 연동`
   - fal.ai queue API adapter 구현
   - provider 선택은 `VIDEO_GENERATION_PROVIDER=auto|mock|fal`
   - `FAL_KEY`가 있으면 실제 provider, 없으면 mock provider 사용
   - provider 결과 URL을 Job의 `output_url`, `thumbnail_url`에 반영

## 별도 프론트 작업

- 생성 진행 화면
- polling 연동
- 실패/재시도 UI
- 완료 후 결과 페이지 이동
