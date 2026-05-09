"""영화 데이터 서비스 (현재 in-memory mock, 추후 DB 연동으로 교체)."""

from app.api.movies.schemas import Movie, MovieSummary, OstTrack, SimilarMovie
from app.core.errors import AppError
from app.core.logging import get_logger

logger = get_logger(__name__)

# TODO: DB 연동 시 이 mock 데이터 제거
_movies: list[Movie] = [
    Movie(
        id=1,
        title="나의 로맨틱 코드 여정",
        description=(
            "새벽까지 이어지는 디버깅 세션, 동료들과 나눈 진솔한 대화, "
            "그리고 배포가 성공하던 순간의 짜릿함. "
            "코드 한 줄 한 줄에 녹아든 나의 이야기를 담은 따뜻한 성장 로맨스."
        ),
        thumbnail="https://picsum.photos/seed/movie1/400/600",
        genre="로맨스",
        sentiment="따뜻함",
        ost=[
            OstTrack(title="Dynamite", artist="BTS", spotify_url="https://open.spotify.com/track/0t1kP63rueHleOhQkYSXFY"),
            OstTrack(title="좋은 날", artist="아이유", spotify_url="https://open.spotify.com/track/1rfofaqEpACxVEHIZBJe6W"),
        ],
        similar_movies=[
            SimilarMovie(id=2, title="청춘의 기록", thumbnail="https://picsum.photos/seed/movie2/400/600"),
            SimilarMovie(id=3, title="소울 사운드트랙", thumbnail="https://picsum.photos/seed/movie3/400/600"),
        ],
    ),
    Movie(
        id=2,
        title="청춘의 기록",
        description=(
            "스물셋, 첫 사회생활의 두려움과 설렘. "
            "카카오톡 대화창에 가득 찬 친구들과의 일상, 이력서를 고쳐 쓰며 보낸 밤들. "
            "그 모든 순간이 모여 완성된 나만의 청춘 드라마."
        ),
        thumbnail="https://picsum.photos/seed/movie2/400/600",
        genre="드라마",
        sentiment="설렘",
        ost=[
            OstTrack(title="Feel Good", artist="Dua Lipa"),
            OstTrack(title="봄날", artist="BTS", spotify_url="https://open.spotify.com/track/5rSoHSXqYZfSGDNLh2VqJF"),
        ],
        similar_movies=[
            SimilarMovie(id=1, title="나의 로맨틱 코드 여정", thumbnail="https://picsum.photos/seed/movie1/400/600"),
            SimilarMovie(id=3, title="소울 사운드트랙", thumbnail="https://picsum.photos/seed/movie3/400/600"),
        ],
    ),
    Movie(
        id=3,
        title="소울 사운드트랙",
        description=(
            "Spotify 플레이리스트에 담긴 800곡의 이야기. "
            "슬플 때 들었던 곡, 달릴 때 들었던 비트, 새벽 감성으로 반복 재생했던 그 노래들이 "
            "만들어낸 나만의 음악 영화."
        ),
        thumbnail="https://picsum.photos/seed/movie3/400/600",
        genre="뮤지컬",
        sentiment="그리움",
        ost=[
            OstTrack(title="Blinding Lights", artist="The Weeknd"),
            OstTrack(title="Celebrity", artist="아이유"),
        ],
        similar_movies=[
            SimilarMovie(id=1, title="나의 로맨틱 코드 여정", thumbnail="https://picsum.photos/seed/movie1/400/600"),
            SimilarMovie(id=2, title="청춘의 기록", thumbnail="https://picsum.photos/seed/movie2/400/600"),
        ],
    ),
]


def list_movies() -> list[MovieSummary]:
    logger.info("movie_list_requested", extra={"event": "movie_list_requested", "count": len(_movies)})
    return [
        MovieSummary(id=m.id, title=m.title, thumbnail=m.thumbnail, genre=m.genre)
        for m in _movies
    ]


def get_movie(movie_id: int) -> Movie:
    movie = next((m for m in _movies if m.id == movie_id), None)
    if movie is None:
        logger.warning(
            "movie_not_found",
            extra={"event": "movie_not_found", "movie_id": movie_id},
        )
        raise AppError(
            status_code=404,
            code="MOVIE_NOT_FOUND",
            title="Movie Not Found",
            detail=f"Movie with id {movie_id} does not exist.",
            type_="movie_not_found",
        )
    logger.info(
        "movie_detail_requested",
        extra={"event": "movie_detail_requested", "movie_id": movie_id},
    )
    return movie


def delete_movie(movie_id: int) -> None:
    global _movies
    before = len(_movies)
    _movies = [m for m in _movies if m.id != movie_id]
    if len(_movies) == before:
        logger.warning(
            "movie_not_found",
            extra={"event": "movie_not_found", "movie_id": movie_id},
        )
        raise AppError(
            status_code=404,
            code="MOVIE_NOT_FOUND",
            title="Movie Not Found",
            detail=f"Movie with id {movie_id} does not exist.",
            type_="movie_not_found",
        )
    logger.info(
        "movie_deleted",
        extra={"event": "movie_deleted", "movie_id": movie_id},
    )


def download_movie(movie_id: int) -> Movie:
    movie = get_movie(movie_id)
    logger.info(
        "movie_download_requested",
        extra={"event": "movie_download_requested", "movie_id": movie_id},
    )
    return movie


def share_movie(movie_id: int, base_url: str) -> tuple[Movie, str]:
    """공유 URL을 생성하고 반환한다."""
    movie = get_movie(movie_id)
    share_url = f"{base_url}/movies/{movie_id}"
    logger.info(
        "movie_shared",
        extra={"event": "movie_shared", "movie_id": movie_id, "share_url": share_url},
    )
    return movie, share_url
