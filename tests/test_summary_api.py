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
    assert body["story_brief"] is None
    assert body["scene_plan"] == []
    assert body["generation_prompt"] is None


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
    assert response.json()["story_brief"]["title"] == "나의 인생 영화"
    assert len(response.json()["scene_plan"]) > 0
    assert "장면 구성" in response.json()["generation_prompt"]


def test_summary_for_unknown_movie_returns_404(api_client):
    response = api_client.get("/api/movies/99999/summary")

    assert response.status_code == 404


def test_generate_creates_queued_generation_job(api_client):
    movie_id = _create_draft(api_client)
    api_client.post(f"/api/movies/{movie_id}/chat", json={"message": "학창시절 이야기"})

    response = api_client.post(f"/api/movies/{movie_id}/generate")

    assert response.status_code == 200
    body = response.json()
    assert body["movie_id"] == movie_id
    assert body["job_id"] > 0
    assert body["status"] == "QUEUED"
    assert body["progress"] == 0


def test_generate_without_story_input_returns_409(api_client):
    movie_id = _create_draft(api_client)

    response = api_client.post(f"/api/movies/{movie_id}/generate")

    assert response.status_code == 409
    assert response.json()["code"] == "GENERATION_INPUT_NOT_READY"


def test_generate_duplicate_in_progress_job_returns_409(api_client):
    movie_id = _create_draft(api_client)
    api_client.post(f"/api/movies/{movie_id}/chat", json={"message": "학창시절 이야기"})
    api_client.post(f"/api/movies/{movie_id}/generate")

    response = api_client.post(f"/api/movies/{movie_id}/generate")

    assert response.status_code == 409
    assert response.json()["code"] == "GENERATION_ALREADY_IN_PROGRESS"


def test_get_generation_status_returns_latest_job(api_client):
    movie_id = _create_draft(api_client)
    api_client.post(f"/api/movies/{movie_id}/chat", json={"message": "학창시절 이야기"})
    created = api_client.post(f"/api/movies/{movie_id}/generate").json()

    response = api_client.get(f"/api/movies/{movie_id}/generation")

    assert response.status_code == 200
    body = response.json()
    assert body["movie_id"] == movie_id
    assert body["job_id"] == created["job_id"]
    assert body["status"] == "QUEUED"
    assert body["progress"] == 0


def test_get_generation_status_without_job_returns_404(api_client):
    movie_id = _create_draft(api_client)

    response = api_client.get(f"/api/movies/{movie_id}/generation")

    assert response.status_code == 404
    assert response.json()["code"] == "GENERATION_JOB_NOT_FOUND"


def test_cancel_generation_marks_in_progress_job_canceled(api_client):
    movie_id = _create_draft(api_client)
    api_client.post(f"/api/movies/{movie_id}/chat", json={"message": "학창시절 이야기"})
    created = api_client.post(f"/api/movies/{movie_id}/generate").json()

    response = api_client.post(f"/api/movies/{movie_id}/generation/cancel")

    assert response.status_code == 200
    body = response.json()
    assert body["movie_id"] == movie_id
    assert body["job_id"] == created["job_id"]
    assert body["status"] == "CANCELED"


def test_cancel_generation_without_in_progress_job_returns_404(api_client):
    movie_id = _create_draft(api_client)

    response = api_client.post(f"/api/movies/{movie_id}/generation/cancel")

    assert response.status_code == 404
    assert response.json()["code"] == "GENERATION_JOB_NOT_FOUND"


def test_generate_for_unknown_movie_returns_404(api_client):
    response = api_client.post("/api/movies/99999/generate")

    assert response.status_code == 404
