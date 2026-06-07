import json
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from openai import APITimeoutError, AsyncOpenAI

logger = get_logger(__name__)

_AI_QUESTIONS = [
    "어떤 시절의 이야기를 가장 담고 싶으신가요?",
    "그 시절 가장 기억에 남는 장소나 공간이 있다면 알려주세요.",
    "영화에서 가장 중요하게 표현하고 싶은 감정은 무엇인가요?",
    "이 영화를 보고 나서 어떤 기분이 들었으면 하나요?",
]

_CHAT_SYSTEM_PROMPT = (
    "당신은 사용자의 인생 영화를 함께 기획하는 대화 파트너입니다. "
    "이번 단계에서는 무거운 전체 시나리오나 장면 계획을 만들지 말고, "
    "다음 대화를 이끌 질문 하나와 현재까지의 짧은 초안만 JSON으로 응답하세요. "
    "민감한 개인정보는 일반화하세요.\n"
    "{"
    '"ai_question": "다음 대화를 이끌 핵심 질문 하나", '
    '"current_draft": "현재까지 정리된 영화 시나리오 초안 1~3문장"'
    "}"
)

_STORY_SYSTEM_PROMPT = (
    "당신은 사용자의 인생 영화를 기획하는 시나리오 디렉터입니다. "
    "사용자의 대화 내용을 바탕으로 아래 JSON 형식으로만 응답하세요. "
    "민감한 개인정보는 요약하거나 일반화하고, 영상 생성에 필요한 감정/장면/스타일 중심으로 정리하세요.\n"
    "{"
    '"ai_question": "다음 대화를 이끌 핵심 질문 하나", '
    '"current_draft": "현재까지 정리된 영화 시나리오 초안 2~4문장", '
    '"story_brief": {'
    '"title": "영화 제목", '
    '"logline": "한 문장 로그라인", '
    '"protagonist": "주인공 설명", '
    '"time_period": "주요 시기", '
    '"locations": ["장소"], '
    '"emotions": ["감정"], '
    '"visual_style": "시각 스타일", '
    '"ending_tone": "결말 톤"'
    "}, "
    '"scene_plan": ['
    '{"order": 1, "summary": "장면 요약", "visual_prompt": "영상 생성용 장면 묘사", '
    '"narration": "내레이션", "emotion": "장면 감정"}'
    "]"
    "}"
)


@dataclass(frozen=True)
class ChatTurnResult:
    ai_question: str
    current_draft: str


@dataclass(frozen=True)
class FinalizedStory:
    story_brief: dict[str, Any]
    scene_plan: list[dict[str, Any]]
    generation_prompt: str


@dataclass(frozen=True)
class StoryGenerationResult:
    ai_question: str
    current_draft: str
    story_brief: dict[str, Any]
    scene_plan: list[dict[str, Any]]
    generation_prompt: str


async def generate_chat_turn(
    *,
    api_key: str | None,
    history: list[dict[str, str]],
    latest_message: str,
    current_draft: str | None,
    settings: Settings | None = None,
    movie_id: int | None = None,
) -> ChatTurnResult:
    if not api_key:
        return build_mock_chat_turn(history, current_draft, latest_message)

    settings = settings or get_settings()
    for attempt in range(2):
        try:
            return await _call_chat_gpt(
                api_key,
                history,
                settings,
                current_draft,
                latest_message,
            )
        except APITimeoutError as exc:
            if attempt == 0:
                continue
            log_openai_fallback("openai_chat_fallback", exc, history, movie_id)
        except Exception as exc:
            log_openai_fallback("openai_chat_fallback", exc, history, movie_id)
        break

    return build_mock_chat_turn(history, current_draft, latest_message)


