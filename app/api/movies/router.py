import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from sqlalchemy.orm import Session

from app.api.movies import schemas
from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.core.openapi import (
    AUTH_REQUIRED_RESPONSE,
    COMMON_PROBLEM_RESPONSES,
    FORBIDDEN_RESPONSE,
    INVALID_FILE_TYPE_RESPONSE,
    MOVIE_NOT_FOUND_RESPONSE,
)
from app.db.session import get_db_session
from app.models.movie import Movie
from app.models.video_generation_job import VideoGenerationJob
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

router = APIRouter(prefix="/api/movies", tags=["영화"])

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

_AUTH_MOVIE_RESPONSES = {
    401: AUTH_REQUIRED_RESPONSE,
    403: FORBIDDEN_RESPONSE,
    404: MOVIE_NOT_FOUND_RESPONSE,
    **COMMON_PROBLEM_RESPONSES,
}


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


@router.post(
    "/draft",
    response_model=CreateDraftResponse,
    summary="영화 초안 생성",
    description=(
        "`theme_id`로 테마를 선택해 영화 초안을 생성합니다. "
        "응답의 `movie_id`는 이후 음악 선택·파일 업로드·AI 채팅·요약·생성 시작 등 "
        "모든 영화 제작 요청에 사용됩니다. Bearer access token이 필요합니다."
    ),
    responses={
        200: {"description": "영화 초안 생성 성공입니다."},
        401: AUTH_REQUIRED_RESPONSE,
        **COMMON_PROBLEM_RESPONSES,
    },
)
async def create_draft(
    request: CreateDraftRequest,
    db: Session = Depends(get_db_session),
    current_user: AccessTokenClaims = Depends(get_current_user),
):
    """테마를 선택해 영화 초안을 생성합니다. movie_id를 반환하며 이후 모든 요청에 사용됩니다."""
    repo = SQLAlchemyMovieRepository(db)
    movie = repo.create(user_id=current_user.user_id, theme_id=request.theme_id)
    return CreateDraftResponse(movie_id=movie.id, status=movie.status.value)


@router.put(
    "/{movie_id}/music",
    summary="음악 선택 저장",
    description=(
        "사용자가 선택한 `music_id`를 영화에 저장합니다. "
        "이후 `/summary` 조회 시 선택된 음악 정보가 포함됩니다. "
        "Bearer access token이 필요하며, 본인 영화에만 접근할 수 있습니다."
    ),
    responses={
        200: {"description": "음악 선택 저장 성공입니다."},
        **_AUTH_MOVIE_RESPONSES,
    },
)
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


@router.post(
    "/{movie_id}/files",
    response_model=FileUploadResponse,
    summary="파일 업로드",
    description=(
        "영화 제작에 사용할 파일(사진·영상·문서)을 업로드합니다. "
        "허용 확장자는 `jpg`, `jpeg`, `png`, `pdf`, `txt`, `mp4`, `mov`이며 "
        "그 외 확장자는 400 오류를 반환합니다. "
        "업로드된 파일은 `file_id`, `filename`, `type`, `extracted_text`로 응답됩니다."
    ),
    responses={
        200: {"description": "파일 업로드 성공입니다."},
        400: INVALID_FILE_TYPE_RESPONSE,
        **_AUTH_MOVIE_RESPONSES,
    },
)
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


@router.post(
    "/{movie_id}/chat",
    response_model=ChatResponse,
    summary="AI 채팅 (시나리오 수집)",
    description=(
        "사용자 `message`를 받아 OpenAI GPT로 AI 역질문(`ai_question`)과 "
        "현재 시나리오 초안(`current_draft`)을 반환합니다. "
        "채팅이 누적될수록 `story_brief`·`scene_plan`이 구체화되며 "
        "최종 `generation_prompt`가 완성됩니다."
    ),
    responses={
        200: {"description": "AI 채팅 응답 성공입니다."},
        **_AUTH_MOVIE_RESPONSES,
    },
)
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


@router.get(
    "/{movie_id}/chat",
    summary="AI 채팅 히스토리 조회",
    description=(
        "지금까지 진행된 AI 채팅 히스토리를 `history` 배열로 반환합니다. "
        "각 항목은 `role`(`user` 또는 `ai`)과 `message`로 구성됩니다."
    ),
    responses={
        200: {"description": "채팅 히스토리 반환 성공입니다."},
        **_AUTH_MOVIE_RESPONSES,
    },
)
async def get_chat_history(
    movie_id: int,
    db: Session = Depends(get_db_session),
    current_user: AccessTokenClaims = Depends(get_current_user),
):
    """지금까지의 AI 채팅 히스토리를 반환합니다."""
    repo = SQLAlchemyMovieRepository(db)
    movie = _get_movie_or_403(repo, movie_id, current_user.user_id)
    return {"history": movie.chat_history or []}


@router.get(
    "/{movie_id}/summary",
    response_model=SummaryResponse,
    summary="최종 입력 요약 조회",
    description=(
        "피드백 페이지에서 사용자에게 보여줄 최종 입력 요약을 반환합니다. "
        "응답에는 AI 채팅으로 완성된 `prompt`, 업로드한 `files`, 선택한 `theme`·`music`, "
        "그리고 영상 생성에 필요한 `story_brief`·`scene_plan`·`generation_prompt`가 포함됩니다."
    ),
    responses={
        200: {"description": "최종 입력 요약 반환 성공입니다."},
        **_AUTH_MOVIE_RESPONSES,
    },
)
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


