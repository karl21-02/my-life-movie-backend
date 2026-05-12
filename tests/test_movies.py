from fastapi.testclient import TestClient

from app.main import create_app


def create_test_client() -> TestClient:
    return TestClient(create_app(), raise_server_exceptions=False)


# ── 목록 조회 ───────────────────────────────────────────────

def test_get_movies_returns_list():
    response = create_test_client().get("/api/v1/movies")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) > 0


def test_get_movies_summary_shape():
    response = create_test_client().get("/api/v1/movies")

    first = response.json()[0]
    assert "id" in first
    assert "title" in first
    assert "thumbnail" in first
    assert "genre" in first
    # 상세 정보는 목록에 포함되지 않아야 한다
    assert "ost" not in first
    assert "similar_movies" not in first


# ── 상세 조회 ───────────────────────────────────────────────

def test_get_movie_returns_detail():
    response = create_test_client().get("/api/v1/movies/1")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 1
    assert "title" in body
    assert "description" in body
    assert "genre" in body
    assert "sentiment" in body
    assert isinstance(body["ost"], list)
    assert isinstance(body["similar_movies"], list)


def test_get_movie_ost_shape():
    response = create_test_client().get("/api/v1/movies/1")

    ost = response.json()["ost"]
    assert len(ost) > 0
    assert "title" in ost[0]
    assert "artist" in ost[0]


def test_get_movie_not_found_returns_problem_detail():
    response = create_test_client().get(
        "/api/v1/movies/9999",
        headers={"X-Request-ID": "req_not_found"},
    )

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "MOVIE_NOT_FOUND"
    assert body["status"] == 404
    assert body["request_id"] == "req_not_found"


# ── 삭제 ────────────────────────────────────────────────────

def test_delete_movie_returns_message():
    client = create_test_client()
    assert client.get("/api/v1/movies/3").status_code == 200

    response = client.delete("/api/v1/movies/3")

    assert response.status_code == 200
    assert "message" in response.json()


def test_delete_movie_not_found_returns_problem_detail():
    response = create_test_client().delete(
        "/api/v1/movies/9999",
        headers={"X-Request-ID": "req_del_not_found"},
    )

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "MOVIE_NOT_FOUND"
    assert body["request_id"] == "req_del_not_found"


# ── 다운로드 ─────────────────────────────────────────────────

def test_download_movie_returns_info():
    response = create_test_client().get("/api/v1/movies/1/download")

    assert response.status_code == 200
    body = response.json()
    assert body["movie_id"] == 1
    assert "title" in body
    assert "message" in body


def test_download_movie_not_found_returns_problem_detail():
    response = create_test_client().get(
        "/api/v1/movies/9999/download",
        headers={"X-Request-ID": "req_dl_not_found"},
    )

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "MOVIE_NOT_FOUND"
    assert body["request_id"] == "req_dl_not_found"


# ── request id 전파 ──────────────────────────────────────────

def test_request_id_propagated_in_movie_response():
    response = create_test_client().get(
        "/api/v1/movies",
        headers={"X-Request-ID": "req_movie_id_test"},
    )

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "req_movie_id_test"


# ── 비슷한 영화 추천 ──────────────────────────────────────────

def test_get_similar_movies_returns_200():
    response = create_test_client().get("/api/v1/movies/1/similar")

    assert response.status_code == 200


def test_get_similar_movies_response_shape():
    response = create_test_client().get("/api/v1/movies/1/similar")

    body = response.json()
    assert body["movie_id"] == 1
    assert isinstance(body["similar_movies"], list)


def test_get_similar_movies_item_shape():
    response = create_test_client().get("/api/v1/movies/1/similar")

    movies = response.json()["similar_movies"]
    assert len(movies) > 0
    first = movies[0]
    assert "id" in first
    assert "title" in first
    assert "thumbnail" in first


def test_get_similar_movies_excludes_self():
    response = create_test_client().get("/api/v1/movies/1/similar")

    ids = [m["id"] for m in response.json()["similar_movies"]]
    assert 1 not in ids


def test_get_similar_movies_limit():
    response = create_test_client().get("/api/v1/movies/1/similar")

    movies = response.json()["similar_movies"]
    assert len(movies) <= 4


def test_get_similar_movies_not_found_returns_problem_detail():
    response = create_test_client().get(
        "/api/v1/movies/9999/similar",
        headers={"X-Request-ID": "req_similar_not_found"},
    )

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "MOVIE_NOT_FOUND"
    assert body["request_id"] == "req_similar_not_found"
