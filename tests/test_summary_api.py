import io


def _create_draft(api_client, theme_id: int = 1) -> int:
    return api_client.post("/api/movies/draft", json={"theme_id": theme_id}).json()["movie_id"]


def test_summary_returns_theme_and_empty_defaults(api_client):
    movie_id = _create_draft(api_client, theme_id=2)

    response = api_client.get(f"/api/movies/{movie_id}/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["theme"]["theme_id"] == 2
    assert body["files"] == []
    assert body["music"] is None


def test_summary_includes_uploaded_files(api_client):
    movie_id = _create_draft(api_client)

    api_client.post(
        f"/api/movies/{movie_id}/files",
        files={"file": ("photo.jpg", io.BytesIO(b"data"), "image/jpeg")},
    )

    response = api_client.get(f"/api/movies/{movie_id}/summary")

    assert response.status_code == 200
    assert len(response.json()["files"]) == 1


def test_summary_includes_music_after_selection(api_client):
    movie_id = _create_draft(api_client)

    api_client.put(f"/api/movies/{movie_id}/music", json={"music_id": 101})

    response = api_client.get(f"/api/movies/{movie_id}/summary")

    assert response.status_code == 200
    assert response.json()["music"]["music_id"] == 101


def test_summary_includes_prompt_after_chat(api_client):
    movie_id = _create_draft(api_client)

    api_client.post(f"/api/movies/{movie_id}/chat", json={"message": "학창시절 이야기"})

    response = api_client.get(f"/api/movies/{movie_id}/summary")

    assert response.status_code == 200
    assert len(response.json()["prompt"]) > 0


def test_summary_for_unknown_movie_returns_404(api_client):
    response = api_client.get("/api/movies/99999/summary")

    assert response.status_code == 404


def test_generate_changes_status_to_generating(api_client):
    movie_id = _create_draft(api_client)

    response = api_client.post(f"/api/movies/{movie_id}/generate")

    assert response.status_code == 200
    assert response.json()["status"] == "GENERATING"


def test_generate_for_unknown_movie_returns_404(api_client):
    response = api_client.post("/api/movies/99999/generate")

    assert response.status_code == 404