@router.get(
    "/{movie_id}/generation",
    response_model=GenerationStatusResponse,
    summary="영상 생성 상태 조회",
    description=(
        "가장 최신 영상 생성 Job의 상태를 조회합니다. "
        "`status`는 `QUEUED`·`PROCESSING`·`SUCCEEDED`·`FAILED`·`CANCELLED` 중 하나이며, "
        "`progress`(0~100), `output_url`, `thumbnail_url`이 함께 반환됩니다. "
        "생성 완료 시 `output_url`로 영상에 접근할 수 있습니다."
    ),
    responses={
        200: {"description": "영상 생성 상태 반환 성공입니다."},
        **_AUTH_MOVIE_RESPONSES,
    },
)
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


@router.post(
    "/{movie_id}/generate",
    response_model=GenerationRequestResponse,
    summary="영상 생성 시작",
    description=(
        "영화의 `generation_prompt`와 수집된 입력을 바탕으로 영상 생성 Job을 생성합니다. "
        "Job은 `QUEUED` 상태로 즉시 반환되며, 실제 생성은 백그라운드에서 진행됩니다. "
        "생성 상태는 `GET /{movie_id}/generation`으로 폴링해서 확인하세요."
    ),
    responses={
        200: {"description": "영상 생성 요청 접수 성공입니다."},
        **_AUTH_MOVIE_RESPONSES,
    },
)
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


@router.post(
    "/{movie_id}/generation/cancel",
    response_model=GenerationStatusResponse,
    summary="영상 생성 취소",
    description=(
        "`QUEUED` 또는 `PROCESSING` 상태의 영상 생성 Job을 취소합니다. "
        "취소된 Job은 `CANCELLED` 상태가 되며, 이후 `POST /{movie_id}/generate`로 재시작할 수 있습니다."
    ),
    responses={
        200: {"description": "영상 생성 취소 성공입니다."},
        **_AUTH_MOVIE_RESPONSES,
    },
)
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


@router.get(
    "",
    response_model=list[schemas.MovieSummary],
    summary="내 영화 목록 조회",
    description=(
        "Bearer access token으로 인증된 사용자의 영화 목록을 반환합니다. "
        "각 항목에는 `id`, `title`, `genre`, `status`, `thumbnail_url`, `output_url`이 포함됩니다. "
        "다른 사용자의 영화는 조회되지 않습니다."
    ),
    responses={
        200: {"description": "영화 목록 반환 성공입니다."},
        401: AUTH_REQUIRED_RESPONSE,
        **COMMON_PROBLEM_RESPONSES,
    },
)
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


@router.get(
    "/{movie_id}",
    response_model=schemas.Movie,
    summary="영화 상세 조회",
    description=(
        "특정 영화의 상세 정보를 반환합니다. "
        "응답에는 `title`, `description`, `genre`, `sentiment`, `status`, "
        "`output_url`, `thumbnail_url`, `ost`, `similar_movies`가 포함됩니다. "
        "본인 영화가 아니면 403을 반환합니다."
    ),
    responses={
        200: {"description": "영화 상세 반환 성공입니다."},
        **_AUTH_MOVIE_RESPONSES,
    },
)
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


@router.delete(
    "/{movie_id}",
    response_model=schemas.DeleteMovieResponse,
    summary="영화 삭제",
    description=(
        "특정 영화와 연관된 모든 데이터를 삭제합니다. "
        "삭제는 복구가 불가능하며, 본인 영화가 아니면 403을 반환합니다."
    ),
    responses={
        200: {"description": "영화 삭제 성공입니다."},
        **_AUTH_MOVIE_RESPONSES,
    },
)
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


@router.get(
    "/{movie_id}/download",
    response_model=schemas.DownloadMovieResponse,
    summary="영화 다운로드 정보 조회",
    description=(
        "영상 생성이 완료된 영화의 다운로드 정보를 반환합니다. "
        "`output_url`로 생성된 영상 파일에 직접 접근할 수 있습니다. "
        "아직 생성이 완료되지 않은 경우 `output_url`은 `null`로 반환됩니다."
    ),
    responses={
        200: {"description": "다운로드 정보 반환 성공입니다."},
        **_AUTH_MOVIE_RESPONSES,
    },
)
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
    return schemas.DownloadMovieResponse(
        message=f"{title} 다운로드가 준비되었습니다.",
        movie_id=movie.id,
        title=title,
        output_url=latest_job.output_url if latest_job is not None else None,
    )


@router.post(
    "/{movie_id}/share",
    response_model=schemas.ShareMovieResponse,
    summary="영화 공유 URL 생성",
    description=(
        "영화의 공유 URL을 생성해 반환합니다. "
        "`share_url`은 `{base_url}/movies/{movie_id}` 형태이며, "
        "해당 URL을 통해 영화 결과 페이지에 접근할 수 있습니다."
    ),
    responses={
        200: {"description": "공유 URL 생성 성공입니다."},
        **_AUTH_MOVIE_RESPONSES,
    },
)
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


@router.get(
    "/{movie_id}/similar",
    response_model=schemas.SimilarMoviesResponse,
    summary="유사 영화 추천",
    description=(
        "영화의 테마(장르)를 기반으로 유사한 유명 영화 최대 4편을 추천합니다. "
        "결과물 페이지에서 '이런 영화는 어때요?' 섹션에 활용됩니다. "
        "각 항목은 `id`, `title`, `thumbnail`로 구성됩니다."
    ),
    responses={
        200: {"description": "유사 영화 추천 성공입니다."},
        **_AUTH_MOVIE_RESPONSES,
    },
)
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
        similar_movies=[],
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
