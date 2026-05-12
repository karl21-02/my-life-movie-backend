import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from sqlalchemy.orm import Session

from app.api.movies import schemas, service
from app.core.config import get_settings
from app.core.deps import get_current_user
from app.db.session import get_db_session
from app.repositories.movie_repository import SQLAlchemyMovieRepository
from app.repositories.video_generation_job_repository import SQLAlchemyVideoGenerationJobRepository
from app.schemas.movie import (
    CreateDraftRequest,
    CreateDraftResponse,
    UpdateMusicRequest,
    ChatRequest,
    ChatResponse,
    FileUploadResponse,
    GenerationRequestResponse,
    GenerationStatusResponse,
    SummaryResponse,
)
from app.services.access_token_service import AccessTokenClaims
from app.services.story_generation_service import generate_story_inputs
from app.services.video_generation_service import VideoGenerationService

router = APIRouter(prefix="/api/movies", tags=["movies"])

# 파일 업로드 시 허용되는 확장자 목록 (소문자 기준)
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".txt", ".mp4", ".mov"}

# 영화 조회 시 존재 여부와 소유자 권한을 확인하는 헬퍼 함수
def _get_movie_or_403(repo: SQLAlchemyMovieRepository, movie_id: int, user_id: int):
    movie = repo.get_by_id(movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    if movie.user_id != user_id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")
    return movie


@router.post("/draft", response_model=CreateDraftResponse)
async def create_draft(
    request: CreateDraftRequest,
    db: Session = Depends(get_db_session),
    current_user: AccessTokenClaims = Depends(get_current_user),
):
    """테마를 선택해 영화 초안을 생성합니다. movie_id를 반환하며 이후 모든 요청에 사용됩니다."""
    repo = SQLAlchemyMovieRepository(db)
    movie = repo.create(user_id=current_user.user_id, theme_id=request.theme_id)
    return CreateDraftResponse(movie_id=movie.id, status=movie.status.value)


@router.put("/{movie_id}/music")
async def update_music(
    movie_id: int,
    request: UpdateMusicRequest,
    db: Session = Depends(get_db_session),
    current_user: AccessTokenClaims = Depends(get_current_user),
):
    """선택한 음악 ID를 영화에 저장합니다."""
    repo = SQLAlchemyMovieRepository(db)
    movie = _get_movie_or_403(repo, movie_id, current_user.user_id)
    movie.music_id = request.music_id
    repo.update(movie)
    return {"movie_id": movie.id, "music_id": movie.music_id}


@router.post("/{movie_id}/files", response_model=FileUploadResponse)
async def upload_file(
    movie_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db_session),
    current_user: AccessTokenClaims = Depends(get_current_user),
):
    """파일(사진/영상/문서)을 업로드합니다. 허용 확장자: jpg, jpeg, png, pdf, txt, mp4, mov"""
    repo = SQLAlchemyMovieRepository(db)
    movie = _get_movie_or_403(repo, movie_id, current_user.user_id)

    ext = ("." + file.filename.rsplit(".", 1)[-1].lower()) if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"허용되지 않는 파일 형식입니다: {ext}")

    if ext in {".jpg", ".jpeg", ".png"}:
        file_type = "image"
    elif ext in {".mp4", ".mov"}:
        file_type = "video"
    else:
        file_type = "document"

    file_info = {
        "file_id": str(uuid.uuid4()),
        "filename": file.filename,
        "type": file_type,
        "extracted_text": f"[{file.filename}] 파일 분석 완료 (AI 연동 시 실제 내용으로 교체)",
    }
    movie.files = (movie.files or []) + [file_info]
    repo.update(movie)
    return FileUploadResponse(**file_info)


@router.post("/{movie_id}/chat", response_model=ChatResponse)
async def chat_prompt(
    movie_id: int,
    request: ChatRequest,
    db: Session = Depends(get_db_session),
    current_user: AccessTokenClaims = Depends(get_current_user),
):
    """사용자 메시지를 받아 AI 역질문과 현재 시나리오 초안을 반환합니다."""
    repo = SQLAlchemyMovieRepository(db)
    movie = _get_movie_or_403(repo, movie_id, current_user.user_id)

    history = list(movie.chat_history or [])
    history.append({"role": "user", "message": request.message})

    result = await generate_story_inputs(
        api_key=get_settings().openai_api_key,
        history=history,
        current_draft=movie.current_draft,
        latest_message=request.message,
    )

    history.append({"role": "ai", "message": result.ai_question})
    movie.chat_history = history
    movie.current_draft = result.current_draft
    movie.story_brief = result.story_brief
    movie.scene_plan = result.scene_plan
    movie.generation_prompt = result.generation_prompt
    repo.update(movie)
    return ChatResponse(
        ai_question=result.ai_question,
        current_draft=result.current_draft,
        story_brief=result.story_brief,
        scene_plan=result.scene_plan,
    )


