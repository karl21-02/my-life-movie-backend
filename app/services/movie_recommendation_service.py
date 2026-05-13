import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from openai import OpenAI

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.movie import Movie
from app.models.movie_recommendation import MovieRecommendation
from app.repositories.movie_recommendation_repository import MovieRecommendationRepository

logger = get_logger(__name__)


@dataclass(frozen=True)
class MovieRecommendationPlan:
    movie_titles: list[str]
    queries: list[str]
    keywords: list[str]
    mood: str
    reason_template: str


@dataclass(frozen=True)
class RecommendedMovie:
    id: int
    title: str
    thumbnail: str
    external_url: str | None = None
    provider: str = "tmdb"
    reason: str | None = None
    score: float = 0.0


class MovieMetadataProvider(Protocol):
    def search_movies(self, query: str, *, limit: int = 6) -> list[dict]:
        ...


class RecommendationPlanner(Protocol):
    def build_plan(self, movie: Movie, genre: str) -> MovieRecommendationPlan:
        ...


class OpenAIRecommendationPlanner:
    def __init__(
        self,
        *,
        api_key: str,
        timeout_seconds: float = 8,
        client: OpenAI | None = None,
    ) -> None:
        self.client = client or OpenAI(api_key=api_key, timeout=timeout_seconds)

    def build_plan(self, movie: Movie, genre: str) -> MovieRecommendationPlan:
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a movie recommendation search strategist. Return JSON only with this exact schema: "
                        '{"movie_titles":["real existing movie title"],"queries":["english tmdb search query"],'
                        '"keywords":["english similarity keyword"],'
                        '"mood":"english mood","reason_template":"Korean one sentence reason"}. '
                        "Use the user's life story, genre, emotions, scenes, and visual style. "
                        "movie_titles must contain real existing films that are thematically similar. "
                        "queries must be 3 to 5 short TMDB search queries. Do not invent fake movie titles."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(build_movie_recommendation_context(movie, genre), ensure_ascii=False),
                },
            ],
            response_format={"type": "json_object"},
            max_tokens=500,
        )
        content = response.choices[0].message.content or "{}"
        return parse_recommendation_plan(json.loads(content), movie, genre)


class TMDBMovieMetadataProvider:
    def __init__(
        self,
        *,
        access_token: str,
        api_base_url: str,
        image_base_url: str,
        poster_size: str,
        language: str,
        timeout_seconds: float,
        client: httpx.Client | None = None,
    ) -> None:
        self.access_token = access_token
        self.api_base_url = api_base_url.rstrip("/")
        self.image_base_url = image_base_url.rstrip("/")
        self.poster_size = poster_size.strip("/")
        self.language = language
        self.client = client or httpx.Client(timeout=timeout_seconds)

    def search_movies(self, query: str, *, limit: int = 6) -> list[dict]:
        if not self.access_token or not query.strip():
            return []

        response = self.client.get(
            f"{self.api_base_url}/search/movie",
            headers={"Authorization": f"Bearer {self.access_token}"},
            params={
                "query": query,
                "language": self.language,
                "include_adult": "false",
                "page": 1,
            },
        )
        response.raise_for_status()
        results = response.json().get("results")
        if not isinstance(results, list):
            return []
        return [result for result in results[:limit] if isinstance(result, dict)]

    def poster_url(self, poster_path: str | None) -> str:
        if not poster_path:
            return ""
        return f"{self.image_base_url}/{self.poster_size}/{poster_path.lstrip('/')}"


