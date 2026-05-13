import httpx
import pytest

from app.core.config import Settings
from app.models.movie import Movie, MovieStatus
from app.models.movie_recommendation import MovieRecommendation
from app.services.movie_recommendation_service import (
    HeuristicRecommendationPlanner,
    MovieRecommendationPlan,
    MovieRecommendationService,
    OpenAIRecommendationPlanner,
    TMDBMovieMetadataProvider,
    build_movie_recommendation_service,
    rank_tmdb_candidates,
)


pytestmark = pytest.mark.unit


def sample_movie() -> Movie:
    return Movie(
        id=1,
        user_id=1,
        theme_id=1,
        current_draft="첫 독립의 설렘과 두려움을 담은 성장 영화",
        story_brief={
            "title": "첫 독립",
            "logline": "작은 방에서 시작된 성장 이야기",
            "locations": ["원룸"],
            "emotions": ["설렘", "두려움", "성장"],
            "visual_style": "따뜻한 필름룩",
            "ending_tone": "성장",
        },
        scene_plan=[{"summary": "작은 원룸에서 짐을 푸는 장면"}],
        generation_prompt="coming of age, first apartment, warm nostalgic drama",
        files=[],
        chat_history=[],
        status=MovieStatus.COMPLETED,
    )


def test_movie_recommendation_service_returns_empty_without_tmdb_provider():
    service = MovieRecommendationService()

    movies = service.recommend_for_movie(sample_movie(), "하이틴")

    assert movies == []


def test_tmdb_movie_metadata_provider_returns_search_results():
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
                        "overview": "A warm coming of age story.",
                        "popularity": 30,
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

    movies = provider.search_movies("coming of age")

    assert movies[0]["id"] == 2108
    assert provider.poster_url("/poster.jpg") == "https://image.tmdb.org/t/p/w500/poster.jpg"


def test_rank_tmdb_candidates_scores_by_story_keywords():
    plan = MovieRecommendationPlan(
        queries=["coming of age apartment"],
        keywords=["coming", "apartment", "growth"],
        mood="warm",
        reason_template="성장 서사가 유사합니다.",
    )
    candidates = [
        {"id": 1, "title": "Space War", "overview": "A battle in space.", "poster_path": "/a.jpg", "popularity": 90},
        {
            "id": 2,
            "title": "First Room",
            "overview": "A coming of age story about growth in a small apartment.",
            "poster_path": "/b.jpg",
            "popularity": 20,
        },
    ]

    ranked = rank_tmdb_candidates(candidates, plan)

    assert ranked[0]["id"] == 2
    assert ranked[0]["_similarity_score"] > ranked[1]["_similarity_score"]


def test_movie_recommendation_service_searches_with_movie_context_and_stores_results():
    class FakeProvider:
        def __init__(self) -> None:
            self.queries: list[str] = []

        def search_movies(self, query: str, *, limit: int = 6):
            self.queries.append(query)
            return [
                {
                    "id": 2108,
                    "title": "The Breakfast Club",
                    "overview": "A coming of age story about growth and fear.",
                    "poster_path": "/poster.jpg",
                    "popularity": 30,
                }
            ]

        def poster_url(self, poster_path: str | None) -> str:
            return f"https://image.tmdb.org/t/p/w500/{poster_path.lstrip('/')}" if poster_path else ""

    class FakeRepository:
        def __init__(self) -> None:
            self.stored: list[MovieRecommendation] = []

        def list_by_movie_id(self, movie_id: int):
            return self.stored

        def replace_for_movie(self, *, movie_id: int, recommendations):
            self.stored = recommendations
            return recommendations

    provider = FakeProvider()
    repository = FakeRepository()
    service = MovieRecommendationService(
        metadata_provider=provider,
        planner=HeuristicRecommendationPlanner(),
        recommendation_repository=repository,
    )

    recommendations = service.get_or_create_for_movie(movie=sample_movie(), genre="하이틴")

    assert provider.queries
    assert recommendations[0].provider == "tmdb"
    assert recommendations[0].external_url == "https://www.themoviedb.org/movie/2108"
    assert repository.stored[0].title == "The Breakfast Club"
    assert repository.stored[0].metadata_json["score"] > 0


def test_build_movie_recommendation_service_uses_openai_planner_when_key_exists():
    service = build_movie_recommendation_service(
        Settings(tmdb_access_token="tmdb-token", openai_api_key="openai-key")
    )

    assert service.metadata_provider is not None
    assert isinstance(service.planner, OpenAIRecommendationPlanner)


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
                    metadata_json={"score": 3.5},
                )
            ]

        def replace_for_movie(self, *, movie_id: int, recommendations):
            raise AssertionError("저장된 추천이 있으면 새로 생성하지 않아야 합니다.")

    service = MovieRecommendationService(recommendation_repository=FakeRepository())

    recommendations = service.get_or_create_for_movie(movie=sample_movie(), genre="하이틴")

    assert recommendations[0].title == "저장된 추천"
    assert recommendations[0].provider == "tmdb"
    assert recommendations[0].score == 3.5
