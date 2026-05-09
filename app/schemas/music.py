from pydantic import BaseModel


class MusicTrack(BaseModel):
    music_id: int
    title: str
    file_url: str
    is_ai_recommended: bool = False


class MusicListResponse(BaseModel):
    default_tracks: list[MusicTrack]
    ai_recommended: list[MusicTrack]


class MusicRecommendRequest(BaseModel):
    movie_id: int
    message: str


class MusicRecommendResponse(BaseModel):
    ai_message: str
    tracks: list[MusicTrack]