class MovieRecommendationService:
    def __init__(
        self,
        *,
        metadata_provider: TMDBMovieMetadataProvider | None = None,
        planner: RecommendationPlanner | None = None,
        recommendation_repository: MovieRecommendationRepository | None = None,
    ) -> None:
        self.metadata_provider = metadata_provider
        self.planner = planner
        self.recommendation_repository = recommendation_repository

    def recommend_for_movie(self, movie: Movie, genre: str, *, limit: int = 4) -> list[RecommendedMovie]:
        if self.metadata_provider is None or self.planner is None:
            return []

        plan = self.build_plan(movie, genre)
        if plan is None:
            return []
        candidates = self.collect_tmdb_candidates(build_tmdb_search_queries(plan))
        ranked_movies = rank_tmdb_candidates(candidates, plan)
        return [
            build_recommended_movie(candidate, self.metadata_provider, plan)
            for candidate in ranked_movies[:limit]
        ]

    def build_plan(self, movie: Movie, genre: str) -> MovieRecommendationPlan | None:
        try:
            return self.planner.build_plan(movie, genre)
        except Exception as exc:
            logger.warning(
                "추천 검색 계획 생성에 실패했습니다.",
                extra={
                    "event": "movie_recommendation_plan_failed",
                    "movie_id": movie.id,
                    "error_type": type(exc).__name__,
                },
            )
            return None

    def collect_tmdb_candidates(self, queries: list[str]) -> list[dict]:
        seen_ids: set[int] = set()
        candidates: list[dict] = []
        for query in queries:
            try:
                results = self.metadata_provider.search_movies(query, limit=8) if self.metadata_provider else []
            except Exception as exc:
                logger.warning(
                    "TMDB 추천 후보 검색에 실패했습니다.",
                    extra={
                        "event": "movie_recommendation_tmdb_search_failed",
                        "query": query,
                        "error_type": type(exc).__name__,
                    },
                )
                results = []
            for result in results:
                movie_id = result.get("id")
                if isinstance(movie_id, int) and movie_id not in seen_ids:
                    seen_ids.add(movie_id)
                    candidates.append({**result, "_recommendation_query": query})
        return candidates

    def get_or_create_for_movie(
        self,
        *,
        movie: Movie,
        genre: str,
        limit: int = 4,
    ) -> list[RecommendedMovie]:
        if self.recommendation_repository is None:
            return self.recommend_for_movie(movie, genre, limit=limit)

        stored_recommendations = self.recommendation_repository.list_by_movie_id(movie.id)
        if stored_recommendations:
            return [
                recommended_movie_from_model(recommendation)
                for recommendation in stored_recommendations[:limit]
            ]

        recommendations = self.recommend_for_movie(movie, genre, limit=limit)
        if not recommendations:
            return []

        stored_recommendations = self.recommendation_repository.replace_for_movie(
            movie_id=movie.id,
            recommendations=[
                movie_recommendation_model_from_recommended_movie(
                    movie_id=movie.id,
                    recommendation=recommendation,
                    rank=index + 1,
                )
                for index, recommendation in enumerate(recommendations)
            ],
        )
        return [
            recommended_movie_from_model(recommendation)
            for recommendation in stored_recommendations[:limit]
        ]


def build_movie_recommendation_service(settings: Settings) -> MovieRecommendationService:
    provider = None
    if settings.tmdb_access_token:
        provider = TMDBMovieMetadataProvider(
            access_token=settings.tmdb_access_token,
            api_base_url=settings.tmdb_api_base_url,
            image_base_url=settings.tmdb_image_base_url,
            poster_size=settings.tmdb_poster_size,
            language=settings.tmdb_language,
            timeout_seconds=settings.tmdb_timeout_seconds,
        )

    planner: RecommendationPlanner | None = None
    if settings.openai_api_key:
        planner = OpenAIRecommendationPlanner(api_key=settings.openai_api_key)

    return MovieRecommendationService(metadata_provider=provider, planner=planner)


def build_movie_recommendation_context(movie: Movie, genre: str) -> dict[str, Any]:
    story_brief = movie.story_brief if isinstance(movie.story_brief, dict) else {}
    return {
        "genre": genre,
        "summary": movie.current_draft or "",
        "generation_prompt": movie.generation_prompt or "",
        "story": story_brief,
        "scenes": movie.scene_plan if isinstance(movie.scene_plan, list) else [],
    }


def parse_recommendation_plan(data: dict[str, Any], movie: Movie, genre: str) -> MovieRecommendationPlan:
    movie_titles = dedupe_texts([normalize_text(title) for title in read_text_array(data, "movie_titles")])
    queries = dedupe_texts([normalize_text(query) for query in read_text_array(data, "queries")])
    keywords = dedupe_texts([normalize_text(keyword) for keyword in read_text_array(data, "keywords")])
    if not movie_titles or not queries or not keywords:
        raise ValueError("추천 검색 계획에 movie_titles, queries, keywords가 필요합니다.")
    return MovieRecommendationPlan(
        movie_titles=movie_titles[:8],
        queries=queries[:5],
        keywords=keywords[:12],
        mood=normalize_text(data.get("mood")) or genre,
        reason_template=normalize_text(data.get("reason_template")) or "스토리 분위기와 감정선이 유사합니다.",
    )


