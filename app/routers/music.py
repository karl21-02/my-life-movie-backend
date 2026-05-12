import base64

import httpx
from fastapi import APIRouter

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.music import MusicListResponse, MusicRecommendRequest, MusicRecommendResponse, MusicTrack

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/music", tags=["music"])

# 테마별 기본 음악 목록 <- 뭘로 정하지
MUSIC_BY_THEME: dict[int, list[MusicTrack]] = {
    1: [
        MusicTrack(music_id=101, title="Summer Crush", file_url="/static/music/summer_crush.mp3"),
        MusicTrack(music_id=102, title="First Love Story", file_url="/static/music/first_love.mp3"),
        MusicTrack(music_id=103, title="School Days", file_url="/static/music/school_days.mp3"),
    ],
    2: [
        MusicTrack(music_id=201, title="Neon City", file_url="/static/music/neon_city.mp3"),
        MusicTrack(music_id=202, title="Digital Rain", file_url="/static/music/digital_rain.mp3"),
        MusicTrack(music_id=203, title="Synthwave Night", file_url="/static/music/synthwave_night.mp3"),
    ],
    3: [
        MusicTrack(music_id=301, title="Silent Waltz", file_url="/static/music/silent_waltz.mp3"),
        MusicTrack(music_id=302, title="Old Cinema", file_url="/static/music/old_cinema.mp3"),
    ],
    4: [
        MusicTrack(music_id=401, title="Fairy Garden", file_url="/static/music/fairy_garden.mp3"),
        MusicTrack(music_id=402, title="Magic Spell", file_url="/static/music/magic_spell.mp3"),
        MusicTrack(music_id=403, title="Enchanted Forest", file_url="/static/music/enchanted_forest.mp3"),
    ],
    5: [
        MusicTrack(music_id=501, title="Sakura Memory", file_url="/static/music/sakura_memory.mp3"),
        MusicTrack(music_id=502, title="Evening Festival", file_url="/static/music/evening_festival.mp3"),
        MusicTrack(music_id=503, title="Summer Cicadas", file_url="/static/music/summer_cicadas.mp3"),
    ],
    6: [
        MusicTrack(music_id=601, title="Spirited Journey", file_url="/static/music/spirited_journey.mp3"),
        MusicTrack(music_id=602, title="My Neighbor's Theme", file_url="/static/music/neighbor_theme.mp3"),
        MusicTrack(music_id=603, title="Castle in the Sky", file_url="/static/music/castle_sky.mp3"),
    ],
}


@router.get("", response_model=MusicListResponse)
async def get_music_by_theme(theme_id: int):
    """테마 ID에 맞는 기본 음악 목록을 반환합니다. (?theme_id=1)"""
    tracks = MUSIC_BY_THEME.get(theme_id, [])
    return MusicListResponse(default_tracks=tracks, ai_recommended=[])


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
        )
        for i, item in enumerate(items)
    ]


def _mock_recommend() -> MusicRecommendResponse:
    return MusicRecommendResponse(
        ai_message="말씀하신 분위기에 어울리는 곡을 찾아봤어요!",
        tracks=[MusicTrack(music_id=999, title="AI 추천: Emotional Journey", file_url="", is_ai_recommended=True)],
    )


@router.post("/recommend", response_model=MusicRecommendResponse)
async def recommend_music(request: MusicRecommendRequest):
    settings = get_settings()
    if not settings.spotify_client_id or not settings.spotify_client_secret:
        return _mock_recommend()
    try:
        token = await _get_spotify_token(settings.spotify_client_id, settings.spotify_client_secret)
        tracks = await _search_spotify_tracks(token, request.message)

        if not tracks:
            logger.info("spotify_empty_results", extra={"query": request.message})
            tracks = await _search_spotify_tracks(token, f"{request.message} music")

        if not tracks:
            logger.warning("spotify_no_results_after_retry", extra={"query": request.message})
            return _mock_recommend()

        return MusicRecommendResponse(
            ai_message=f"'{request.message}' 분위기에 어울리는 곡을 찾았어요!",
            tracks=tracks,
        )
    except Exception as e:
        logger.warning("spotify_recommend_failed", extra={"error": str(e)})
        return MusicRecommendResponse(
            ai_message="음악을 불러오는 중 오류가 발생했어요. 잠시 후 다시 시도해주세요.",
            tracks=[MusicTrack(music_id=998, title="추천 로드 실패", file_url="", is_ai_recommended=True)],
        )
