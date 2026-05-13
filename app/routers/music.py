import base64
from dataclasses import dataclass
from hashlib import sha1

import httpx
from fastapi import APIRouter

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.music import MusicListResponse, MusicRecommendRequest, MusicRecommendResponse, MusicTrack
from app.services.storage_service import build_storage_key, build_storage_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/music", tags=["music"])


@dataclass(frozen=True)
class MusicTrackSeed:
    music_id: int
    title: str
    object_name: str
    artist: str = "My Life Movie"


MUSIC_BY_THEME: dict[int, list[MusicTrackSeed]] = {
    1: [
        MusicTrackSeed(music_id=101, title="Summer Crush", object_name="teen/summer_crush.mp3"),
        MusicTrackSeed(music_id=102, title="First Love Story", object_name="teen/first_love.mp3"),
        MusicTrackSeed(music_id=103, title="School Days", object_name="teen/school_days.mp3"),
    ],
    2: [
        MusicTrackSeed(music_id=201, title="Neon City", object_name="city/neon_city.mp3"),
        MusicTrackSeed(music_id=202, title="Digital Rain", object_name="city/digital_rain.mp3"),
        MusicTrackSeed(music_id=203, title="Synthwave Night", object_name="city/synthwave_night.mp3"),
    ],
    3: [
        MusicTrackSeed(music_id=301, title="Silent Waltz", object_name="classic/silent_waltz.mp3"),
        MusicTrackSeed(music_id=302, title="Old Cinema", object_name="classic/old_cinema.mp3"),
    ],
    4: [
        MusicTrackSeed(music_id=401, title="Fairy Garden", object_name="fantasy/fairy_garden.mp3"),
        MusicTrackSeed(music_id=402, title="Magic Spell", object_name="fantasy/magic_spell.mp3"),
        MusicTrackSeed(music_id=403, title="Enchanted Forest", object_name="fantasy/enchanted_forest.mp3"),
    ],
    5: [
        MusicTrackSeed(music_id=501, title="Sakura Memory", object_name="anime/sakura_memory.mp3"),
        MusicTrackSeed(music_id=502, title="Evening Festival", object_name="anime/evening_festival.mp3"),
        MusicTrackSeed(music_id=503, title="Summer Cicadas", object_name="anime/summer_cicadas.mp3"),
    ],
    6: [
        MusicTrackSeed(music_id=601, title="Spirited Journey", object_name="ghibli/spirited_journey.mp3"),
        MusicTrackSeed(music_id=602, title="My Neighbor's Theme", object_name="ghibli/neighbor_theme.mp3"),
        MusicTrackSeed(music_id=603, title="Castle in the Sky", object_name="ghibli/castle_sky.mp3"),
    ],
}


@router.get("", response_model=MusicListResponse)
async def get_music_by_theme(theme_id: int):
    """테마 ID에 맞는 기본 음악 목록을 반환합니다. (?theme_id=1)"""
    tracks = [build_theme_track(seed) for seed in MUSIC_BY_THEME.get(theme_id, [])]
    return MusicListResponse(default_tracks=tracks, ai_recommended=[])


def build_theme_track(seed: MusicTrackSeed) -> MusicTrack:
    settings = get_settings()
    storage = build_storage_service(settings)
    prefix = settings.s3_music_prefix if settings.storage_provider == "s3" else "music"
    return MusicTrack(
        music_id=seed.music_id,
        title=seed.title,
        file_url=storage.public_url(build_storage_key(prefix, seed.object_name)),
        artist=seed.artist,
        provider=settings.storage_provider,
    )


async def _get_spotify_token(client_id: str, client_secret: str) -> str:
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://accounts.spotify.com/api/token",
            headers={"Authorization": f"Basic {credentials}"},
            data={"grant_type": "client_credentials"},
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


async def _search_spotify_tracks(token: str, query: str) -> list[MusicTrack]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.spotify.com/v1/search",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": query, "type": "track", "limit": 5},
        )
        resp.raise_for_status()
        items = resp.json()["tracks"]["items"]
    return [
        MusicTrack(
            music_id=2000 + i,
            title=f"{item['name']} - {item['artists'][0]['name']}",
            file_url=item.get("preview_url") or "",
            is_ai_recommended=True,
            artist=item["artists"][0]["name"],
            provider="spotify",
            provider_track_id=item["id"],
            external_url=item.get("external_urls", {}).get("spotify"),
        )
        for i, item in enumerate(items)
    ]


