from pydantic import BaseModel


class OstTrack(BaseModel):
    title: str
    artist: str
    spotify_url: str | None = None


class SimilarMovie(BaseModel):
    id: int
    title: str
    thumbnail: str
    external_url: str | None = None
    provider: str = "fallback"


class Movie(BaseModel):
    id: int
    title: str
    description: str
    thumbnail: str
    genre: str
    sentiment: str
    status: str
    output_url: str | None = None
    thumbnail_url: str | None = None
    ost: list[OstTrack]
    similar_movies: list[SimilarMovie]


class MovieSummary(BaseModel):
    id: int
    title: str
    thumbnail: str
    genre: str
    status: str
    output_url: str | None = None
    thumbnail_url: str | None = None


class DeleteMovieResponse(BaseModel):
    message: str


class DownloadMovieResponse(BaseModel):
    message: str
    movie_id: int
    title: str
    output_url: str | None = None
    download_url: str | None = None


class ShareMovieResponse(BaseModel):
    message: str
    movie_id: int
    title: str
    share_url: str


class SimilarMoviesResponse(BaseModel):
    movie_id: int
    similar_movies: list[SimilarMovie]
