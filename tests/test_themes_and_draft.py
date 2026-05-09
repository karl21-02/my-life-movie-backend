from fastapi.testclient import TestClient

from app.main import create_app


def create_test_client() -> TestClient:
    return TestClient(create_app())


def test_get_themes_returns_six_themes():
    response = create_test_client().get("/api/v1/themes")

    assert response.status_code == 200
    themes = response.json()
    assert len(themes) == 6


def test_get_themes_contains_required_fields():
    response = create_test_client().get("/api/v1/themes")

    theme = response.json()[0]
    assert "theme_id" in theme
    assert "name" in theme
    assert "description" in theme
    assert "preview_color" in theme


def test_get_themes_includes_all_six_types():
    response = create_test_client().get("/api/v1/themes")

    names = [t["name"] for t in response.json()]
    assert "하이틴" in names
    assert "사이버펑크" in names
    assert "무성영화" in names
    assert "동화" in names
    assert "재패니즈 노스탤지아" in names
    assert "지브리" in names


def test_create_draft_returns_movie_id_and_draft_status(api_client):
    response = api_client.post(
        "/api/v1/movies/draft",
        json={"theme_id": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert "movie_id" in body
    assert body["status"] == "DRAFT"


def test_create_draft_movie_id_is_positive_integer(api_client):
    response = api_client.post(
        "/api/v1/movies/draft",
        json={"theme_id": 3},
    )

    assert response.status_code == 200
    assert isinstance(response.json()["movie_id"], int)
    assert response.json()["movie_id"] > 0
