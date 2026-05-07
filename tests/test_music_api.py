from fastapi.testclient import TestClient

from app.main import create_app


def create_test_client() -> TestClient:
    return TestClient(create_app())


def test_get_music_by_theme_returns_tracks():
    response = create_test_client().get("/api/v1/music?theme_id=1")

    assert response.status_code == 200
    body = response.json()
    assert "default_tracks" in body
    assert len(body["default_tracks"]) > 0


def test_get_music_track_contains_required_fields():
    response = create_test_client().get("/api/v1/music?theme_id=1")

    track = response.json()["default_tracks"][0]
    assert "music_id" in track
    assert "title" in track
    assert "file_url" in track


def test_get_music_returns_empty_for_unknown_theme():
    response = create_test_client().get("/api/v1/music?theme_id=999")

    assert response.status_code == 200
    assert response.json()["default_tracks"] == []


def test_recommend_music_returns_ai_message_and_tracks():
    response = create_test_client().post(
        "/api/v1/music/recommend",
        json={"movie_id": 1, "message": "잔잔하고 따뜻한 분위기가 좋아요"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "ai_message" in body
    assert "tracks" in body
    assert len(body["tracks"]) > 0


def test_update_music_saves_selection():
    client = create_test_client()

    draft = client.post("/api/v1/movies/draft", json={"theme_id": 1}).json()
    movie_id = draft["movie_id"]

    response = client.put(
        f"/api/v1/movies/{movie_id}/music",
        json={"music_id": 101},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["movie_id"] == movie_id
    assert body["music_id"] == 101


def test_update_music_returns_404_for_unknown_movie():
    response = create_test_client().put(
        "/api/v1/movies/99999/music",
        json={"music_id": 101},
    )

    assert response.status_code == 404
