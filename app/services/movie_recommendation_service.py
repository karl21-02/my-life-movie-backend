from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import Settings
from app.models.movie_recommendation import MovieRecommendation
from app.repositories.movie_recommendation_repository import MovieRecommendationRepository


@dataclass(frozen=True)
class RecommendedMovie:
    id: int
    title: str
    thumbnail: str
    external_url: str | None = None
    provider: str = "fallback"
    search_query: str | None = None


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
        recommendation_repository: MovieRecommendationRepository | None = None,
    ) -> None:
        self.metadata_provider = metadata_provider
        self.recommendation_repository = recommendation_repository

    def recommend_by_genre(self, genre: str, *, limit: int = 4) -> list[RecommendedMovie]:
        fallback_movies = fallback_movies_by_genre(genre)[:limit]
        if self.metadata_provider is None:
            return fallback_movies

        recommendations: list[RecommendedMovie] = []
        for fallback_movie in fallback_movies:
            try:
                recommended_movie = self.metadata_provider.search_movie(
                    fallback_movie.search_query or fallback_movie.title
                )
            except Exception:
                recommended_movie = None
            recommendations.append(recommended_movie or fallback_movie)
        return recommendations

    def get_or_create_for_movie(
        self,
        *,
        movie_id: int,
        genre: str,
        limit: int = 4,
    ) -> list[RecommendedMovie]:
        if self.recommendation_repository is None:
            return self.recommend_by_genre(genre, limit=limit)

        stored_recommendations = self.recommendation_repository.list_by_movie_id(movie_id)
        if stored_recommendations:
            return [
                recommended_movie_from_model(recommendation)
                for recommendation in stored_recommendations[:limit]
            ]

        recommendations = self.recommend_by_genre(genre, limit=limit)
        stored_recommendations = self.recommendation_repository.replace_for_movie(
            movie_id=movie_id,
            recommendations=[
                movie_recommendation_model_from_recommended_movie(
                    movie_id=movie_id,
                    recommendation=recommendation,
                    rank=index + 1,
                    genre=genre,
                )
                for index, recommendation in enumerate(recommendations)
            ],
        )
        return [
            recommended_movie_from_model(recommendation)
            for recommendation in stored_recommendations[:limit]
        ]


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


def recommended_movie_from_model(model: MovieRecommendation) -> RecommendedMovie:
    provider_movie_id = model.provider_movie_id
    parsed_id = int(provider_movie_id) if provider_movie_id and provider_movie_id.isdigit() else model.id
    return RecommendedMovie(
        id=parsed_id,
        title=model.title,
        thumbnail=model.poster_url,
        external_url=model.external_url,
        provider=model.provider,
    )


