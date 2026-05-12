from pydantic import BaseModel
from typing import Optional


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