@router.get("/{movie_id}/chat")
async def get_chat_history(
    movie_id: int,
    db: Session = Depends(get_db_session),
    current_user: AccessTokenClaims = Depends(get_current_user),
):
    """지금까지의 AI 채팅 히스토리를 반환합니다."""
    repo = SQLAlchemyMovieRepository(db)
    movie = _get_movie_or_403(repo, movie_id, current_user.user_id)
    return {"history": movie.chat_history or []}


@router.get("/{movie_id}/summary", response_model=SummaryResponse)
async def get_summary(
    movie_id: int,
    db: Session = Depends(get_db_session),
    current_user: AccessTokenClaims = Depends(get_current_user),
):
    """피드백 페이지용 최종 입력 요약 (프롬프트 + 업로드 파일 + 테마 + 음악)을 반환합니다."""
    repo = SQLAlchemyMovieRepository(db)
    movie = _get_movie_or_403(repo, movie_id, current_user.user_id)
    return SummaryResponse(
        prompt=movie.current_draft or "",
        files=movie.files or [],
        theme={"theme_id": movie.theme_id},
        music={"music_id": movie.music_id} if movie.music_id is not None else None,
        story_brief=movie.story_brief,
        scene_plan=movie.scene_plan or [],
        generation_prompt=movie.generation_prompt,
    )


def _get_video_generation_service(db: Session) -> VideoGenerationService:
    return VideoGenerationService(
        movie_repository=SQLAlchemyMovieRepository(db),
        job_repository=SQLAlchemyVideoGenerationJobRepository(db),
    )


@router.get("/{movie_id}/generation", response_model=GenerationStatusResponse)
async def get_generation_status(
    movie_id: int,
    db: Session = Depends(get_db_session),
    current_user: AccessTokenClaims = Depends(get_current_user),
):
    """최신 영상 생성 Job 상태를 조회합니다."""
    job = _get_video_generation_service(db).get_latest_generation(
        movie_id=movie_id,
        user_id=current_user.user_id,
    )
    return GenerationStatusResponse(
        movie_id=job.movie_id,
        job_id=job.id,
        status=job.status.value,
        progress=job.progress,
        output_url=job.output_url,
        thumbnail_url=job.thumbnail_url,
        error_code=job.error_code,
        error_message=job.error_message,
    )


@router.post("/{movie_id}/generate", response_model=GenerationRequestResponse)
async def generate_movie(
    movie_id: int,
    db: Session = Depends(get_db_session),
    current_user: AccessTokenClaims = Depends(get_current_user),
):
    """영상 생성 Job을 생성하고 QUEUED 상태로 반환합니다."""
    result = _get_video_generation_service(db).request_generation(
        movie_id=movie_id,
        user_id=current_user.user_id,
    )
    return GenerationRequestResponse(
        movie_id=result.job.movie_id,
        job_id=result.job.id,
        status=result.job.status.value,
        progress=result.job.progress,
        message="영상 생성 요청이 접수되었습니다.",
    )


@router.get("", response_model=list[schemas.MovieSummary])
async def get_movies() -> list[schemas.MovieSummary]:
    """영화 목록을 반환한다."""
    return service.list_movies()


@router.get("/{movie_id}", response_model=schemas.Movie)
async def get_movie(movie_id: int) -> schemas.Movie:
    """특정 영화의 상세 정보를 반환한다."""
    return service.get_movie(movie_id)


@router.delete("/{movie_id}", response_model=schemas.DeleteMovieResponse)
async def delete_movie(movie_id: int) -> schemas.DeleteMovieResponse:
    """특정 영화를 삭제한다."""
    service.delete_movie(movie_id)
    return schemas.DeleteMovieResponse(message="영화가 삭제되었습니다.")


@router.get("/{movie_id}/download", response_model=schemas.DownloadMovieResponse)
async def download_movie(movie_id: int) -> schemas.DownloadMovieResponse:
    """특정 영화의 다운로드 정보를 반환한다."""
    movie = service.download_movie(movie_id)
    return schemas.DownloadMovieResponse(
        message=f"{movie.title} 다운로드가 준비되었습니다.",
        movie_id=movie.id,
        title=movie.title,
    )


@router.post("/{movie_id}/share", response_model=schemas.ShareMovieResponse)
async def share_movie(movie_id: int, request: Request) -> schemas.ShareMovieResponse:
    """특정 영화의 공유 URL을 생성하여 반환한다."""
    base_url = str(request.base_url).rstrip("/")
    movie, share_url = service.share_movie(movie_id, base_url)
    return schemas.ShareMovieResponse(
        message=f"{movie.title} 공유 링크가 생성되었습니다.",
        movie_id=movie.id,
        title=movie.title,
        share_url=share_url,
    )
