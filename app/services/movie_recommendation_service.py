from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import Settings


@dataclass(frozen=True)
class RecommendedMovie:
    id: int
    title: str
    thumbnail: str
    external_url: str | None = None
    provider: str = "fallback"


class MovieMetadataProvider(Protocol):
    def search_movie(self, title: str) -> RecommendedMovie | None:
        ...


class TMDBMovieMetadataProvider:
    def __init__(
        self,
        *,
        access_token: str,
        api_base_url: str,
        image_base_url: str,
        poster_size: str,
        language: str,
        timeout_seconds: float,
        client: httpx.Client | None = None,
    ) -> None:
        self.access_token = access_token
        self.api_base_url = api_base_url.rstrip("/")
        self.image_base_url = image_base_url.rstrip("/")
        self.poster_size = poster_size.strip("/")
        self.language = language
        self.client = client or httpx.Client(timeout=timeout_seconds)

    def search_movie(self, title: str) -> RecommendedMovie | None:
        if not self.access_token:
            return None

        response = self.client.get(
            f"{self.api_base_url}/search/movie",
            headers={"Authorization": f"Bearer {self.access_token}"},
            params={
                "query": title,
                "language": self.language,
                "include_adult": "false",
                "page": 1,
            },
        )
        response.raise_for_status()
        results = response.json().get("results")
        if not isinstance(results, list) or not results:
            return None

        return build_tmdb_recommendation(results[0], self.image_base_url, self.poster_size)


class MovieRecommendationService:
    def __init__(
        self,
        *,
        metadata_provider: MovieMetadataProvider | None = None,
    ) -> None:
        self.metadata_provider = metadata_provider

    def recommend_by_genre(self, genre: str, *, limit: int = 4) -> list[RecommendedMovie]:
        fallback_movies = fallback_movies_by_genre(genre)[:limit]
        if self.metadata_provider is None:
            return fallback_movies

        recommendations: list[RecommendedMovie] = []
        for fallback_movie in fallback_movies:
            try:
                recommended_movie = self.metadata_provider.search_movie(fallback_movie.title)
            except Exception:
                recommended_movie = None
            recommendations.append(recommended_movie or fallback_movie)
        return recommendations


def build_movie_recommendation_service(settings: Settings) -> MovieRecommendationService:
    provider = None
    if settings.tmdb_access_token:
        provider = TMDBMovieMetadataProvider(
            access_token=settings.tmdb_access_token,
            api_base_url=settings.tmdb_api_base_url,
            image_base_url=settings.tmdb_image_base_url,
            poster_size=settings.tmdb_poster_size,
            language=settings.tmdb_language,
            timeout_seconds=settings.tmdb_timeout_seconds,
        )
    return MovieRecommendationService(metadata_provider=provider)


def build_tmdb_recommendation(data: dict, image_base_url: str, poster_size: str) -> RecommendedMovie | None:
    movie_id = data.get("id")
    title = data.get("title") or data.get("name")
    poster_path = data.get("poster_path")
    if not isinstance(movie_id, int) or not isinstance(title, str) or not title:
        return None

    thumbnail = ""
    if isinstance(poster_path, str) and poster_path:
        thumbnail = f"{image_base_url.rstrip('/')}/{poster_size.strip('/')}/{poster_path.lstrip('/')}"

    return RecommendedMovie(
        id=movie_id,
        title=title,
        thumbnail=thumbnail,
        external_url=f"https://www.themoviedb.org/movie/{movie_id}",
        provider="tmdb",
    )


def fallback_movies_by_genre(genre: str) -> list[RecommendedMovie]:
    return [
        RecommendedMovie(**movie)
        for movie in FALLBACK_MOVIES_BY_GENRE.get(genre, [])
    ]


