from fastapi import APIRouter

from app.api.movies import schemas, service

router = APIRouter(prefix="/movies", tags=["movies"])


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
