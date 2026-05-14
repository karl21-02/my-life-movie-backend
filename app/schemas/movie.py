from typing import Any, Optional
from typing import Literal

from pydantic import BaseModel, Field

GenerationStatus = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"]
GenerationErrorCode = Literal[
    "PROVIDER_ERROR",
    "PROVIDER_TIMEOUT",
    "PROVIDER_MODERATION_BLOCKED",
    "GENERATION_INPUT_NOT_READY",
    "GENERATION_ALREADY_IN_PROGRESS",
]


class CreateDraftRequest(BaseModel):
    theme_id: int


class CreateDraftResponse(BaseModel):
    movie_id: int
    status: str


class UpdateMusicRequest(BaseModel):
    music_id: int


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    ai_question: str
    current_draft: str
    story_brief: dict[str, Any]
    scene_plan: list[dict[str, Any]]


class FileUploadResponse(BaseModel):
    file_id: str
    filename: str
    type: str
    extracted_text: str


class SummaryResponse(BaseModel):
    prompt: str
    files: list[dict]
    theme: dict
    music: Optional[dict]
    story_brief: dict[str, Any] | None = None
    scene_plan: list[dict[str, Any]] = Field(default_factory=list)
    generation_prompt: str | None = None


class GenerationRequestResponse(BaseModel):
    movie_id: int = Field(description="영상 생성을 요청한 영화 ID", examples=[11])
    job_id: int = Field(description="생성된 영상 생성 Job ID", examples=[9])
    status: GenerationStatus = Field(description="생성 Job의 현재 상태", examples=["QUEUED"])
    progress: int = Field(description="0~100 사이의 생성 진행률", ge=0, le=100, examples=[0])
    message: str = Field(description="요청 접수 메시지", examples=["영상 생성 요청이 접수되었습니다."])


class GenerationStatusResponse(BaseModel):
    movie_id: int = Field(description="영상 생성 상태를 조회한 영화 ID", examples=[11])
    job_id: int = Field(description="최신 영상 생성 Job ID", examples=[9])
    status: GenerationStatus = Field(description="생성 Job의 현재 상태", examples=["RUNNING"])
    progress: int = Field(description="0~100 사이의 생성 진행률", ge=0, le=100, examples=[75])
    output_url: str | None = Field(
        default=None,
        description="생성 성공 후 접근 가능한 영상 URL입니다.",
        examples=["/generated/videos/video_123.mp4"],
    )
    thumbnail_url: str | None = Field(
        default=None,
        description="생성 성공 후 접근 가능한 썸네일 URL입니다.",
        examples=["/generated/thumbnails/video_123.webp"],
    )
    error_code: GenerationErrorCode | None = Field(
        default=None,
        description="실패 시 machine-readable 오류 코드입니다.",
        examples=["PROVIDER_MODERATION_BLOCKED"],
    )
    error_message: str | None = Field(
        default=None,
        description="실패 시 사용자 또는 운영자가 확인할 오류 메시지입니다.",
        examples=["moderation_blocked: Your request was blocked by our moderation system."],
    )
