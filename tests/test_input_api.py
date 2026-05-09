import io
from fastapi.testclient import TestClient

from app.main import create_app


def create_test_client() -> TestClient:
    return TestClient(create_app())


def _create_draft(client: TestClient) -> int:
    return client.post("/api/v1/movies/draft", json={"theme_id": 1}).json()["movie_id"]


def test_upload_image_file_returns_file_info():
    client = create_test_client()
    movie_id = _create_draft(client)

    response = client.post(
        f"/api/v1/movies/{movie_id}/files",
        files={"file": ("photo.jpg", io.BytesIO(b"fake image data"), "image/jpeg")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "photo.jpg"
    assert body["type"] == "image"
    assert "file_id" in body


def test_upload_disallowed_file_type_returns_400():
    client = create_test_client()
    movie_id = _create_draft(client)

    response = client.post(
        f"/api/v1/movies/{movie_id}/files",
        files={"file": ("malware.exe", io.BytesIO(b"bad data"), "application/octet-stream")},
    )

    assert response.status_code == 400


def test_upload_file_to_unknown_movie_returns_404():
    client = create_test_client()

    response = client.post(
        "/api/v1/movies/99999/files",
        files={"file": ("photo.jpg", io.BytesIO(b"data"), "image/jpeg")},
    )

    assert response.status_code == 404


def test_chat_returns_ai_question_and_draft():
    client = create_test_client()
    movie_id = _create_draft(client)

    response = client.post(
        f"/api/v1/movies/{movie_id}/chat",
        json={"message": "초등학교 시절 친구들과 뛰놀던 기억이 있어요"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "ai_question" in body
    assert "current_draft" in body
    assert len(body["ai_question"]) > 0


def test_chat_to_unknown_movie_returns_404():
    client = create_test_client()

    response = client.post(
        "/api/v1/movies/99999/chat",
        json={"message": "테스트"},
    )

    assert response.status_code == 404


def test_get_chat_history_returns_conversation():
    client = create_test_client()
    movie_id = _create_draft(client)

    client.post(f"/api/v1/movies/{movie_id}/chat", json={"message": "첫 번째 메시지"})
    client.post(f"/api/v1/movies/{movie_id}/chat", json={"message": "두 번째 메시지"})

    response = client.get(f"/api/v1/movies/{movie_id}/chat")

    assert response.status_code == 200
    history = response.json()["history"]
    assert len(history) == 4  # user + ai 각 2회


def test_get_chat_history_for_unknown_movie_returns_404():
    client = create_test_client()

    response = client.get("/api/v1/movies/99999/chat")

    assert response.status_code == 404
