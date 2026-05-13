from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.movie import Movie, MovieStatus


class MovieRepository(Protocol):
    def create(self, *, user_id: int, theme_id: int) -> Movie:
        ...

    def get_by_id(self, movie_id: int) -> Movie | None:
        ...

    def list_by_user_id(self, user_id: int) -> list[Movie]:
        ...

    def update(self, movie: Movie) -> Movie:
        ...

    def delete(self, movie: Movie) -> None:
        ...


class SQLAlchemyMovieRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, *, user_id: int, theme_id: int) -> Movie:
        movie = Movie(
            user_id=user_id,
            theme_id=theme_id,
            status=MovieStatus.DRAFT,
            files=[],
            chat_history=[],
        )
        self.session.add(movie)
        self.session.commit()
        self.session.refresh(movie)
        return movie

    def get_by_id(self, movie_id: int) -> Movie | None:
        return self.session.get(Movie, movie_id)

    def list_by_user_id(self, user_id: int) -> list[Movie]:
        return list(
            self.session.scalars(
                select(Movie)
                .where(Movie.user_id == user_id)
                .order_by(Movie.created_at.desc(), Movie.id.desc())
            )
        )

    def update(self, movie: Movie) -> Movie:
        self.session.commit()
        self.session.refresh(movie)
        return movie

    def delete(self, movie: Movie) -> None:
        self.session.delete(movie)
        self.session.commit()
