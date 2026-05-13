import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.movies import schemas
from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.db.session import get_db_session
from app.models.movie import Movie
from app.models.video_generation_job import VideoGenerationJob, VideoGenerationJobStatus
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
from app.services.video_generation_provider import resolve_video_generation_provider_name
from app.services.video_generation_service import VideoGenerationService

router = APIRouter(prefix="/api/movies", tags=["movies"])

# 파일 업로드 시 허용되는 확장자 목록 (소문자 기준)
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".txt", ".mp4", ".mov"}
THEME_NAMES = {
    1: "하이틴",
    2: "사이버펑크",
    3: "무성영화",
    4: "동화",
    5: "재패니즈 노스탤지아",
    6: "지브리",
}
FAMOUS_MOVIES_BY_GENRE = {
    "하이틴": [
        {"id": 101, "title": "브렉퍼스트 클럽", "thumbnail": "https://picsum.photos/seed/fam101/400/600"},
        {"id": 102, "title": "퀸카로 살아남는 법", "thumbnail": "https://picsum.photos/seed/fam102/400/600"},
        {"id": 103, "title": "사랑할 수 없는 10가지 이유", "thumbnail": "https://picsum.photos/seed/fam103/400/600"},
        {"id": 104, "title": "이지 에이", "thumbnail": "https://picsum.photos/seed/fam104/400/600"},
    ],
    "사이버펑크": [
        {"id": 201, "title": "블레이드 러너 2049", "thumbnail": "https://picsum.photos/seed/fam201/400/600"},
        {"id": 202, "title": "매트릭스", "thumbnail": "https://picsum.photos/seed/fam202/400/600"},
        {"id": 203, "title": "공각기동대", "thumbnail": "https://picsum.photos/seed/fam203/400/600"},
        {"id": 204, "title": "아키라", "thumbnail": "https://picsum.photos/seed/fam204/400/600"},
    ],
    "무성영화": [
        {"id": 301, "title": "아티스트", "thumbnail": "https://picsum.photos/seed/fam301/400/600"},
        {"id": 302, "title": "메트로폴리스", "thumbnail": "https://picsum.photos/seed/fam302/400/600"},
        {"id": 303, "title": "시티 라이트", "thumbnail": "https://picsum.photos/seed/fam303/400/600"},
        {"id": 304, "title": "황금광 시대", "thumbnail": "https://picsum.photos/seed/fam304/400/600"},
    ],
    "동화": [
        {"id": 401, "title": "신데렐라", "thumbnail": "https://picsum.photos/seed/fam401/400/600"},
        {"id": 402, "title": "미녀와 야수", "thumbnail": "https://picsum.photos/seed/fam402/400/600"},
        {"id": 403, "title": "라푼젤", "thumbnail": "https://picsum.photos/seed/fam403/400/600"},
        {"id": 404, "title": "마법에 걸린 사랑", "thumbnail": "https://picsum.photos/seed/fam404/400/600"},
    ],
    "재패니즈 노스탤지아": [
        {"id": 501, "title": "이 세상의 한 구석에", "thumbnail": "https://picsum.photos/seed/fam501/400/600"},
        {"id": 502, "title": "추억은 방울방울", "thumbnail": "https://picsum.photos/seed/fam502/400/600"},
        {"id": 503, "title": "귀를 기울이면", "thumbnail": "https://picsum.photos/seed/fam503/400/600"},
        {"id": 504, "title": "초속 5센티미터", "thumbnail": "https://picsum.photos/seed/fam504/400/600"},
    ],
    "지브리": [
        {"id": 601, "title": "센과 치히로의 행방불명", "thumbnail": "https://picsum.photos/seed/fam601/400/600"},
        {"id": 602, "title": "하울의 움직이는 성", "thumbnail": "https://picsum.photos/seed/fam602/400/600"},
        {"id": 603, "title": "모노노케 히메", "thumbnail": "https://picsum.photos/seed/fam603/400/600"},
        {"id": 604, "title": "마녀 배달부 키키", "thumbnail": "https://picsum.photos/seed/fam604/400/600"},
    ],
}

