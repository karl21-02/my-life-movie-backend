import json
from dataclasses import dataclass
from typing import Any

from openai import APITimeoutError, AsyncOpenAI

_GPT_TIMEOUT_SECONDS = 10.0

_AI_QUESTIONS = [
    "어떤 시절의 이야기를 가장 담고 싶으신가요?",
    "그 시절 가장 기억에 남는 장소나 공간이 있다면 알려주세요.",
    "영화에서 가장 중요하게 표현하고 싶은 감정은 무엇인가요?",
    "이 영화를 보고 나서 어떤 기분이 들었으면 하나요?",
]

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
class StoryGenerationResult:
    ai_question: str
    current_draft: str
    story_brief: dict[str, Any]
    scene_plan: list[dict[str, Any]]
    generation_prompt: str


async def generate_story_inputs(
    *,
    api_key: str | None,
    history: list[dict[str, str]],
    current_draft: str | None,
    latest_message: str,
) -> StoryGenerationResult:
    if not api_key:
        return build_mock_story_result(history, current_draft, latest_message)

    try:
        return await _call_gpt(api_key, history)
    except APITimeoutError:
        return build_timeout_story_result(history, current_draft, latest_message)
    except Exception:
        return build_mock_story_result(history, current_draft, latest_message)


async def _call_gpt(api_key: str, history: list[dict[str, str]]) -> StoryGenerationResult:
    client = AsyncOpenAI(api_key=api_key, timeout=_GPT_TIMEOUT_SECONDS)
    messages: list[dict[str, str]] = [{"role": "system", "content": _STORY_SYSTEM_PROMPT}]
    for entry in history:
        role = "user" if entry["role"] == "user" else "assistant"
        messages.append({"role": role, "content": entry["message"]})

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        response_format={"type": "json_object"},
        max_tokens=900,
    )
    content = response.choices[0].message.content or "{}"
    return parse_story_result(json.loads(content))


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


def build_timeout_story_result(
    history: list[dict[str, str]],
    current_draft: str | None,
    latest_message: str,
) -> StoryGenerationResult:
    result = build_mock_story_result(history, current_draft, latest_message)
    return StoryGenerationResult(
        ai_question="죄송합니다, AI 응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.",
        current_draft=result.current_draft,
        story_brief=result.story_brief,
        scene_plan=result.scene_plan,
        generation_prompt=result.generation_prompt,
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
