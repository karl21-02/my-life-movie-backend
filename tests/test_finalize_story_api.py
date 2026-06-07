from app.models.movie import Movie


def _create_draft(api_client, theme_id: int = 1) -> int:
    return api_client.post("/api/movies/draft", json={"theme_id": theme_id}).json()["movie_id"]


def test_finalize_story_without_input_returns_409(api_client, monkeypatch):
    called = False

    async def fake_finalize_story(**kwargs):
        nonlocal called
        called = True
        raise AssertionError("finalize_story should not be called for empty input")

    monkeypatch.setattr("app.api.movies.router.finalize_story", fake_finalize_story)
    movie_id = _create_draft(api_client)

    response = api_client.post(f"/api/movies/{movie_id}/finalize-story")

    assert response.status_code == 409
    assert response.json()["code"] == "GENERATION_INPUT_NOT_READY"
    assert called is False


def test_finalize_story_fills_generation_inputs(api_client, db_session):
    movie_id = _create_draft(api_client)
    api_client.post(f"/api/movies/{movie_id}/chat", json={"message": "학창시절 이야기"})

    response = api_client.post(f"/api/movies/{movie_id}/finalize-story")

    assert response.status_code == 200
    body = response.json()
    assert body["story_brief"]["title"] == "나의 인생 영화"
    assert len(body["scene_plan"]) > 0
    assert "장면 구성" in body["generation_prompt"]
    assert body["is_finalized"] is True

    movie = db_session.get(Movie, movie_id)
    assert movie.story_brief["title"] == "나의 인생 영화"
    assert len(movie.scene_plan) > 0
    assert movie.generation_prompt


def test_finalize_story_is_idempotent_when_already_finalized(
    api_client,
    db_session,
    monkeypatch,
):
    async def fake_finalize_story(**kwargs):
        raise AssertionError("finalize_story should not be called for finalized input")

    monkeypatch.setattr("app.api.movies.router.finalize_story", fake_finalize_story)
    movie_id = _create_draft(api_client)
    movie = db_session.get(Movie, movie_id)
    movie.current_draft = "이미 확정된 이야기"
    movie.story_brief = {"title": "확정된 제목"}
    movie.scene_plan = [{"order": 1, "visual_prompt": "confirmed scene"}]
    movie.generation_prompt = "확정된 프롬프트"
    db_session.commit()

    response = api_client.post(f"/api/movies/{movie_id}/finalize-story")

    assert response.status_code == 200
    body = response.json()
    assert body["story_brief"]["title"] == "확정된 제목"
    assert body["generation_prompt"] == "확정된 프롬프트"
    assert body["is_finalized"] is True


def test_finalize_story_for_unknown_movie_returns_404(api_client):
    response = api_client.post("/api/movies/99999/finalize-story")

    assert response.status_code == 404
