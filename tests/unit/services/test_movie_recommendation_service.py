import httpx
import pytest

from app.core.config import Settings
from app.models.movie_recommendation import MovieRecommendation
from app.services.movie_recommendation_service import (
    MovieRecommendationService,
    TMDBMovieMetadataProvider,
    build_movie_recommendation_service,
)


pytestmark = pytest.mark.unit


def test_movie_recommendation_service_uses_fallback_without_provider():
    service = MovieRecommendationService()

    movies = service.recommend_by_genre("하이틴")

    assert len(movies) == 4
    assert movies[0].title == "브렉퍼스트 클럽"
    assert movies[0].provider == "fallback"
    assert movies[0].external_url is not None


def test_tmdb_movie_metadata_provider_maps_search_result():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-token"
        assert request.url.path == "/3/search/movie"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": 2108,
                        "title": "The Breakfast Club",
                        "poster_path": "/poster.jpg",
                    }
                ]
            },
        )

    provider = TMDBMovieMetadataProvider(
        access_token="test-token",
        api_base_url="https://api.themoviedb.org/3",
        image_base_url="https://image.tmdb.org/t/p",
        poster_size="w500",
        language="ko-KR",
        timeout_seconds=1,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    movie = provider.search_movie("브렉퍼스트 클럽")

    assert movie is not None
    assert movie.id == 2108
    assert movie.title == "The Breakfast Club"
    assert movie.thumbnail == "https://image.tmdb.org/t/p/w500/poster.jpg"
    assert movie.external_url == "https://www.themoviedb.org/movie/2108"
    assert movie.provider == "tmdb"


def test_movie_recommendation_service_searches_tmdb_with_original_title():
    class FakeProvider:
        def search_movie(self, title: str):
            assert title == "The Breakfast Club"
            return None

    service = MovieRecommendationService(metadata_provider=FakeProvider())

    movies = service.recommend_by_genre("하이틴", limit=1)

    assert movies[0].title == "브렉퍼스트 클럽"
    assert movies[0].provider == "fallback"


def test_build_movie_recommendation_service_uses_tmdb_when_token_exists():
    service = build_movie_recommendation_service(Settings(tmdb_access_token="test-token"))

    assert service.metadata_provider is not None


def test_movie_recommendation_service_returns_stored_recommendations_first():
    class FakeRepository:
        def list_by_movie_id(self, movie_id: int):
            return [
                MovieRecommendation(
                    id=10,
                    movie_id=movie_id,
                    provider="tmdb",
                    provider_movie_id="2108",
                    title="저장된 추천",
                    poster_url="https://image.tmdb.org/t/p/w500/poster.jpg",
                    external_url="https://www.themoviedb.org/movie/2108",
                    rank=1,
                )
            ]

        def replace_for_movie(self, *, movie_id: int, recommendations):
            raise AssertionError("저장된 추천이 있으면 새로 생성하지 않아야 합니다.")

    service = MovieRecommendationService(recommendation_repository=FakeRepository())

    recommendations = service.get_or_create_for_movie(movie_id=1, genre="하이틴")

    assert recommendations[0].title == "저장된 추천"
    assert recommendations[0].provider == "tmdb"
