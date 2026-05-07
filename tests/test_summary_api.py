import io
from fastapi.testclient import TestClient

from app.main import create_app


def create_test_client() -> TestClient:
    return TestClient(create_app())


def _create_draft(client: TestClient, theme_id: int = 1) -> int:
    return client.post("/api/v1/movies/draft", json={"theme_id": theme_id}).json()["movie_id"]


def test_summary_returns_theme_and_empty_defaults():
    client = create_test_client()
    movie_id = _create_draft(client, theme_id=2)

    response = client.get(f"/api/v1/movies/{movie_id}/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["theme"]["theme_id"] == 2
    assert body["files"] == []
    assert body["music"] is None


def test_summary_includes_uploaded_files():
    client = create_test_client()
    movie_id = _create_draft(client)

    client.post(
        f"/api/v1/movies/{movie_id}/files",
        files={"file": ("photo.jpg", io.BytesIO(b"data"), "image/jpeg")},
    )

    response = client.get(f"/api/v1/movies/{movie_id}/summary")

    assert response.status_code == 200
    assert len(response.json()["files"]) == 1


def test_summary_includes_music_after_selection():
    client = create_test_client()
    movie_id = _create_draft(client)

    client.put(f"/api/v1/movies/{movie_id}/music", json={"music_id": 101})

    response = client.get(f"/api/v1/movies/{movie_id}/summary")

    assert response.status_code == 200
    assert response.json()["music"]["music_id"] == 101


def test_summary_includes_prompt_after_chat():
    client = create_test_client()
    movie_id = _create_draft(client)

    client.post(f"/api/v1/movies/{movie_id}/chat", json={"message": "학창시절 이야기"})

    response = client.get(f"/api/v1/movies/{movie_id}/summary")

    assert response.status_code == 200
    assert len(response.json()["prompt"]) > 0


def test_summary_for_unknown_movie_returns_404():
    response = create_test_client().get("/api/v1/movies/99999/summary")

    assert response.status_code == 404


def test_generate_changes_status_to_generating():
    client = create_test_client()
    movie_id = _create_draft(client)

    response = client.post(f"/api/v1/movies/{movie_id}/generate")

    assert response.status_code == 200
    assert response.json()["status"] == "GENERATING"


def test_generate_for_unknown_movie_returns_404():
    response = create_test_client().post("/api/v1/movies/99999/generate")

    assert response.status_code == 404
