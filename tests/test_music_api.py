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
        json={
            "movie_id": 1,
            "message": "잔잔하고 따뜻한 분위기가 좋아요",
            "mood": "차분함",
            "scene": "가족과 다시 만나는 장면",
            "story_hint": "어릴 적 기억을 회상하는 이야기",
            "avoid": "너무 빠른 비트",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "ai_message" in body
    assert "tracks" in body
    assert len(body["tracks"]) > 0
    assert "artist" in body["tracks"][0]
    assert "provider" in body["tracks"][0]


def test_recommend_music_mock_returns_contextual_unique_tracks():
    client = create_test_client()

    calm_response = client.post(
        "/api/v1/music/recommend",
        json={"movie_id": 1, "message": "차분하고 따뜻한 분위기"},
    )
    bright_response = client.post(
        "/api/v1/music/recommend",
        json={"movie_id": 1, "message": "밝고 신나는 여름 분위기"},
    )

    assert calm_response.status_code == 200
    assert bright_response.status_code == 200
    calm_tracks = calm_response.json()["tracks"]
    bright_tracks = bright_response.json()["tracks"]
    assert len(calm_tracks) >= 3
    assert len(bright_tracks) >= 3
    assert calm_tracks[0]["music_id"] != bright_tracks[0]["music_id"]
    assert calm_tracks[0]["title"] != bright_tracks[0]["title"]


def test_recommend_music_returns_mock_when_empty_results(monkeypatch):
    """Spotify가 빈 결과를 반환하면 mock fallback이 내려와야 한다."""
    async def fake_get_token(client_id, client_secret):
        return "fake_token"

    async def fake_search_empty(token, query):
        return []

    from app.core.config import Settings
    monkeypatch.setattr("app.routers.music._get_spotify_token", fake_get_token)
    monkeypatch.setattr("app.routers.music._search_spotify_tracks", fake_search_empty)
    monkeypatch.setattr("app.routers.music.get_settings", lambda: Settings(
        spotify_client_id="x", spotify_client_secret="x"
    ))

    response = create_test_client().post(
        "/api/v1/music/recommend",
        json={"movie_id": 1, "message": "따뜻한 분위기"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["tracks"]) > 0


def test_recommend_music_builds_spotify_query_from_user_context(monkeypatch):
    captured_queries: list[str] = []

    async def fake_get_token(client_id, client_secret):
        return "fake_token"

    async def fake_search(token, query):
        captured_queries.append(query)
        return []

    from app.core.config import Settings
    monkeypatch.setattr("app.routers.music._get_spotify_token", fake_get_token)
    monkeypatch.setattr("app.routers.music._search_spotify_tracks", fake_search)
    monkeypatch.setattr("app.routers.music.get_settings", lambda: Settings(
        spotify_client_id="x", spotify_client_secret="x"
    ))

    response = create_test_client().post(
        "/api/v1/music/recommend",
        json={
            "movie_id": 1,
            "message": "따뜻한 영화 음악",
            "mood": "차분함",
            "scene": "졸업식 장면",
            "story_hint": "친구들과 헤어지는 성장 이야기",
            "avoid": "전자음",
        },
    )

    assert response.status_code == 200
    assert "차분함" in captured_queries[0]
    assert "졸업식 장면" in captured_queries[0]
    assert "친구들과 헤어지는 성장 이야기" in captured_queries[0]
    assert "not 전자음" in captured_queries[0]


def test_update_music_saves_selection(api_client):
    draft = api_client.post("/api/movies/draft", json={"theme_id": 1}).json()
    movie_id = draft["movie_id"]

    response = api_client.put(
        f"/api/movies/{movie_id}/music",
        json={"music_id": 101},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["movie_id"] == movie_id
    assert body["music_id"] == 101


def test_update_music_returns_404_for_unknown_movie(api_client):
    response = api_client.put(
        "/api/movies/99999/music",
        json={"music_id": 101},
    )

    assert response.status_code == 404
