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

router = APIRouter(prefix="/api/v1/music", tags=["음악"])


@dataclass(frozen=True)
class MusicTrackSeed:
    music_id: int
    title: str
    object_name: str
    artist: str = "My Life Movie"
    search_query: str | None = None


MUSIC_BY_THEME: dict[int, list[MusicTrackSeed]] = {
    1: [
        MusicTrackSeed(music_id=101, title="Summer Crush", object_name="teen/summer_crush.mp3", search_query="teen summer crush pop"),
        MusicTrackSeed(music_id=102, title="First Love Story", object_name="teen/first_love.mp3", search_query="first love teen pop soundtrack"),
        MusicTrackSeed(music_id=103, title="School Days", object_name="teen/school_days.mp3", search_query="school days coming of age soundtrack"),
    ],
    2: [
        MusicTrackSeed(music_id=201, title="Neon City", object_name="city/neon_city.mp3", search_query="neon city synthwave"),
        MusicTrackSeed(music_id=202, title="Digital Rain", object_name="city/digital_rain.mp3", search_query="digital rain synthwave"),
        MusicTrackSeed(music_id=203, title="Synthwave Night", object_name="city/synthwave_night.mp3", search_query="cyberpunk synthwave"),
    ],
    3: [
        MusicTrackSeed(music_id=301, title="Silent Waltz", object_name="classic/silent_waltz.mp3", search_query="silent film waltz instrumental"),
        MusicTrackSeed(music_id=302, title="Old Cinema", object_name="classic/old_cinema.mp3", search_query="old cinema piano instrumental"),
    ],
    4: [
        MusicTrackSeed(music_id=401, title="Fairy Garden", object_name="fantasy/fairy_garden.mp3", search_query="fairy garden fantasy soundtrack"),
        MusicTrackSeed(music_id=402, title="Magic Spell", object_name="fantasy/magic_spell.mp3", search_query="magic spell fantasy music"),
        MusicTrackSeed(music_id=403, title="Enchanted Forest", object_name="fantasy/enchanted_forest.mp3", search_query="enchanted forest fantasy soundtrack"),
    ],
    5: [
        MusicTrackSeed(music_id=501, title="Sakura Memory", object_name="anime/sakura_memory.mp3", search_query="sakura memory japanese nostalgia"),
        MusicTrackSeed(music_id=502, title="Evening Festival", object_name="anime/evening_festival.mp3", search_query="evening festival japanese soundtrack"),
        MusicTrackSeed(music_id=503, title="Summer Cicadas", object_name="anime/summer_cicadas.mp3", search_query="summer cicadas japanese anime music"),
    ],
    6: [
        MusicTrackSeed(music_id=601, title="Spirited Journey", object_name="ghibli/spirited_journey.mp3", search_query="spirited journey orchestral fantasy"),
        MusicTrackSeed(music_id=602, title="My Neighbor's Theme", object_name="ghibli/neighbor_theme.mp3", search_query="neighbor theme warm animation soundtrack"),
        MusicTrackSeed(music_id=603, title="Castle in the Sky", object_name="ghibli/castle_sky.mp3", search_query="castle in the sky orchestral"),
    ],
}


@router.get(
    "",
    response_model=MusicListResponse,
    summary="테마 음악 목록 조회",
    description="테마 ID에 맞는 기본 음악 목록과 재생 가능한 미리듣기 URL을 반환합니다.",
)
async def get_music_by_theme(theme_id: int):
    """테마 ID에 맞는 기본 음악 목록을 반환합니다. (?theme_id=1)"""
    seeds = MUSIC_BY_THEME.get(theme_id, [])
    tracks = await build_playable_theme_tracks(seeds)
    if not tracks:
        tracks = [build_theme_track(seed) for seed in seeds]
    return MusicListResponse(default_tracks=tracks, ai_recommended=[])


async def build_playable_theme_tracks(seeds: list[MusicTrackSeed]) -> list[MusicTrack]:
    tracks: list[MusicTrack] = []
    seen_ids: set[str] = set()
    for seed in seeds:
        query = seed.search_query or seed.title
        for track in await _search_deezer_tracks(query, limit=1, is_ai_recommended=False):
            provider_track_id = track.provider_track_id or str(track.music_id)
            if provider_track_id in seen_ids:
                continue
            seen_ids.add(provider_track_id)
            tracks.append(track)
            break
    return tracks


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