def movie_recommendation_model_from_recommended_movie(
    *,
    movie_id: int,
    recommendation: RecommendedMovie,
    rank: int,
    genre: str,
) -> MovieRecommendation:
    return MovieRecommendation(
        movie_id=movie_id,
        provider=recommendation.provider,
        provider_movie_id=str(recommendation.id),
        title=recommendation.title,
        poster_url=recommendation.thumbnail,
        external_url=recommendation.external_url,
        rank=rank,
        reason=f"{genre} 테마 기반 추천",
        metadata_json={"source": recommendation.provider},
    )


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
            "search_query": "The Breakfast Club",
        },
        {
            "id": 102,
            "title": "퀸카로 살아남는 법",
            "thumbnail": "https://picsum.photos/seed/fam102/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Mean%20Girls",
            "search_query": "Mean Girls",
        },
        {
            "id": 103,
            "title": "사랑할 수 없는 10가지 이유",
            "thumbnail": "https://picsum.photos/seed/fam103/400/600",
            "external_url": "https://www.themoviedb.org/search?query=10%20Things%20I%20Hate%20About%20You",
            "search_query": "10 Things I Hate About You",
        },
        {
            "id": 104,
            "title": "이지 에이",
            "thumbnail": "https://picsum.photos/seed/fam104/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Easy%20A",
            "search_query": "Easy A",
        },
    ],
    "사이버펑크": [
        {
            "id": 201,
            "title": "블레이드 러너 2049",
            "thumbnail": "https://picsum.photos/seed/fam201/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Blade%20Runner%202049",
            "search_query": "Blade Runner 2049",
        },
        {
            "id": 202,
            "title": "매트릭스",
            "thumbnail": "https://picsum.photos/seed/fam202/400/600",
            "external_url": "https://www.themoviedb.org/search?query=The%20Matrix",
            "search_query": "The Matrix",
        },
        {
            "id": 203,
            "title": "공각기동대",
            "thumbnail": "https://picsum.photos/seed/fam203/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Ghost%20in%20the%20Shell",
            "search_query": "Ghost in the Shell",
        },
        {
            "id": 204,
            "title": "아키라",
            "thumbnail": "https://picsum.photos/seed/fam204/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Akira",
            "search_query": "Akira",
        },
    ],
    "무성영화": [
        {
            "id": 301,
            "title": "아티스트",
            "thumbnail": "https://picsum.photos/seed/fam301/400/600",
            "external_url": "https://www.themoviedb.org/search?query=The%20Artist",
            "search_query": "The Artist",
        },
        {
            "id": 302,
            "title": "메트로폴리스",
            "thumbnail": "https://picsum.photos/seed/fam302/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Metropolis",
            "search_query": "Metropolis",
        },
        {
            "id": 303,
            "title": "시티 라이트",
            "thumbnail": "https://picsum.photos/seed/fam303/400/600",
            "external_url": "https://www.themoviedb.org/search?query=City%20Lights",
            "search_query": "City Lights",
        },
        {
            "id": 304,
            "title": "황금광 시대",
            "thumbnail": "https://picsum.photos/seed/fam304/400/600",
            "external_url": "https://www.themoviedb.org/search?query=The%20Gold%20Rush",
            "search_query": "The Gold Rush",
        },
    ],
    "동화": [
        {
            "id": 401,
            "title": "신데렐라",
            "thumbnail": "https://picsum.photos/seed/fam401/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Cinderella",
            "search_query": "Cinderella",
        },
        {
            "id": 402,
            "title": "미녀와 야수",
            "thumbnail": "https://picsum.photos/seed/fam402/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Beauty%20and%20the%20Beast",
            "search_query": "Beauty and the Beast",
        },
        {
            "id": 403,
            "title": "라푼젤",
            "thumbnail": "https://picsum.photos/seed/fam403/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Tangled",
            "search_query": "Tangled",
        },
        {
            "id": 404,
            "title": "마법에 걸린 사랑",
            "thumbnail": "https://picsum.photos/seed/fam404/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Enchanted",
            "search_query": "Enchanted",
        },
    ],
    "재패니즈 노스탤지아": [
        {
            "id": 501,
            "title": "이 세상의 한 구석에",
            "thumbnail": "https://picsum.photos/seed/fam501/400/600",
            "external_url": "https://www.themoviedb.org/search?query=In%20This%20Corner%20of%20the%20World",
            "search_query": "In This Corner of the World",
        },
        {
            "id": 502,
            "title": "추억은 방울방울",
            "thumbnail": "https://picsum.photos/seed/fam502/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Only%20Yesterday",
            "search_query": "Only Yesterday",
        },
        {
            "id": 503,
            "title": "귀를 기울이면",
            "thumbnail": "https://picsum.photos/seed/fam503/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Whisper%20of%20the%20Heart",
            "search_query": "Whisper of the Heart",
        },
        {
            "id": 504,
            "title": "초속 5센티미터",
            "thumbnail": "https://picsum.photos/seed/fam504/400/600",
            "external_url": "https://www.themoviedb.org/search?query=5%20Centimeters%20per%20Second",
            "search_query": "5 Centimeters per Second",
        },
    ],
    "지브리": [
        {
            "id": 601,
            "title": "센과 치히로의 행방불명",
            "thumbnail": "https://picsum.photos/seed/fam601/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Spirited%20Away",
            "search_query": "Spirited Away",
        },
        {
            "id": 602,
            "title": "하울의 움직이는 성",
            "thumbnail": "https://picsum.photos/seed/fam602/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Howl%27s%20Moving%20Castle",
            "search_query": "Howl's Moving Castle",
        },
        {
            "id": 603,
            "title": "모노노케 히메",
            "thumbnail": "https://picsum.photos/seed/fam603/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Princess%20Mononoke",
            "search_query": "Princess Mononoke",
        },
        {
            "id": 604,
            "title": "마녀 배달부 키키",
            "thumbnail": "https://picsum.photos/seed/fam604/400/600",
            "external_url": "https://www.themoviedb.org/search?query=Kiki%27s%20Delivery%20Service",
            "search_query": "Kiki's Delivery Service",
        },
    ],
}
