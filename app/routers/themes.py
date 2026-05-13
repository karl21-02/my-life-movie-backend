from fastapi import APIRouter

from app.core.openapi import COMMON_PROBLEM_RESPONSES
from app.schemas.theme import Theme

router = APIRouter(prefix="/api/v1/themes", tags=["테마"])

THEMES = [
    Theme(theme_id=1, name="하이틴", description="청춘의 설렘과 우정이 가득한 하이틴 무비 스타일", preview_color="#FFD6E0"),
    Theme(theme_id=2, name="사이버펑크", description="미래 도시의 네온빛과 기술이 충돌하는 사이버펑크 세계관", preview_color="#00FFFF"),
    Theme(theme_id=3, name="무성영화", description="흑백의 고전적 아름다움을 담은 무성영화 스타일", preview_color="#D4C5A9"),
    Theme(theme_id=4, name="동화", description="마법과 상상력이 가득한 동화 같은 세계", preview_color="#C8E6C9"),
    Theme(theme_id=5, name="재패니즈 노스탤지아", description="일본 감성의 아련한 노스탤지아", preview_color="#FFE0B2"),
    Theme(theme_id=6, name="지브리", description="지브리 스튜디오 특유의 따뜻하고 몽환적인 세계관", preview_color="#B2DFDB"),
]


@router.get(
    "",
    response_model=list[Theme],
    summary="테마 목록 조회",
    description=(
        "인생 영화 제작 첫 단계에서 사용자가 선택할 수 있는 테마 목록을 반환합니다. "
        "각 테마는 `theme_id`, `name`, `description`, `preview_color`를 포함합니다. "
        "현재 하이틴·사이버펑크·무성영화·동화·재패니즈 노스탤지아·지브리 6종을 제공합니다."
    ),
    responses={
        200: {"description": "테마 목록 반환 성공입니다."},
        **COMMON_PROBLEM_RESPONSES,
    },
)
async def get_themes():
    """영화 테마 목록 6개를 반환합니다. (하이틴, 사이버펑크, 무성영화, 동화, 재패니즈 노스탤지아, 지브리)"""
    return THEMES