MOCK_RECOMMENDATION_CATALOG: dict[str, list[str]] = {
    "calm": ["Quiet Memory", "Warm Letter", "Soft Morning"],
    "bright": ["Golden Days", "Summer Smile", "Light Steps"],
    "sad": ["Rainy Goodbye", "Blue Diary", "Last Scene"],
    "romantic": ["First Heartbeat", "Love Montage", "Moonlit Promise"],
    "dramatic": ["Turning Point", "Final Chapter", "Rising Frame"],
}


def _recommendation_mood(*values: str | None) -> str:
    normalized = " ".join(value or "" for value in values).lower()
    if any(keyword in normalized for keyword in ("잔잔", "차분", "따뜻", "평온", "calm", "soft", "warm")):
        return "calm"
    if any(keyword in normalized for keyword in ("밝", "신나", "희망", "여름", "bright", "happy", "summer")):
        return "bright"
    if any(keyword in normalized for keyword in ("슬픈", "이별", "눈물", "그리움", "sad", "rain", "blue")):
        return "sad"
    if any(keyword in normalized for keyword in ("사랑", "로맨스", "설렘", "첫사랑", "love", "romantic")):
        return "romantic"
    if any(keyword in normalized for keyword in ("웅장", "극적", "긴장", "반전", "dramatic", "epic")):
        return "dramatic"
    return "calm"


def _stable_music_id(seed: str, index: int) -> int:
    digest = sha1(f"{seed}:{index}".encode("utf-8")).hexdigest()
    return 9000 + int(digest[:6], 16) % 900000


def _recommendation_seed(request: MusicRecommendRequest) -> str:
    return " ".join(
        value.strip()
        for value in (
            request.message,
            request.mood or "",
            request.scene or "",
            request.story_hint or "",
            request.avoid or "",
        )
        if value and value.strip()
    )


def _spotify_query(request: MusicRecommendRequest) -> str:
    parts = [
        request.mood,
        request.scene,
        request.message,
        request.story_hint,
        "soundtrack instrumental",
    ]
    if request.avoid:
        parts.append(f"not {request.avoid}")
    return " ".join(part.strip() for part in parts if part and part.strip())


def _mock_recommend(request: MusicRecommendRequest) -> MusicRecommendResponse:
    seed = _recommendation_seed(request)
    mood = _recommendation_mood(request.message, request.mood, request.scene, request.story_hint)
    titles = MOCK_RECOMMENDATION_CATALOG[mood]
    return MusicRecommendResponse(
        ai_message="입력해주신 감정, 장면, 이야기 맥락을 반영해 추천곡을 골랐어요.",
        tracks=[
            MusicTrack(
                music_id=_stable_music_id(seed, index),
                title=f"AI 추천: {title}",
                file_url="",
                is_ai_recommended=True,
                artist="My Life Movie AI",
                provider="local",
            )
            for index, title in enumerate(titles)
        ],
    )


@router.post("/recommend", response_model=MusicRecommendResponse)
async def recommend_music(request: MusicRecommendRequest):
    settings = get_settings()
    if not settings.spotify_client_id or not settings.spotify_client_secret:
        return _mock_recommend(request)
    try:
        token = await _get_spotify_token(settings.spotify_client_id, settings.spotify_client_secret)
        query = _spotify_query(request)
        tracks = await _search_spotify_tracks(token, query)

        if not tracks:
            logger.info("spotify_empty_results", extra={"query": query})
            tracks = await _search_spotify_tracks(token, f"{request.message} music")

        if not tracks:
            logger.warning("spotify_no_results_after_retry", extra={"query": query})
            return _mock_recommend(request)

        return MusicRecommendResponse(
            ai_message="입력해주신 감정, 장면, 이야기 맥락에 맞는 실제 음악을 찾았어요.",
            tracks=tracks,
        )
    except Exception as e:
        logger.warning("spotify_recommend_failed", extra={"error": str(e)})
        return MusicRecommendResponse(
            ai_message="음악을 불러오는 중 오류가 발생했어요. 잠시 후 다시 시도해주세요.",
            tracks=_mock_recommend(request).tracks,
        )