def rank_tmdb_candidates(candidates: list[dict], plan: MovieRecommendationPlan) -> list[dict]:
    scored_candidates = [
        (score_tmdb_candidate(candidate, plan), candidate)
        for candidate in candidates
    ]
    scored_candidates.sort(key=lambda item: item[0], reverse=True)
    return [
        {**candidate, "_similarity_score": score}
        for score, candidate in scored_candidates
        if score > 0
    ]


def build_tmdb_search_queries(plan: MovieRecommendationPlan) -> list[str]:
    return dedupe_texts([*plan.movie_titles, *plan.queries, *plan.keywords[:5]])[:12]


def score_tmdb_candidate(candidate: dict, plan: MovieRecommendationPlan) -> float:
    searchable_text = normalize_text(
        " ".join(
            [
                str(candidate.get("title") or ""),
                str(candidate.get("original_title") or ""),
                str(candidate.get("overview") or ""),
            ]
        )
    ).lower()
    score = 0.0
    source_query = normalize_text(candidate.get("_recommendation_query")).lower()
    if source_query in {title.lower() for title in plan.movie_titles}:
        candidate_titles = {
            normalize_text(candidate.get("title")).lower(),
            normalize_text(candidate.get("original_title")).lower(),
        }
        if source_query in candidate_titles:
            score += 6.0
    for keyword in plan.keywords:
        normalized_keyword = keyword.lower()
        if normalized_keyword and normalized_keyword in searchable_text:
            score += 2.0
        else:
            score += keyword_overlap_score(normalized_keyword, searchable_text)

    popularity = candidate.get("popularity")
    if isinstance(popularity, int | float):
        score += min(float(popularity) / 100, 1.5)
    if candidate.get("poster_path"):
        score += 0.5
    return round(score, 4)


def keyword_overlap_score(keyword: str, text: str) -> float:
    tokens = [token for token in re.split(r"\W+", keyword) if len(token) >= 3]
    if not tokens:
        return 0.0
    return sum(0.4 for token in tokens if token in text)


def build_recommended_movie(
    candidate: dict,
    provider: TMDBMovieMetadataProvider,
    plan: MovieRecommendationPlan,
) -> RecommendedMovie:
    movie_id = candidate.get("id")
    title = candidate.get("title") or candidate.get("name") or candidate.get("original_title")
    if not isinstance(movie_id, int) or not isinstance(title, str) or not title:
        raise ValueError("TMDB 추천 후보에 필수 값이 없습니다.")

    score = float(candidate.get("_similarity_score") or 0.0)
    return RecommendedMovie(
        id=movie_id,
        title=title,
        thumbnail=provider.poster_url(candidate.get("poster_path")),
        external_url=f"https://www.themoviedb.org/movie/{movie_id}",
        provider="tmdb",
        reason=plan.reason_template,
        score=score,
    )


def recommended_movie_from_model(model: MovieRecommendation) -> RecommendedMovie:
    provider_movie_id = model.provider_movie_id
    parsed_id = int(provider_movie_id) if provider_movie_id and provider_movie_id.isdigit() else model.id
    metadata = model.metadata_json if isinstance(model.metadata_json, dict) else {}
    score = metadata.get("score")
    return RecommendedMovie(
        id=parsed_id,
        title=model.title,
        thumbnail=model.poster_url,
        external_url=model.external_url,
        provider=model.provider,
        reason=model.reason,
        score=float(score) if isinstance(score, int | float) else 0.0,
    )


def movie_recommendation_model_from_recommended_movie(
    *,
    movie_id: int,
    recommendation: RecommendedMovie,
    rank: int,
) -> MovieRecommendation:
    return MovieRecommendation(
        movie_id=movie_id,
        provider=recommendation.provider,
        provider_movie_id=str(recommendation.id),
        title=recommendation.title,
        poster_url=recommendation.thumbnail,
        external_url=recommendation.external_url,
        rank=rank,
        reason=recommendation.reason,
        metadata_json={"source": recommendation.provider, "score": recommendation.score},
    )


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def as_text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [normalize_text(item) for item in value if normalize_text(item)]
    text = normalize_text(value)
    return [text] if text else []


def read_text_array(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list):
        return []
    return [normalize_text(item) for item in value if normalize_text(item)]


def dedupe_texts(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = normalize_text(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result
