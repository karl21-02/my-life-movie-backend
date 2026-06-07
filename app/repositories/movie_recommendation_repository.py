from typing import Protocol

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.movie_recommendation import MovieRecommendation


class MovieRecommendationRepository(Protocol):
    def list_by_movie_id(self, movie_id: int) -> list[MovieRecommendation]:
        ...

    def replace_for_movie(
        self,
        *,
        movie_id: int,
        recommendations: list[MovieRecommendation],
    ) -> list[MovieRecommendation]:
        ...


class SQLAlchemyMovieRecommendationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_by_movie_id(self, movie_id: int) -> list[MovieRecommendation]:
        return list(
            self.session.scalars(
                select(MovieRecommendation)
                .where(MovieRecommendation.movie_id == movie_id)
                .order_by(MovieRecommendation.rank.asc(), MovieRecommendation.id.asc())
            )
        )

    def replace_for_movie(
        self,
        *,
        movie_id: int,
        recommendations: list[MovieRecommendation],
    ) -> list[MovieRecommendation]:
        self.session.execute(
            delete(MovieRecommendation).where(MovieRecommendation.movie_id == movie_id)
        )
        for recommendation in recommendations:
            recommendation.movie_id = movie_id
            self.session.add(recommendation)
        self.session.commit()
        return self.list_by_movie_id(movie_id)
