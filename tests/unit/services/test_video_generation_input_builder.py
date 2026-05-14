import pytest

from app.models.movie import Movie
from app.services.video_generation_input_builder import build_video_generation_input


pytestmark = pytest.mark.unit


def test_build_video_generation_input_normalizes_movie_fields():
    movie = Movie(
        id=1,
        user_id=1,
        theme_id=2,
        music_id=201,
        current_draft="첫 독립의 설렘과 두려움을 담은 이야기",
        story_brief={
            "title": "첫 독립",
            "logline": "작은 방에서 시작된 성장 이야기",
            "protagonist": "처음 독립한 사용자",
            "time_period": "20대 초반",
            "locations": ["원룸"],
            "emotions": ["설렘", "두려움"],
            "visual_style": "따뜻한 필름룩",
            "ending_tone": "성장",
        },
        scene_plan=[{"order": 1, "summary": "짐을 푸는 장면"}],
        generation_prompt="warm cinematic room",
        files=[
            {"file_id": "img_1", "type": "image", "filename": "room.jpg"},
            {"file_id": "vid_1", "type": "video", "filename": "move.mp4"},
            {"file_id": "doc_1", "type": "document", "filename": "note.txt"},
        ],
    )

    result = build_video_generation_input(movie)

    assert result["story"]["title"] == "첫 독립"
    assert result["style"]["theme_id"] == 2
    assert result["audio_direction"]["music_id"] == 201
    assert result["assets"]["images"][0]["file_id"] == "img_1"
    assert result["assets"]["videos"][0]["file_id"] == "vid_1"
    assert result["assets"]["documents"][0]["file_id"] == "doc_1"
    assert result["provider_prompt"] == "warm cinematic room"