# 영화 조회 시 존재 여부와 소유자 권한을 확인하는 헬퍼 함수
def _get_movie_or_403(repo: SQLAlchemyMovieRepository, movie_id: int, user_id: int):
    movie = repo.get_by_id(movie_id)
    if movie is None:
        raise AppError(
            status_code=404,
            code="MOVIE_NOT_FOUND",
            title="Movie Not Found",
            detail="영화를 찾을 수 없습니다.",
            type_="movie_not_found",
        )
    if movie.user_id != user_id:
        raise AppError(
            status_code=403,
            code="MOVIE_FORBIDDEN",
            title="Movie Forbidden",
            detail="해당 영화에 접근할 권한이 없습니다.",
            type_="movie_forbidden",
        )
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
    settings = get_settings()
    return VideoGenerationService(
        movie_repository=SQLAlchemyMovieRepository(db),
        job_repository=SQLAlchemyVideoGenerationJobRepository(db),
        provider_name=resolve_video_generation_provider_name(settings),
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


@router.post("/{movie_id}/generation/cancel", response_model=GenerationStatusResponse)
async def cancel_generation(
    movie_id: int,
    db: Session = Depends(get_db_session),
    current_user: AccessTokenClaims = Depends(get_current_user),
):
    """진행 중인 영상 생성 Job을 취소합니다."""
    job = _get_video_generation_service(db).cancel_generation(
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


@router.get("", response_model=list[schemas.MovieSummary])
async def get_movies(
    db: Session = Depends(get_db_session),
    current_user: AccessTokenClaims = Depends(get_current_user),
) -> list[schemas.MovieSummary]:
    """현재 사용자의 실제 영화 목록을 반환합니다."""
    movie_repo = SQLAlchemyMovieRepository(db)
    job_repo = SQLAlchemyVideoGenerationJobRepository(db)
    movies = movie_repo.list_by_user_id(current_user.user_id)
    latest_jobs = job_repo.list_latest_by_movie_ids([movie.id for movie in movies])
    return [
        build_movie_summary(movie, latest_jobs.get(movie.id))
        for movie in movies
    ]


@router.get("/{movie_id}", response_model=schemas.Movie)
async def get_movie(
    movie_id: int,
    db: Session = Depends(get_db_session),
    current_user: AccessTokenClaims = Depends(get_current_user),
) -> schemas.Movie:
    """현재 사용자의 특정 영화 상세 정보를 반환합니다."""
    movie_repo = SQLAlchemyMovieRepository(db)
    job_repo = SQLAlchemyVideoGenerationJobRepository(db)
    movie = _get_movie_or_403(movie_repo, movie_id, current_user.user_id)
    return build_movie_detail(movie, job_repo.get_latest_by_movie_id(movie.id))


@router.delete("/{movie_id}", response_model=schemas.DeleteMovieResponse)
async def delete_movie(
    movie_id: int,
    db: Session = Depends(get_db_session),
    current_user: AccessTokenClaims = Depends(get_current_user),
) -> schemas.DeleteMovieResponse:
    """현재 사용자의 특정 영화를 삭제합니다."""
    movie_repo = SQLAlchemyMovieRepository(db)
    movie = _get_movie_or_403(movie_repo, movie_id, current_user.user_id)
    movie_repo.delete(movie)
    return schemas.DeleteMovieResponse(message="영화가 삭제되었습니다.")


@router.get("/{movie_id}/download", response_model=schemas.DownloadMovieResponse)
async def download_movie(
    movie_id: int,
    db: Session = Depends(get_db_session),
    current_user: AccessTokenClaims = Depends(get_current_user),
) -> schemas.DownloadMovieResponse:
    """현재 사용자의 특정 영화 다운로드 정보를 반환합니다."""
    movie_repo = SQLAlchemyMovieRepository(db)
    job_repo = SQLAlchemyVideoGenerationJobRepository(db)
    movie = _get_movie_or_403(movie_repo, movie_id, current_user.user_id)
    latest_job = job_repo.get_latest_by_movie_id(movie.id)
    title = build_movie_title(movie)
    output_url = latest_job.output_url if latest_job is not None else None
    return schemas.DownloadMovieResponse(
        message=f"{title} 다운로드가 준비되었습니다.",
        movie_id=movie.id,
        title=title,
        output_url=output_url,
        download_url=build_movie_download_url(movie.id, output_url),
    )


@router.get("/{movie_id}/download/file")
async def download_movie_file(
    movie_id: int,
    db: Session = Depends(get_db_session),
    current_user: AccessTokenClaims = Depends(get_current_user),
) -> FileResponse:
    """현재 사용자의 생성 완료 영화를 실제 파일로 다운로드합니다."""
    movie_repo = SQLAlchemyMovieRepository(db)
    job_repo = SQLAlchemyVideoGenerationJobRepository(db)
    movie = _get_movie_or_403(movie_repo, movie_id, current_user.user_id)
    latest_job = get_download_ready_job(job_repo, movie.id)
    settings = get_settings()
    file_path = resolve_local_generated_file_path(
        latest_job.output_url or "",
        local_storage_dir=settings.local_storage_dir,
        local_public_base_url=settings.local_public_base_url,
    )
    title = build_movie_title(movie)
    return FileResponse(
        path=file_path,
        media_type="video/mp4",
        filename=build_download_filename(title, file_path.suffix),
        headers={"Cache-Control": "no-store"},
    )


@router.post("/{movie_id}/share", response_model=schemas.ShareMovieResponse)
async def share_movie(
    movie_id: int,
    request: Request,
    db: Session = Depends(get_db_session),
    current_user: AccessTokenClaims = Depends(get_current_user),
) -> schemas.ShareMovieResponse:
    """현재 사용자의 특정 영화 공유 URL을 생성하여 반환합니다."""
    movie_repo = SQLAlchemyMovieRepository(db)
    movie = _get_movie_or_403(movie_repo, movie_id, current_user.user_id)
    base_url = str(request.base_url).rstrip("/")
    title = build_movie_title(movie)
    share_url = f"{base_url}/movies/{movie_id}"
    return schemas.ShareMovieResponse(
        message=f"{title} 공유 링크가 생성되었습니다.",
        movie_id=movie.id,
        title=title,
        share_url=share_url,
    )


@router.get("/{movie_id}/similar", response_model=schemas.SimilarMoviesResponse)
async def get_similar_movies(
    movie_id: int,
    db: Session = Depends(get_db_session),
    current_user: AccessTokenClaims = Depends(get_current_user),
) -> schemas.SimilarMoviesResponse:
    """현재 사용자 영화의 테마 기반으로 유사한 유명 영화 최대 4편을 추천합니다."""
    movie_repo = SQLAlchemyMovieRepository(db)
    movie = _get_movie_or_403(movie_repo, movie_id, current_user.user_id)
    genre = THEME_NAMES.get(movie.theme_id, "인생 영화")
    return schemas.SimilarMoviesResponse(
        movie_id=movie.id,
        similar_movies=build_similar_movies(genre),
    )


def build_movie_summary(
    movie: Movie,
    latest_job: VideoGenerationJob | None,
) -> schemas.MovieSummary:
    thumbnail_url = latest_job.thumbnail_url if latest_job is not None else None
    output_url = latest_job.output_url if latest_job is not None else None
    return schemas.MovieSummary(
        id=movie.id,
        title=build_movie_title(movie),
        thumbnail=thumbnail_url or "",
        genre=THEME_NAMES.get(movie.theme_id, "인생 영화"),
        status=movie.status.value,
        output_url=output_url,
        thumbnail_url=thumbnail_url,
    )


def get_download_ready_job(
    job_repo: SQLAlchemyVideoGenerationJobRepository,
    movie_id: int,
) -> VideoGenerationJob:
    latest_job = job_repo.get_latest_by_movie_id(movie_id)
    if latest_job is None or latest_job.status != VideoGenerationJobStatus.SUCCEEDED or not latest_job.output_url:
        raise AppError(
            status_code=409,
            code="MOVIE_DOWNLOAD_NOT_READY",
            title="Movie Download Not Ready",
            detail="아직 다운로드할 수 있는 생성 완료 영화가 없습니다.",
            type_="movie_download_not_ready",
        )
    return latest_job


def resolve_local_generated_file_path(
    output_url: str,
    *,
    local_storage_dir: str,
    local_public_base_url: str,
) -> Path:
    parsed_url = urlparse(output_url)
    public_base_path = "/" + local_public_base_url.strip("/")
    output_path = unquote(parsed_url.path)
    if not output_path.startswith(f"{public_base_path}/"):
        raise AppError(
            status_code=422,
            code="MOVIE_DOWNLOAD_UNSUPPORTED_URL",
            title="Movie Download Unsupported URL",
            detail="현재 저장소에서 직접 다운로드할 수 없는 영화 URL입니다.",
            type_="movie_download_unsupported_url",
        )

    relative_path = output_path.removeprefix(f"{public_base_path}/")
    storage_root = Path(local_storage_dir).resolve()
    file_path = (storage_root / relative_path).resolve()
    if storage_root not in file_path.parents:
        raise AppError(
            status_code=400,
            code="INVALID_DOWNLOAD_PATH",
            title="Invalid Download Path",
            detail="다운로드 파일 경로가 올바르지 않습니다.",
            type_="invalid_download_path",
        )
    if not file_path.is_file():
        raise AppError(
            status_code=404,
            code="MOVIE_DOWNLOAD_FILE_NOT_FOUND",
            title="Movie Download File Not Found",
            detail="생성된 영화 파일을 찾을 수 없습니다.",
            type_="movie_download_file_not_found",
        )
    return file_path


def build_movie_download_url(movie_id: int, output_url: str | None) -> str | None:
    if not output_url:
        return None

    local_public_base_path = "/" + get_settings().local_public_base_url.strip("/")
    if urlparse(output_url).path.startswith(f"{local_public_base_path}/"):
        return f"/api/movies/{movie_id}/download/file"
    return output_url


def build_download_filename(title: str, extension: str) -> str:
    safe_title = "".join(
        character if character.isalnum() or character in {" ", "-", "_"} else "_"
        for character in title
    ).strip()
    normalized_extension = extension if extension.startswith(".") else f".{extension}"
    return f"{safe_title or 'my-life-movie'}{normalized_extension or '.mp4'}"


def build_movie_detail(
    movie: Movie,
    latest_job: VideoGenerationJob | None,
) -> schemas.Movie:
    summary = build_movie_summary(movie, latest_job)
    return schemas.Movie(
        id=summary.id,
        title=summary.title,
        description=build_movie_description(movie),
        thumbnail=summary.thumbnail,
        genre=summary.genre,
        sentiment=build_movie_sentiment(movie),
        status=summary.status,
        output_url=summary.output_url,
        thumbnail_url=summary.thumbnail_url,
        ost=build_movie_ost(movie),
        similar_movies=build_similar_movies(summary.genre),
    )


def build_movie_title(movie: Movie) -> str:
    story_brief = movie.story_brief if isinstance(movie.story_brief, dict) else {}
    for key in ("title", "movie_title"):
        value = story_brief.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    if movie.current_draft:
        first_line = movie.current_draft.strip().splitlines()[0]
        if first_line:
            return first_line[:40]

    return f"내 인생 영화 #{movie.id}"


def build_movie_description(movie: Movie) -> str:
    if movie.current_draft and movie.current_draft.strip():
        return movie.current_draft.strip()
    if movie.generation_prompt and movie.generation_prompt.strip():
        return movie.generation_prompt.strip()
    return "아직 영화 시나리오를 준비 중입니다."


def build_movie_sentiment(movie: Movie) -> str:
    story_brief = movie.story_brief if isinstance(movie.story_brief, dict) else {}
    for key in ("core_emotion", "emotion", "mood", "tone"):
        value = story_brief.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "기록중"


def build_movie_ost(movie: Movie) -> list[schemas.OstTrack]:
    if movie.music_id is None:
        return []
    return [
        schemas.OstTrack(
            title=f"선택한 음악 #{movie.music_id}",
            artist="My Life Movie",
        )
    ]


def build_similar_movies(genre: str) -> list[schemas.SimilarMovie]:
    return [
        schemas.SimilarMovie(**movie)
        for movie in FAMOUS_MOVIES_BY_GENRE.get(genre, [])[:4]
    ]