FALLBACK_MOVIES_BY_GENRE = {
    "하이틴": [
        {
            "id": 101,
            "title": "브렉퍼스트 클럽",
            "thumbnail": "https://picsum.photos/seed/fam101/400/600",
            "external_url": "https://www.themoviedb.org/search?query=The%20Breakfast%20Club",
        },
        {
            "id": 102,
            "title": "퀸카로 살아남는 법",
            "thumbnail": "https://picsum.photos/seed/fam102/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Mean%20Girls",
        },
        {
            "id": 103,
            "title": "사랑할 수 없는 10가지 이유",
            "thumbnail": "https://picsum.photos/seed/fam103/400/600",
            "external_url": "https://www.themoviedb.org/search?query=10%20Things%20I%20Hate%20About%20You",
        },
        {
            "id": 104,
            "title": "이지 에이",
            "thumbnail": "https://picsum.photos/seed/fam104/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Easy%20A",
        },
    ],
    "사이버펑크": [
        {
            "id": 201,
            "title": "블레이드 러너 2049",
            "thumbnail": "https://picsum.photos/seed/fam201/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Blade%20Runner%202049",
        },
        {
            "id": 202,
            "title": "매트릭스",
            "thumbnail": "https://picsum.photos/seed/fam202/400/600",
            "external_url": "https://www.themoviedb.org/search?query=The%20Matrix",
        },
        {
            "id": 203,
            "title": "공각기동대",
            "thumbnail": "https://picsum.photos/seed/fam203/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Ghost%20in%20the%20Shell",
        },
        {
            "id": 204,
            "title": "아키라",
            "thumbnail": "https://picsum.photos/seed/fam204/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Akira",
        },
    ],
    "무성영화": [
        {
            "id": 301,
            "title": "아티스트",
            "thumbnail": "https://picsum.photos/seed/fam301/400/600",
            "external_url": "https://www.themoviedb.org/search?query=The%20Artist",
        },
        {
            "id": 302,
            "title": "메트로폴리스",
            "thumbnail": "https://picsum.photos/seed/fam302/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Metropolis",
        },
        {
            "id": 303,
            "title": "시티 라이트",
            "thumbnail": "https://picsum.photos/seed/fam303/400/600",
            "external_url": "https://www.themoviedb.org/search?query=City%20Lights",
        },
        {
            "id": 304,
            "title": "황금광 시대",
            "thumbnail": "https://picsum.photos/seed/fam304/400/600",
            "external_url": "https://www.themoviedb.org/search?query=The%20Gold%20Rush",
        },
    ],
    "동화": [
        {
            "id": 401,
            "title": "신데렐라",
            "thumbnail": "https://picsum.photos/seed/fam401/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Cinderella",
        },
        {
            "id": 402,
            "title": "미녀와 야수",
            "thumbnail": "https://picsum.photos/seed/fam402/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Beauty%20and%20the%20Beast",
        },
        {
            "id": 403,
            "title": "라푼젤",
            "thumbnail": "https://picsum.photos/seed/fam403/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Tangled",
        },
        {
            "id": 404,
            "title": "마법에 걸린 사랑",
            "thumbnail": "https://picsum.photos/seed/fam404/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Enchanted",
        },
    ],
    "재패니즈 노스탤지아": [
        {
            "id": 501,
            "title": "이 세상의 한 구석에",
            "thumbnail": "https://picsum.photos/seed/fam501/400/600",
            "external_url": "https://www.themoviedb.org/search?query=In%20This%20Corner%20of%20the%20World",
        },
        {
            "id": 502,
            "title": "추억은 방울방울",
            "thumbnail": "https://picsum.photos/seed/fam502/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Only%20Yesterday",
        },
        {
            "id": 503,
            "title": "귀를 기울이면",
            "thumbnail": "https://picsum.photos/seed/fam503/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Whisper%20of%20the%20Heart",
        },
        {
            "id": 504,
            "title": "초속 5센티미터",
            "thumbnail": "https://picsum.photos/seed/fam504/400/600",
            "external_url": "https://www.themoviedb.org/search?query=5%20Centimeters%20per%20Second",
        },
    ],
    "지브리": [
        {
            "id": 601,
            "title": "센과 치히로의 행방불명",
            "thumbnail": "https://picsum.photos/seed/fam601/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Spirited%20Away",
        },
        {
            "id": 602,
            "title": "하울의 움직이는 성",
            "thumbnail": "https://picsum.photos/seed/fam602/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Howl%27s%20Moving%20Castle",
        },
        {
            "id": 603,
            "title": "모노노케 히메",
            "thumbnail": "https://picsum.photos/seed/fam603/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Princess%20Mononoke",
        },
        {
            "id": 604,
            "title": "마녀 배달부 키키",
            "thumbnail": "https://picsum.photos/seed/fam604/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Kiki%27s%20Delivery%20Service",
        },
    ],
}
