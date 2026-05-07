from pydantic import BaseModel


class OstTrack(BaseModel):
    title: str
    artist: str
    spotify_url: str | None = None


class SimilarMovie(BaseModel):
    id: int
    title: str
    thumbnail: str


class Movie(BaseModel):
    id: int
    title: str
    description: str
    thumbnail: str
    genre: str
    sentiment: str
    ost: list[OstTrack]
    similar_movies: list[SimilarMovie]


class MovieSummary(BaseModel):
    id: int
    title: str
    thumbnail: str
    genre: str


class DeleteMovieResponse(BaseModel):
    message: str


class DownloadMovieResponse(BaseModel):
    message: str
    movie_id: int
    title: str


class ShareMovieResponse(BaseModel):
    message: str
    movie_id: int
    title: str
    share_url: str
