import anyio
import httpx
from openai import APITimeoutError

from app.core.config import Settings
from app.services.story_generation_service import (
    ChatTurnResult,
    FinalizedStory,
    StoryGenerationResult,
    build_mock_story_result,
    finalize_story,
    generate_chat_turn,
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


def test_generate_chat_turn_uses_mock_without_api_key():
    async def run():
        return await generate_chat_turn(
            api_key=None,
            history=[{"role": "user", "message": "첫 자취방 기억"}],
            current_draft=None,
            latest_message="첫 자취방 기억",
            settings=Settings(),
        )

    result = anyio.run(run)

    assert isinstance(result, ChatTurnResult)
    assert result.ai_question
    assert "첫 자취방 기억" in result.current_draft


def test_finalize_story_uses_mock_without_api_key():
    async def run():
        return await finalize_story(
            api_key=None,
            history=[{"role": "user", "message": "졸업식이 기억나요"}],
            current_draft="졸업식의 설렘을 담은 이야기",
            settings=Settings(),
        )

    result = anyio.run(run)

    assert isinstance(result, FinalizedStory)
    assert result.story_brief["title"] == "나의 인생 영화"
    assert "장면 구성" in result.generation_prompt


def test_generate_chat_turn_retries_timeout_once(monkeypatch):
    calls = 0

    async def fake_call_chat_gpt(api_key, history, settings, current_draft, latest_message):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise APITimeoutError(request=httpx.Request("POST", "https://api.openai.com"))
        return ChatTurnResult(ai_question="그때 누구와 함께 있었나요?", current_draft="초안")

    monkeypatch.setattr(
        "app.services.story_generation_service._call_chat_gpt",
        fake_call_chat_gpt,
    )

    async def run():
        return await generate_chat_turn(
            api_key="fake-key",
            history=[{"role": "user", "message": "졸업식"}],
            current_draft=None,
            latest_message="졸업식",
            settings=Settings(),
            movie_id=1,
        )

    result = anyio.run(run)

    assert calls == 2
    assert result.current_draft == "초안"


def test_finalize_story_retries_timeout_once(monkeypatch):
    calls = 0

    async def fake_call_finalize_gpt(api_key, history, settings):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise APITimeoutError(request=httpx.Request("POST", "https://api.openai.com"))
        return StoryGenerationResult(
            ai_question="다음 질문",
            current_draft="초안",
            story_brief={"title": "졸업식"},
            scene_plan=[{"order": 1, "visual_prompt": "graduation"}],
            generation_prompt="제목: 졸업식",
        )

    monkeypatch.setattr(
        "app.services.story_generation_service._call_finalize_gpt",
        fake_call_finalize_gpt,
    )

    async def run():
        return await finalize_story(
            api_key="fake-key",
            history=[{"role": "user", "message": "졸업식"}],
            current_draft="초안",
            settings=Settings(),
            movie_id=1,
        )

    result = anyio.run(run)

    assert calls == 2
    assert result.story_brief["title"] == "졸업식"


def test_generate_chat_turn_logs_fallback(monkeypatch):
    logged: dict | None = None

    async def fake_call_chat_gpt(api_key, history, settings, current_draft, latest_message):
        raise ValueError("boom")

    def fake_warning(message, *, extra):
        nonlocal logged
        logged = {"message": message, "extra": extra}

    monkeypatch.setattr(
        "app.services.story_generation_service._call_chat_gpt",
        fake_call_chat_gpt,
    )
    monkeypatch.setattr(
        "app.services.story_generation_service.logger.warning",
        fake_warning,
    )

    async def run():
        return await generate_chat_turn(
            api_key="fake-key",
            history=[{"role": "user", "message": "졸업식"}],
            current_draft=None,
            latest_message="졸업식",
            settings=Settings(),
            movie_id=7,
        )

    result = anyio.run(run)

    assert result.ai_question
    assert logged is not None
    assert logged["message"] == "openai_chat_fallback"
    assert logged["extra"]["event"] == "openai_chat_fallback"
    assert logged["extra"]["movie_id"] == 7
    assert logged["extra"]["error_type"] == "ValueError"
    assert logged["extra"]["turn_count"] == 1
