import pytest

from app.models.movie import Movie, MovieStatus
from app.models.movie_recommendation import MovieRecommendation
from app.repositories.movie_recommendation_repository import SQLAlchemyMovieRecommendationRepository


pytestmark = pytest.mark.unit


def test_movie_recommendation_repository_replaces_movie_recommendations(db_session):
    movie = Movie(
        user_id=1,
        theme_id=1,
        status=MovieStatus.COMPLETED,
        files=[],
        chat_history=[],
    )
    db_session.add(movie)
    db_session.commit()
    db_session.refresh(movie)

    repository = SQLAlchemyMovieRecommendationRepository(db_session)

    repository.replace_for_movie(
        movie_id=movie.id,
        recommendations=[
            MovieRecommendation(
                movie_id=movie.id,
                provider="fallback",
                provider_movie_id="101",
                title="첫 추천",
                poster_url="https://example.com/first.jpg",
                external_url="https://example.com/first",
                rank=1,
            )
        ],
    )
    repository.replace_for_movie(
        movie_id=movie.id,
        recommendations=[
            MovieRecommendation(
                movie_id=movie.id,
                provider="tmdb",
                provider_movie_id="2108",
                title="새 추천",
                poster_url="https://example.com/new.jpg",
                external_url="https://example.com/new",
                rank=1,
            )
        ],
    )

    recommendations = repository.list_by_movie_id(movie.id)

    assert len(recommendations) == 1
    assert recommendations[0].title == "새 추천"
    assert recommendations[0].provider == "tmdb"
