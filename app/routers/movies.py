import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.schemas.movie import (
    CreateDraftRequest,
    CreateDraftResponse,
    UpdateMusicRequest,
    ChatRequest,
    ChatResponse,
    FileUploadResponse,
    SummaryResponse,
)

router = APIRouter(prefix="/api/v1/movies", tags=["movies"])

# 인메모리 임시 저장소 - DB 연동 시 교체. {id:영화 정보 딕셔너리} 구조임.
movies_store: dict[int, dict] = {}
_next_id = 1

# 허용되는 파일 확장자 (화이트리스트)
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".txt", ".mp4", ".mov"}

# 예시 질문(프롬프트) <- AI 연동 시 실제 질문으로 교체
AI_QUESTIONS = [
    "어떤 시절의 이야기를 가장 담고 싶으신가요?",
    "그 시절 가장 기억에 남는 장소나 공간이 있다면 알려주세요.",
    "영화에서 가장 중요하게 표현하고 싶은 감정은 무엇인가요?",
    "이 영화를 보고 나서 어떤 기분이 들었으면 하나요?",
]

# 영화 ID 증가를 위한 간단한 함수 <- 영화 만들 때 초안 구분
def _next_movie_id() -> int:
    global _next_id
    movie_id = _next_id
    _next_id += 1
    return movie_id


@router.post("/draft", response_model=CreateDraftResponse)
async def create_draft(request: CreateDraftRequest):
    """테마를 선택해 영화 초안을 생성합니다. movie_id를 반환하며 이후 모든 요청에 사용됩니다."""
    movie_id = _next_movie_id()
    movies_store[movie_id] = {
        "movie_id": movie_id,
        "theme_id": request.theme_id,
        "music_id": None,
        "files": [],
        "chat_history": [],
        "current_draft": "",
        "status": "DRAFT",
    }
    return CreateDraftResponse(movie_id=movie_id, status="DRAFT")


@router.put("/{movie_id}/music")
async def update_music(movie_id: int, request: UpdateMusicRequest):
    """선택한 음악 ID를 영화에 저장합니다."""
    if movie_id not in movies_store:
        raise HTTPException(status_code=404, detail="Movie not found")
    movies_store[movie_id]["music_id"] = request.music_id
    return {"movie_id": movie_id, "music_id": request.music_id}


@router.post("/{movie_id}/files", response_model=FileUploadResponse)
async def upload_file(movie_id: int, file: UploadFile = File(...)):
    """파일(사진/영상/문서)을 업로드합니다. 허용 확장자: jpg, jpeg, png, pdf, txt, mp4, mov"""
    if movie_id not in movies_store:
        raise HTTPException(status_code=404, detail="Movie not found")

    ext = ("." + file.filename.rsplit(".", 1)[-1].lower()) if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"허용되지 않는 파일 형식입니다: {ext}")

    file_id = str(uuid.uuid4())
    if ext in {".jpg", ".jpeg", ".png"}:
        file_type = "image"
    elif ext in {".mp4", ".mov"}:
        file_type = "video"
    else:
        file_type = "document"

    file_info = {
        "file_id": file_id,
        "filename": file.filename,
        "type": file_type,
        "extracted_text": f"[{file.filename}] 파일 분석 완료 (AI 연동 시 실제 내용으로 교체)",
    }
    movies_store[movie_id]["files"].append(file_info)
    return FileUploadResponse(**file_info)


@router.post("/{movie_id}/chat", response_model=ChatResponse)
async def chat_prompt(movie_id: int, request: ChatRequest):
    """사용자 메시지를 받아 AI 역질문과 현재 시나리오 초안을 반환합니다. (AI 연동 전 예시)"""
    if movie_id not in movies_store:
        raise HTTPException(status_code=404, detail="Movie not found")

    history = movies_store[movie_id]["chat_history"]
    history.append({"role": "user", "message": request.message})

    turn = len([h for h in history if h["role"] == "user"]) - 1
    ai_question = AI_QUESTIONS[min(turn, len(AI_QUESTIONS) - 1)]

    current_draft = movies_store[movie_id]["current_draft"]
    if request.message:
        current_draft = f"{request.message}의 이야기를 담은 영화."
        movies_store[movie_id]["current_draft"] = current_draft

    history.append({"role": "ai", "message": ai_question})
    return ChatResponse(ai_question=ai_question, current_draft=current_draft)


@router.get("/{movie_id}/chat")
async def get_chat_history(movie_id: int):
    """지금까지의 AI 채팅 히스토리를 반환합니다."""
    if movie_id not in movies_store:
        raise HTTPException(status_code=404, detail="Movie not found")
    return {"history": movies_store[movie_id]["chat_history"]}


@router.get("/{movie_id}/summary", response_model=SummaryResponse)
async def get_summary(movie_id: int):
    """피드백 페이지용 최종 입력 요약 (프롬프트 + 업로드 파일 + 테마 + 음악)을 반환합니다. <- 단순히 반환만 보여줄까 아니면 좀 더 AI 요약을 할까"""
    if movie_id not in movies_store:
        raise HTTPException(status_code=404, detail="Movie not found")
    movie = movies_store[movie_id]
    return SummaryResponse(
        prompt=movie["current_draft"],
        files=movie["files"],
        theme={"theme_id": movie["theme_id"]},
        music={"music_id": movie["music_id"]} if movie["music_id"] else None,
    )


@router.post("/{movie_id}/generate")
async def generate_movie(movie_id: int):
    """영화 생성을 시작합니다. 상태가 GENERATING으로 변경됩니다. (생성 해줘)"""
    if movie_id not in movies_store:
        raise HTTPException(status_code=404, detail="Movie not found")
    movies_store[movie_id]["status"] = "GENERATING"
    return {"movie_id": movie_id, "status": "GENERATING", "message": "영화 생성이 시작되었습니다."}
