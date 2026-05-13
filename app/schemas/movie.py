from typing import Any, Optional

from pydantic import BaseModel, Field


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
    movie_id: int
    job_id: int
    status: str
    progress: int
    message: str


class GenerationStatusResponse(BaseModel):
    movie_id: int
    job_id: int
    status: str
    progress: int
    output_url: str | None = None
    thumbnail_url: str | None = None
    error_code: str | None = None
    error_message: str | None = None
