from fastapi import APIRouter
from app.schemas.music import MusicListResponse, MusicTrack, MusicRecommendRequest, MusicRecommendResponse

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


@router.post("/recommend", response_model=MusicRecommendResponse)
async def recommend_music(request: MusicRecommendRequest):
    """사용자 메시지를 받아 AI가 어울리는 음악을 추천합니다. (AI 연동 전 mock 응답)"""
    return MusicRecommendResponse(
        ai_message="말씀하신 분위기에 어울리는 곡을 찾아봤어요! 더 구체적으로 원하는 감정이나 분위기가 있으신가요?",
        tracks=[
            MusicTrack(music_id=999, title="AI 추천: Emotional Journey", file_url="/static/music/ai_rec_1.mp3", is_ai_recommended=True),
        ],
    )