async def finalize_story(
    *,
    api_key: str | None,
    history: list[dict[str, str]],
    current_draft: str | None,
    settings: Settings | None = None,
    movie_id: int | None = None,
) -> FinalizedStory:
    latest_message = latest_user_message(history, current_draft)
    if not api_key:
        return finalized_story_from_result(
            build_mock_story_result(history, current_draft, latest_message)
        )

    settings = settings or get_settings()
    for attempt in range(2):
        try:
            return finalized_story_from_result(
                await _call_finalize_gpt(api_key, history, settings)
            )
        except APITimeoutError as exc:
            if attempt == 0:
                continue
            log_openai_fallback("openai_finalize_fallback", exc, history, movie_id)
        except Exception as exc:
            log_openai_fallback("openai_finalize_fallback", exc, history, movie_id)
        break

    return finalized_story_from_result(
        build_mock_story_result(history, current_draft, latest_message)
    )


async def generate_story_inputs(
    *,
    api_key: str | None,
    history: list[dict[str, str]],
    current_draft: str | None,
    latest_message: str,
) -> StoryGenerationResult:
    settings = get_settings()
    if not api_key:
        return build_mock_story_result(history, current_draft, latest_message)

    try:
        return await _call_finalize_gpt(api_key, history, settings)
    except APITimeoutError:
        return build_mock_story_result(history, current_draft, latest_message)
    except Exception:
        return build_mock_story_result(history, current_draft, latest_message)


async def _call_chat_gpt(
    api_key: str,
    history: list[dict[str, str]],
    settings: Settings,
    current_draft: str | None,
    latest_message: str,
) -> ChatTurnResult:
    client = AsyncOpenAI(api_key=api_key, timeout=settings.openai_chat_timeout_seconds)
    response = await client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=build_messages(_CHAT_SYSTEM_PROMPT, history),
        response_format={"type": "json_object"},
        max_tokens=settings.openai_chat_max_tokens,
    )
    content = response.choices[0].message.content or "{}"
    result = parse_chat_turn_result(json.loads(content))
    if result.current_draft.strip():
        return result
    return ChatTurnResult(
        ai_question=result.ai_question,
        current_draft=merge_draft(current_draft, latest_message),
    )


async def _call_finalize_gpt(
    api_key: str,
    history: list[dict[str, str]],
    settings: Settings,
) -> StoryGenerationResult:
    client = AsyncOpenAI(api_key=api_key, timeout=settings.openai_story_finalize_timeout_seconds)
    response = await client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=build_messages(_STORY_SYSTEM_PROMPT, history),
        response_format={"type": "json_object"},
        max_tokens=settings.openai_story_finalize_max_tokens,
    )
    content = response.choices[0].message.content or "{}"
    return parse_story_result(json.loads(content))


