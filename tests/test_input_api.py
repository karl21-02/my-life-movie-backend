import io


def _create_draft(api_client, theme_id: int = 1) -> int:
    return api_client.post("/api/movies/draft", json={"theme_id": theme_id}).json()["movie_id"]


def test_upload_image_file_returns_file_info(api_client):
    movie_id = _create_draft(api_client)

    response = api_client.post(
        f"/api/movies/{movie_id}/files",
        files={"file": ("photo.jpg", io.BytesIO(b"fake image data"), "image/jpeg")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "photo.jpg"
    assert body["type"] == "image"
    assert "file_id" in body


def test_upload_disallowed_file_type_returns_400(api_client):
    movie_id = _create_draft(api_client)

    response = api_client.post(
        f"/api/movies/{movie_id}/files",
        files={"file": ("malware.exe", io.BytesIO(b"bad data"), "application/octet-stream")},
    )

    assert response.status_code == 400


def test_upload_file_to_unknown_movie_returns_404(api_client):
    response = api_client.post(
        "/api/movies/99999/files",
        files={"file": ("photo.jpg", io.BytesIO(b"data"), "image/jpeg")},
    )

    assert response.status_code == 404


def test_chat_returns_ai_question_and_draft(api_client):
    movie_id = _create_draft(api_client)

    response = api_client.post(
        f"/api/movies/{movie_id}/chat",
        json={"message": "초등학교 시절 친구들과 뛰놀던 기억이 있어요"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "ai_question" in body
    assert "current_draft" in body
    assert "story_brief" in body
    assert "scene_plan" in body
    assert len(body["ai_question"]) > 0
    assert len(body["scene_plan"]) > 0


def test_chat_to_unknown_movie_returns_404(api_client):
    response = api_client.post(
        "/api/movies/99999/chat",
        json={"message": "테스트"},
    )

    assert response.status_code == 404


def test_get_chat_history_returns_conversation(api_client):
    movie_id = _create_draft(api_client)

    api_client.post(f"/api/movies/{movie_id}/chat", json={"message": "첫 번째 메시지"})
    api_client.post(f"/api/movies/{movie_id}/chat", json={"message": "두 번째 메시지"})

    response = api_client.get(f"/api/movies/{movie_id}/chat")

    assert response.status_code == 200
    history = response.json()["history"]
    assert len(history) == 4  # user + ai 각 2회


def test_chat_returns_timeout_message_when_gpt_times_out(api_client, monkeypatch):
    import httpx
    from openai import APITimeoutError
    from app.core.config import Settings

    async def fake_gpt_timeout(api_key, history):
        raise APITimeoutError(request=httpx.Request("POST", "https://api.openai.com"))

    monkeypatch.setattr("app.services.story_generation_service._call_gpt", fake_gpt_timeout)
    monkeypatch.setattr("app.api.movies.router.get_settings", lambda: Settings(openai_api_key="fake-key"))

    movie_id = _create_draft(api_client)
    response = api_client.post(f"/api/movies/{movie_id}/chat", json={"message": "테스트"})

    assert response.status_code == 200
    assert "초과" in response.json()["ai_question"]
    assert len(response.json()["scene_plan"]) > 0


def test_get_chat_history_for_unknown_movie_returns_404(api_client):
    response = api_client.get("/api/movies/99999/chat")

    assert response.status_code == 404
