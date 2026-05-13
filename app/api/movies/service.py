"""영화 데이터 서비스 (현재 in-memory mock, 추후 DB 연동으로 교체)."""

import random

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
        genre="하이틴",
        sentiment="따뜻함",
        status="COMPLETED",
        output_url=None,
        thumbnail_url=None,
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
        genre="지브리",
        sentiment="설렘",
        status="COMPLETED",
        output_url=None,
        thumbnail_url=None,
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
        genre="재패니즈 노스탤지아",
        sentiment="그리움",
        status="COMPLETED",
        output_url=None,
        thumbnail_url=None,
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

# 장르별 유명 영화 풀 (추천 후보, ID는 101부터 시작)
# TODO: DB 연동 시 실제 테이블로 교체
_famous_movies: list[dict] = [
    # ── 하이틴 ──────────────────────────────────────────────────
    {"id": 101, "title": "브렉퍼스트 클럽", "genre": "하이틴", "thumbnail": "https://picsum.photos/seed/fam101/400/600"},
    {"id": 102, "title": "퀸카로 살아남는 법", "genre": "하이틴", "thumbnail": "https://picsum.photos/seed/fam102/400/600"},
    {"id": 103, "title": "사랑할 수 없는 10가지 이유", "genre": "하이틴", "thumbnail": "https://picsum.photos/seed/fam103/400/600"},
    {"id": 104, "title": "페리스 뷸러의 해방", "genre": "하이틴", "thumbnail": "https://picsum.photos/seed/fam104/400/600"},
    {"id": 105, "title": "이지 에이", "genre": "하이틴", "thumbnail": "https://picsum.photos/seed/fam105/400/600"},
    {"id": 106, "title": "슈퍼배드", "genre": "하이틴", "thumbnail": "https://picsum.photos/seed/fam106/400/600"},
    {"id": 107, "title": "주노", "genre": "하이틴", "thumbnail": "https://picsum.photos/seed/fam107/400/600"},
    {"id": 108, "title": "레이디 버드", "genre": "하이틴", "thumbnail": "https://picsum.photos/seed/fam108/400/600"},
    {"id": 109, "title": "클루리스", "genre": "하이틴", "thumbnail": "https://picsum.photos/seed/fam109/400/600"},
    {"id": 110, "title": "프리티 인 핑크", "genre": "하이틴", "thumbnail": "https://picsum.photos/seed/fam110/400/600"},
    # ── 사이버펑크 ──────────────────────────────────────────────
    {"id": 201, "title": "블레이드 러너 2049", "genre": "사이버펑크", "thumbnail": "https://picsum.photos/seed/fam201/400/600"},
    {"id": 202, "title": "매트릭스", "genre": "사이버펑크", "thumbnail": "https://picsum.photos/seed/fam202/400/600"},
    {"id": 203, "title": "공각기동대", "genre": "사이버펑크", "thumbnail": "https://picsum.photos/seed/fam203/400/600"},
    {"id": 204, "title": "아키라", "genre": "사이버펑크", "thumbnail": "https://picsum.photos/seed/fam204/400/600"},
    {"id": 205, "title": "트론: 새로운 시작", "genre": "사이버펑크", "thumbnail": "https://picsum.photos/seed/fam205/400/600"},
    {"id": 206, "title": "알리타: 배틀 엔젤", "genre": "사이버펑크", "thumbnail": "https://picsum.photos/seed/fam206/400/600"},
    {"id": 207, "title": "업그레이드", "genre": "사이버펑크", "thumbnail": "https://picsum.photos/seed/fam207/400/600"},
    {"id": 208, "title": "엑스 마키나", "genre": "사이버펑크", "thumbnail": "https://picsum.photos/seed/fam208/400/600"},
    {"id": 209, "title": "다크 시티", "genre": "사이버펑크", "thumbnail": "https://picsum.photos/seed/fam209/400/600"},
    {"id": 210, "title": "레디 플레이어 원", "genre": "사이버펑크", "thumbnail": "https://picsum.photos/seed/fam210/400/600"},
    # ── 무성영화 ────────────────────────────────────────────────
    {"id": 301, "title": "아티스트", "genre": "무성영화", "thumbnail": "https://picsum.photos/seed/fam301/400/600"},
    {"id": 302, "title": "메트로폴리스", "genre": "무성영화", "thumbnail": "https://picsum.photos/seed/fam302/400/600"},
    {"id": 303, "title": "시티 라이트", "genre": "무성영화", "thumbnail": "https://picsum.photos/seed/fam303/400/600"},
    {"id": 304, "title": "황금광 시대", "genre": "무성영화", "thumbnail": "https://picsum.photos/seed/fam304/400/600"},
    {"id": 305, "title": "노스페라투", "genre": "무성영화", "thumbnail": "https://picsum.photos/seed/fam305/400/600"},
    {"id": 306, "title": "선라이즈", "genre": "무성영화", "thumbnail": "https://picsum.photos/seed/fam306/400/600"},
    {"id": 307, "title": "더 키드", "genre": "무성영화", "thumbnail": "https://picsum.photos/seed/fam307/400/600"},
    {"id": 308, "title": "잔다르크의 수난", "genre": "무성영화", "thumbnail": "https://picsum.photos/seed/fam308/400/600"},
    {"id": 309, "title": "더 제너럴", "genre": "무성영화", "thumbnail": "https://picsum.photos/seed/fam309/400/600"},
    {"id": 310, "title": "칼리가리 박사의 밀실", "genre": "무성영화", "thumbnail": "https://picsum.photos/seed/fam310/400/600"},
    # ── 동화 ────────────────────────────────────────────────────
    {"id": 401, "title": "신데렐라", "genre": "동화", "thumbnail": "https://picsum.photos/seed/fam401/400/600"},
    {"id": 402, "title": "미녀와 야수", "genre": "동화", "thumbnail": "https://picsum.photos/seed/fam402/400/600"},
    {"id": 403, "title": "라푼젤", "genre": "동화", "thumbnail": "https://picsum.photos/seed/fam403/400/600"},
    {"id": 404, "title": "마법에 걸린 사랑", "genre": "동화", "thumbnail": "https://picsum.photos/seed/fam404/400/600"},
    {"id": 405, "title": "슈렉", "genre": "동화", "thumbnail": "https://picsum.photos/seed/fam405/400/600"},
    {"id": 406, "title": "말레피센트", "genre": "동화", "thumbnail": "https://picsum.photos/seed/fam406/400/600"},
    {"id": 407, "title": "에버 애프터", "genre": "동화", "thumbnail": "https://picsum.photos/seed/fam407/400/600"},
    {"id": 408, "title": "인투 더 우즈", "genre": "동화", "thumbnail": "https://picsum.photos/seed/fam408/400/600"},
    {"id": 409, "title": "겨울왕국", "genre": "동화", "thumbnail": "https://picsum.photos/seed/fam409/400/600"},
    {"id": 410, "title": "모아나", "genre": "동화", "thumbnail": "https://picsum.photos/seed/fam410/400/600"},
    # ── 재패니즈 노스탤지아 ──────────────────────────────────────
    {"id": 501, "title": "이 세상의 한 구석에", "genre": "재패니즈 노스탤지아", "thumbnail": "https://picsum.photos/seed/fam501/400/600"},
    {"id": 502, "title": "반딧불이의 묘", "genre": "재패니즈 노스탤지아", "thumbnail": "https://picsum.photos/seed/fam502/400/600"},
    {"id": 503, "title": "추억은 방울방울", "genre": "재패니즈 노스탤지아", "thumbnail": "https://picsum.photos/seed/fam503/400/600"},
    {"id": 504, "title": "마니와 있으면", "genre": "재패니즈 노스탤지아", "thumbnail": "https://picsum.photos/seed/fam504/400/600"},
    {"id": 505, "title": "늑대아이", "genre": "재패니즈 노스탤지아", "thumbnail": "https://picsum.photos/seed/fam505/400/600"},
    {"id": 506, "title": "귀를 기울이면", "genre": "재패니즈 노스탤지아", "thumbnail": "https://picsum.photos/seed/fam506/400/600"},
    {"id": 507, "title": "바다가 들린다", "genre": "재패니즈 노스탤지아", "thumbnail": "https://picsum.photos/seed/fam507/400/600"},
    {"id": 508, "title": "초속 5센티미터", "genre": "재패니즈 노스탤지아", "thumbnail": "https://picsum.photos/seed/fam508/400/600"},
    {"id": 509, "title": "목소리의 형태", "genre": "재패니즈 노스탤지아", "thumbnail": "https://picsum.photos/seed/fam509/400/600"},
    {"id": 510, "title": "언어의 정원", "genre": "재패니즈 노스탤지아", "thumbnail": "https://picsum.photos/seed/fam510/400/600"},
    # ── 지브리 ──────────────────────────────────────────────────
    {"id": 601, "title": "센과 치히로의 행방불명", "genre": "지브리", "thumbnail": "https://picsum.photos/seed/fam601/400/600"},
    {"id": 602, "title": "이웃집 토토로", "genre": "지브리", "thumbnail": "https://picsum.photos/seed/fam602/400/600"},
    {"id": 603, "title": "모노노케 히메", "genre": "지브리", "thumbnail": "https://picsum.photos/seed/fam603/400/600"},
    {"id": 604, "title": "하울의 움직이는 성", "genre": "지브리", "thumbnail": "https://picsum.photos/seed/fam604/400/600"},
    {"id": 605, "title": "바람계곡의 나우시카", "genre": "지브리", "thumbnail": "https://picsum.photos/seed/fam605/400/600"},
    {"id": 606, "title": "천공의 성 라퓨타", "genre": "지브리", "thumbnail": "https://picsum.photos/seed/fam606/400/600"},
    {"id": 607, "title": "마녀 배달부 키키", "genre": "지브리", "thumbnail": "https://picsum.photos/seed/fam607/400/600"},
    {"id": 608, "title": "붉은 돼지", "genre": "지브리", "thumbnail": "https://picsum.photos/seed/fam608/400/600"},
    {"id": 609, "title": "가구야 공주 이야기", "genre": "지브리", "thumbnail": "https://picsum.photos/seed/fam609/400/600"},
    {"id": 610, "title": "마루 밑 아리에티", "genre": "지브리", "thumbnail": "https://picsum.photos/seed/fam610/400/600"},
]


def list_movies() -> list[MovieSummary]:
    logger.info("movie_list_requested", extra={"event": "movie_list_requested", "count": len(_movies)})
    return [
        MovieSummary(
            id=m.id,
            title=m.title,
            thumbnail=m.thumbnail,
            genre=m.genre,
            status=m.status,
            output_url=m.output_url,
            thumbnail_url=m.thumbnail_url,
        )
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


def get_similar_movies(movie_id: int, limit: int = 4) -> list[SimilarMovie]:
    """같은 장르의 유명 영화 풀에서 랜덤으로 최대 limit편을 추천한다."""
    base = get_movie(movie_id)  # 존재하지 않으면 404 raise

    candidates = [m for m in _famous_movies if m["genre"] == base.genre]
    selected = random.sample(candidates, min(limit, len(candidates)))

    logger.info(
        "similar_movies_requested",
        extra={"event": "similar_movies_requested", "movie_id": movie_id, "genre": base.genre, "count": len(selected)},
    )
    return [SimilarMovie(id=m["id"], title=m["title"], thumbnail=m["thumbnail"]) for m in selected]
