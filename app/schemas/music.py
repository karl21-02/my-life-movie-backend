from pydantic import BaseModel


class MusicTrack(BaseModel):
    music_id: int
    title: str
    file_url: str
    is_ai_recommended: bool = False
    artist: str | None = None
    provider: str = "local"
    provider_track_id: str | None = None
    external_url: str | None = None


class MusicListResponse(BaseModel):
    default_tracks: list[MusicTrack]
    ai_recommended: list[MusicTrack]


class MusicRecommendRequest(BaseModel):
    movie_id: int
    message: str
    mood: str | None = None
    scene: str | None = None
    story_hint: str | None = None
    avoid: str | None = None


class MusicRecommendResponse(BaseModel):
    ai_message: str
    tracks: list[MusicTrack]
