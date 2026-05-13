from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260513_0004"
down_revision: str | None = "20260509_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "famous_movies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("genre", sa.String(length=64), nullable=False),
        sa.Column("thumbnail", sa.String(length=512), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_famous_movies"),
    )
    op.create_index("ix_famous_movies_genre", "famous_movies", ["genre"])

    op.bulk_insert(
        sa.table(
            "famous_movies",
            sa.column("title", sa.String),
            sa.column("genre", sa.String),
            sa.column("thumbnail", sa.String),
        ),
        [
            # ── 하이틴 ──────────────────────────────────────────
            {"title": "브렉퍼스트 클럽", "genre": "하이틴", "thumbnail": "https://picsum.photos/seed/fam101/400/600"},
            {"title": "퀸카로 살아남는 법", "genre": "하이틴", "thumbnail": "https://picsum.photos/seed/fam102/400/600"},
            {"title": "사랑할 수 없는 10가지 이유", "genre": "하이틴", "thumbnail": "https://picsum.photos/seed/fam103/400/600"},
            {"title": "페리스 뷸러의 해방", "genre": "하이틴", "thumbnail": "https://picsum.photos/seed/fam104/400/600"},
            {"title": "이지 에이", "genre": "하이틴", "thumbnail": "https://picsum.photos/seed/fam105/400/600"},
            {"title": "슈퍼배드", "genre": "하이틴", "thumbnail": "https://picsum.photos/seed/fam106/400/600"},
            {"title": "주노", "genre": "하이틴", "thumbnail": "https://picsum.photos/seed/fam107/400/600"},
            {"title": "레이디 버드", "genre": "하이틴", "thumbnail": "https://picsum.photos/seed/fam108/400/600"},
            {"title": "클루리스", "genre": "하이틴", "thumbnail": "https://picsum.photos/seed/fam109/400/600"},
            {"title": "프리티 인 핑크", "genre": "하이틴", "thumbnail": "https://picsum.photos/seed/fam110/400/600"},
            # ── 사이버펑크 ──────────────────────────────────────
            {"title": "블레이드 러너 2049", "genre": "사이버펑크", "thumbnail": "https://picsum.photos/seed/fam201/400/600"},
            {"title": "매트릭스", "genre": "사이버펑크", "thumbnail": "https://picsum.photos/seed/fam202/400/600"},
            {"title": "공각기동대", "genre": "사이버펑크", "thumbnail": "https://picsum.photos/seed/fam203/400/600"},
            {"title": "아키라", "genre": "사이버펑크", "thumbnail": "https://picsum.photos/seed/fam204/400/600"},
            {"title": "트론: 새로운 시작", "genre": "사이버펑크", "thumbnail": "https://picsum.photos/seed/fam205/400/600"},
            {"title": "알리타: 배틀 엔젤", "genre": "사이버펑크", "thumbnail": "https://picsum.photos/seed/fam206/400/600"},
            {"title": "업그레이드", "genre": "사이버펑크", "thumbnail": "https://picsum.photos/seed/fam207/400/600"},
            {"title": "엑스 마키나", "genre": "사이버펑크", "thumbnail": "https://picsum.photos/seed/fam208/400/600"},
            {"title": "다크 시티", "genre": "사이버펑크", "thumbnail": "https://picsum.photos/seed/fam209/400/600"},
            {"title": "레디 플레이어 원", "genre": "사이버펑크", "thumbnail": "https://picsum.photos/seed/fam210/400/600"},
            # ── 무성영화 ────────────────────────────────────────
            {"title": "아티스트", "genre": "무성영화", "thumbnail": "https://picsum.photos/seed/fam301/400/600"},
            {"title": "메트로폴리스", "genre": "무성영화", "thumbnail": "https://picsum.photos/seed/fam302/400/600"},
            {"title": "시티 라이트", "genre": "무성영화", "thumbnail": "https://picsum.photos/seed/fam303/400/600"},
            {"title": "황금광 시대", "genre": "무성영화", "thumbnail": "https://picsum.photos/seed/fam304/400/600"},
            {"title": "노스페라투", "genre": "무성영화", "thumbnail": "https://picsum.photos/seed/fam305/400/600"},
            {"title": "선라이즈", "genre": "무성영화", "thumbnail": "https://picsum.photos/seed/fam306/400/600"},
            {"title": "더 키드", "genre": "무성영화", "thumbnail": "https://picsum.photos/seed/fam307/400/600"},
            {"title": "잔다르크의 수난", "genre": "무성영화", "thumbnail": "https://picsum.photos/seed/fam308/400/600"},
            {"title": "더 제너럴", "genre": "무성영화", "thumbnail": "https://picsum.photos/seed/fam309/400/600"},
            {"title": "칼리가리 박사의 밀실", "genre": "무성영화", "thumbnail": "https://picsum.photos/seed/fam310/400/600"},
            # ── 동화 ────────────────────────────────────────────
            {"title": "신데렐라", "genre": "동화", "thumbnail": "https://picsum.photos/seed/fam401/400/600"},
            {"title": "미녀와 야수", "genre": "동화", "thumbnail": "https://picsum.photos/seed/fam402/400/600"},
            {"title": "라푼젤", "genre": "동화", "thumbnail": "https://picsum.photos/seed/fam403/400/600"},
            {"title": "마법에 걸린 사랑", "genre": "동화", "thumbnail": "https://picsum.photos/seed/fam404/400/600"},
            {"title": "슈렉", "genre": "동화", "thumbnail": "https://picsum.photos/seed/fam405/400/600"},
            {"title": "말레피센트", "genre": "동화", "thumbnail": "https://picsum.photos/seed/fam406/400/600"},
            {"title": "에버 애프터", "genre": "동화", "thumbnail": "https://picsum.photos/seed/fam407/400/600"},
            {"title": "인투 더 우즈", "genre": "동화", "thumbnail": "https://picsum.photos/seed/fam408/400/600"},
            {"title": "겨울왕국", "genre": "동화", "thumbnail": "https://picsum.photos/seed/fam409/400/600"},
            {"title": "모아나", "genre": "동화", "thumbnail": "https://picsum.photos/seed/fam410/400/600"},
            # ── 재패니즈 노스탤지아 ──────────────────────────────
            {"title": "이 세상의 한 구석에", "genre": "재패니즈 노스탤지아", "thumbnail": "https://picsum.photos/seed/fam501/400/600"},
            {"title": "반딧불이의 묘", "genre": "재패니즈 노스탤지아", "thumbnail": "https://picsum.photos/seed/fam502/400/600"},
            {"title": "추억은 방울방울", "genre": "재패니즈 노스탤지아", "thumbnail": "https://picsum.photos/seed/fam503/400/600"},
            {"title": "마니와 있으면", "genre": "재패니즈 노스탤지아", "thumbnail": "https://picsum.photos/seed/fam504/400/600"},
            {"title": "늑대아이", "genre": "재패니즈 노스탤지아", "thumbnail": "https://picsum.photos/seed/fam505/400/600"},
            {"title": "귀를 기울이면", "genre": "재패니즈 노스탤지아", "thumbnail": "https://picsum.photos/seed/fam506/400/600"},
            {"title": "바다가 들린다", "genre": "재패니즈 노스탤지아", "thumbnail": "https://picsum.photos/seed/fam507/400/600"},
            {"title": "초속 5센티미터", "genre": "재패니즈 노스탤지아", "thumbnail": "https://picsum.photos/seed/fam508/400/600"},
            {"title": "목소리의 형태", "genre": "재패니즈 노스탤지아", "thumbnail": "https://picsum.photos/seed/fam509/400/600"},
            {"title": "언어의 정원", "genre": "재패니즈 노스탤지아", "thumbnail": "https://picsum.photos/seed/fam510/400/600"},
            # ── 지브리 ──────────────────────────────────────────
            {"title": "센과 치히로의 행방불명", "genre": "지브리", "thumbnail": "https://picsum.photos/seed/fam601/400/600"},
            {"title": "이웃집 토토로", "genre": "지브리", "thumbnail": "https://picsum.photos/seed/fam602/400/600"},
            {"title": "모노노케 히메", "genre": "지브리", "thumbnail": "https://picsum.photos/seed/fam603/400/600"},
            {"title": "하울의 움직이는 성", "genre": "지브리", "thumbnail": "https://picsum.photos/seed/fam604/400/600"},
            {"title": "바람계곡의 나우시카", "genre": "지브리", "thumbnail": "https://picsum.photos/seed/fam605/400/600"},
            {"title": "천공의 성 라퓨타", "genre": "지브리", "thumbnail": "https://picsum.photos/seed/fam606/400/600"},
            {"title": "마녀 배달부 키키", "genre": "지브리", "thumbnail": "https://picsum.photos/seed/fam607/400/600"},
            {"title": "붉은 돼지", "genre": "지브리", "thumbnail": "https://picsum.photos/seed/fam608/400/600"},
            {"title": "가구야 공주 이야기", "genre": "지브리", "thumbnail": "https://picsum.photos/seed/fam609/400/600"},
            {"title": "마루 밑 아리에티", "genre": "지브리", "thumbnail": "https://picsum.photos/seed/fam610/400/600"},
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_famous_movies_genre", table_name="famous_movies")
    op.drop_table("famous_movies")
