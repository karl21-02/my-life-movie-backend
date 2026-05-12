from typing import Any

from app.models.movie import Movie


def build_video_generation_input(movie: Movie) -> dict[str, Any]:
    story_brief = movie.story_brief or {}
    scene_plan = movie.scene_plan or []
    files = movie.files or []

    return {
        "story": {
            "title": story_brief.get("title") or "나의 인생 영화",
            "logline": story_brief.get("logline") or "",
            "summary": movie.current_draft or "",
            "protagonist": story_brief.get("protagonist"),
            "time_period": story_brief.get("time_period"),
            "locations": story_brief.get("locations") or [],
            "emotions": story_brief.get("emotions") or [],
            "ending_tone": story_brief.get("ending_tone"),
        },
        "style": {
            "theme_id": movie.theme_id,
            "visual_style": story_brief.get("visual_style") or "cinematic, warm, emotional",
            "mood": story_brief.get("emotions") or [],
        },
        "audio_direction": {
            "music_id": movie.music_id,
        },
        "assets": {
            "images": [file for file in files if file.get("type") == "image"],
            "videos": [file for file in files if file.get("type") == "video"],
            "documents": [file for file in files if file.get("type") == "document"],
        },
        "scenes": scene_plan,
        "provider_prompt": movie.generation_prompt or "",
    }