def build_messages(system_prompt: str, history: list[dict[str, str]]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for entry in history:
        role = "user" if entry["role"] == "user" else "assistant"
        messages.append({"role": role, "content": entry["message"]})
    return messages


def parse_chat_turn_result(data: dict[str, Any]) -> ChatTurnResult:
    return ChatTurnResult(
        ai_question=str(data.get("ai_question") or _AI_QUESTIONS[0]),
        current_draft=str(data.get("current_draft") or ""),
    )


def parse_story_result(data: dict[str, Any]) -> StoryGenerationResult:
    story_brief = data.get("story_brief")
    scene_plan = data.get("scene_plan")

    if not isinstance(story_brief, dict):
        story_brief = {}
    if not isinstance(scene_plan, list):
        scene_plan = []

    result = StoryGenerationResult(
        ai_question=str(data.get("ai_question") or _AI_QUESTIONS[0]),
        current_draft=str(data.get("current_draft") or ""),
        story_brief=story_brief,
        scene_plan=[scene for scene in scene_plan if isinstance(scene, dict)],
        generation_prompt=str(data.get("generation_prompt") or ""),
    )
    if result.generation_prompt:
        return result

    return StoryGenerationResult(
        ai_question=result.ai_question,
        current_draft=result.current_draft,
        story_brief=result.story_brief,
        scene_plan=result.scene_plan,
        generation_prompt=build_generation_prompt(result.story_brief, result.scene_plan),
    )


def build_mock_chat_turn(
    history: list[dict[str, str]],
    current_draft: str | None,
    latest_message: str,
) -> ChatTurnResult:
    turn = max(len([entry for entry in history if entry["role"] == "user"]) - 1, 0)
    draft = merge_draft(current_draft, latest_message)
    return ChatTurnResult(
        ai_question=_AI_QUESTIONS[min(turn, len(_AI_QUESTIONS) - 1)],
        current_draft=draft,
    )


def build_mock_story_result(
    history: list[dict[str, str]],
    current_draft: str | None,
    latest_message: str,
) -> StoryGenerationResult:
    turn = max(len([entry for entry in history if entry["role"] == "user"]) - 1, 0)
    ai_question = _AI_QUESTIONS[min(turn, len(_AI_QUESTIONS) - 1)]
    draft = current_draft or f"{latest_message}의 이야기를 담은 영화."

    story_brief = {
        "title": "나의 인생 영화",
        "logline": f"{latest_message}의 기억을 중심으로 삶의 중요한 순간을 따라가는 영화",
        "protagonist": "자신의 기억을 돌아보는 사용자",
        "time_period": "사용자가 들려준 시기",
        "locations": [],
        "emotions": ["회상", "따뜻함", "여운"],
        "visual_style": "따뜻한 시네마틱 필름룩",
        "ending_tone": "잔잔한 여운",
    }
    scene_plan = [
        {
            "order": 1,
            "summary": "주인공이 기억의 시작점에 서 있는 장면",
            "visual_prompt": "warm cinematic opening scene, soft natural light, reflective mood",
            "narration": "그 시절의 기억은 아직도 선명하게 남아 있습니다.",
            "emotion": "회상",
        },
        {
            "order": 2,
            "summary": latest_message,
            "visual_prompt": "personal life memory, emotional cinematic scene, gentle camera movement",
            "narration": latest_message,
            "emotion": "따뜻함",
        },
        {
            "order": 3,
            "summary": "기억이 한 편의 영화처럼 정리되는 마무리 장면",
            "visual_prompt": "quiet ending scene, soft glow, nostalgic atmosphere",
            "narration": "그 순간들이 모여 지금의 나를 만들었습니다.",
            "emotion": "여운",
        },
    ]
    return StoryGenerationResult(
        ai_question=ai_question,
        current_draft=draft,
        story_brief=story_brief,
        scene_plan=scene_plan,
        generation_prompt=build_generation_prompt(story_brief, scene_plan),
    )


def finalized_story_from_result(result: StoryGenerationResult) -> FinalizedStory:
    return FinalizedStory(
        story_brief=result.story_brief,
        scene_plan=result.scene_plan,
        generation_prompt=result.generation_prompt,
    )


def latest_user_message(history: list[dict[str, str]], current_draft: str | None) -> str:
    for entry in reversed(history):
        if entry.get("role") == "user" and entry.get("message"):
            return entry["message"]
    return current_draft or "사용자가 들려준 이야기"


def merge_draft(current_draft: str | None, latest_message: str) -> str:
    if current_draft and current_draft.strip():
        return f"{current_draft.strip()}\n{latest_message}".strip()
    return f"{latest_message}의 이야기를 담은 영화."


def log_openai_fallback(
    event: str,
    exc: Exception,
    history: list[dict[str, str]],
    movie_id: int | None,
) -> None:
    logger.warning(
        event,
        extra={
            "event": event,
            "movie_id": movie_id,
            "error_type": type(exc).__name__,
            "turn_count": len(history),
        },
    )


def build_generation_prompt(
    story_brief: dict[str, Any],
    scene_plan: list[dict[str, Any]],
) -> str:
    title = story_brief.get("title") or "나의 인생 영화"
    logline = story_brief.get("logline") or "사용자의 인생 이야기를 담은 짧은 영화"
    visual_style = story_brief.get("visual_style") or "cinematic, warm, emotional"
    scene_text = "\n".join(
        f"{scene.get('order', index + 1)}. {scene.get('visual_prompt') or scene.get('summary') or ''}"
        for index, scene in enumerate(scene_plan)
    )
    return (
        f"제목: {title}\n"
        f"로그라인: {logline}\n"
        f"시각 스타일: {visual_style}\n"
        "장면 구성:\n"
        f"{scene_text}"
    ).strip()