async def _search_deezer_tracks(
    query: str,
    *,
    limit: int = 5,
    is_ai_recommended: bool = True,
) -> list[MusicTrack]:
    if not query.strip():
        return []

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://api.deezer.com/search",
            params={"q": query, "limit": limit},
        )
        resp.raise_for_status()
        items = resp.json().get("data")

    if not isinstance(items, list):
        return []

    tracks: list[MusicTrack] = []
    for item in items:
        if not isinstance(item, dict) or not item.get("preview"):
            continue
        artist = item.get("artist") if isinstance(item.get("artist"), dict) else {}
        artist_name = artist.get("name") if isinstance(artist, dict) else None
        track_id = str(item.get("id") or "")
        tracks.append(
            MusicTrack(
                music_id=int(item.get("id") or _stable_music_id(query, len(tracks))),
                title=str(item.get("title") or "Unknown Track"),
                file_url=str(item.get("preview")),
                is_ai_recommended=is_ai_recommended,
                artist=artist_name,
                provider="deezer",
                provider_track_id=track_id,
                external_url=item.get("link"),
            )
        )
        if len(tracks) >= limit:
            break
    return tracks


async def _attach_deezer_previews(tracks: list[MusicTrack]) -> list[MusicTrack]:
    enriched_tracks: list[MusicTrack] = []
    for track in tracks:
        if track.file_url:
            enriched_tracks.append(track)
            continue

        query = " ".join(part for part in (track.title, track.artist or "") if part).strip()
        deezer_tracks = await _search_deezer_tracks(query, limit=1, is_ai_recommended=track.is_ai_recommended)
        if deezer_tracks:
            deezer_track = deezer_tracks[0]
            enriched_tracks.append(
                track.model_copy(
                    update={
                        "file_url": deezer_track.file_url,
                        "provider": "spotify+deezer",
                        "external_url": track.external_url or deezer_track.external_url,
                    }
                )
            )
        else:
            enriched_tracks.append(track)
    return enriched_tracks


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


@router.post(
    "/recommend",
    response_model=MusicRecommendResponse,
    summary="AI 음악 추천",
    description=(
        "사용자가 입력한 분위기, 감정, 장면 설명을 기반으로 Spotify/Deezer에서 "
        "미리듣기 가능한 음악 후보를 추천합니다."
    ),
)
async def recommend_music(request: MusicRecommendRequest):
    settings = get_settings()
    query = _spotify_query(request)
    if not settings.spotify_client_id or not settings.spotify_client_secret:
        deezer_tracks = await _search_deezer_tracks(query)
        if deezer_tracks:
            return MusicRecommendResponse(
                ai_message="입력해주신 감정, 장면, 이야기 맥락에 맞는 실제 미리듣기 음악을 찾았어요.",
                tracks=deezer_tracks,
            )
        return _mock_recommend(request)
    try:
        token = await _get_spotify_token(settings.spotify_client_id, settings.spotify_client_secret)
        tracks = await _search_spotify_tracks(token, query)
        tracks = await _attach_deezer_previews(tracks)

        if not tracks:
            logger.info("spotify_empty_results", extra={"query": query})
            tracks = await _search_spotify_tracks(token, f"{request.message} music")
            tracks = await _attach_deezer_previews(tracks)

        if not tracks:
            logger.warning("spotify_no_results_after_retry_try_deezer", extra={"query": query})
            tracks = await _search_deezer_tracks(query)

        if not tracks:
            return _mock_recommend(request)

        return MusicRecommendResponse(
            ai_message="입력해주신 감정, 장면, 이야기 맥락에 맞는 실제 미리듣기 음악을 찾았어요.",
            tracks=tracks,
        )
    except Exception as e:
        logger.warning("spotify_recommend_failed", extra={"error": str(e)})
        deezer_tracks = await _search_deezer_tracks(query)
        if deezer_tracks:
            return MusicRecommendResponse(
                ai_message="입력해주신 감정, 장면, 이야기 맥락에 맞는 실제 미리듣기 음악을 찾았어요.",
                tracks=deezer_tracks,
            )
        return MusicRecommendResponse(
            ai_message="음악을 불러오는 중 오류가 발생했어요. 잠시 후 다시 시도해주세요.",
            tracks=_mock_recommend(request).tracks,
        )
