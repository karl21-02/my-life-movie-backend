import anyio

from app.services.story_generation_service import (
    StoryGenerationResult,
    build_mock_story_result,
    generate_story_inputs,
    parse_story_result,
)


def test_build_mock_story_result_returns_generation_inputs():
    result = build_mock_story_result(
        [{"role": "user", "message": "졸업식이 기억나요"}],
        None,
        "졸업식이 기억나요",
    )

    assert result.current_draft
    assert result.story_brief["title"] == "나의 인생 영화"
    assert len(result.scene_plan) == 3
    assert "장면 구성" in result.generation_prompt


def test_parse_story_result_builds_generation_prompt_when_missing():
    result = parse_story_result(
        {
            "ai_question": "그때 누구와 함께 있었나요?",
            "current_draft": "졸업식의 설렘을 담은 이야기",
            "story_brief": {
                "title": "졸업식",
                "logline": "새로운 시작 앞에 선 하루",
                "visual_style": "밝은 필름룩",
            },
            "scene_plan": [{"order": 1, "visual_prompt": "school graduation day"}],
        }
    )

    assert result.ai_question == "그때 누구와 함께 있었나요?"
    assert result.generation_prompt.startswith("제목: 졸업식")


def test_generate_story_inputs_uses_mock_without_api_key():
    async def run():
        return await generate_story_inputs(
            api_key=None,
            history=[{"role": "user", "message": "첫 자취방 기억"}],
            current_draft=None,
            latest_message="첫 자취방 기억",
        )

    result = anyio.run(run)

    assert isinstance(result, StoryGenerationResult)
    assert result.story_brief["logline"]
