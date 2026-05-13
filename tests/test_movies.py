from sqlalchemy.orm import Session

from app.models.movie import Movie, MovieStatus
from app.models.video_generation_job import VideoGenerationJob, VideoGenerationJobStatus
from app.services.access_token_service import AccessTokenClaims


def create_completed_movie(
    db_session: Session,
    *,
    user_id: int,
    title: str = "나의 실제 생성 영화",
    theme_id: int = 1,
) -> Movie:
    movie = Movie(
        user_id=user_id,
        theme_id=theme_id,
        music_id=101,
        current_draft="삶의 중요한 장면을 따뜻하게 엮은 이야기",
        story_brief={"title": title, "core_emotion": "따뜻함"},
        scene_plan=[],
        generation_prompt="wide shot, cinematic life story",
        files=[],
        chat_history=[],
        status=MovieStatus.COMPLETED,
    )
    db_session.add(movie)
    db_session.commit()
    db_session.refresh(movie)

    job = VideoGenerationJob(
        movie_id=movie.id,
        user_id=user_id,
        status=VideoGenerationJobStatus.SUCCEEDED,
        provider="openai",
        provider_job_id="video_123",
        progress=100,
        input_snapshot={"provider_prompt": "wide shot, cinematic life story"},
        output_url="/generated/videos/video_123.mp4",
        thumbnail_url="/generated/thumbnails/video_123.webp",
    )
    db_session.add(job)
    db_session.commit()
    return movie


def test_get_movies_returns_current_user_movies(api_client, db_session: Session, mock_user: AccessTokenClaims):
    movie = create_completed_movie(db_session, user_id=mock_user.user_id)
    create_completed_movie(db_session, user_id=999, title="다른 사용자 영화")

    response = api_client.get("/api/movies")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == movie.id
    assert body[0]["title"] == "나의 실제 생성 영화"
    assert body[0]["genre"] == "하이틴"
    assert body[0]["status"] == "COMPLETED"
    assert body[0]["output_url"] == "/generated/videos/video_123.mp4"
    assert body[0]["thumbnail_url"] == "/generated/thumbnails/video_123.webp"


def test_get_movies_summary_shape(api_client, db_session: Session, mock_user: AccessTokenClaims):
    create_completed_movie(db_session, user_id=mock_user.user_id)

    response = api_client.get("/api/movies")

    first = response.json()[0]
    assert "id" in first
    assert "title" in first
    assert "thumbnail" in first
    assert "genre" in first
    assert "status" in first
    assert "output_url" in first
    assert "ost" not in first
    assert "similar_movies" not in first


def test_get_movie_returns_detail(api_client, db_session: Session, mock_user: AccessTokenClaims):
    movie = create_completed_movie(db_session, user_id=mock_user.user_id)

    response = api_client.get(f"/api/movies/{movie.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == movie.id
    assert body["title"] == "나의 실제 생성 영화"
    assert body["description"] == "삶의 중요한 장면을 따뜻하게 엮은 이야기"
    assert body["genre"] == "하이틴"
    assert body["sentiment"] == "따뜻함"
    assert body["status"] == "COMPLETED"
    assert body["output_url"] == "/generated/videos/video_123.mp4"
    assert isinstance(body["ost"], list)
    assert isinstance(body["similar_movies"], list)


def test_get_movie_not_found_returns_problem_detail(api_client):
    response = api_client.get(
        "/api/movies/9999",
        headers={"X-Request-ID": "req_not_found"},
    )

    assert response.status_code == 404


def test_delete_movie_returns_message(api_client, db_session: Session, mock_user: AccessTokenClaims):
    movie = create_completed_movie(db_session, user_id=mock_user.user_id)

    response = api_client.delete(f"/api/movies/{movie.id}")

    assert response.status_code == 200
    assert "message" in response.json()
    assert api_client.get(f"/api/movies/{movie.id}").status_code == 404


def test_delete_movie_not_found_returns_problem_detail(api_client):
    response = api_client.delete(
        "/api/movies/9999",
        headers={"X-Request-ID": "req_del_not_found"},
    )

    assert response.status_code == 404


def test_download_movie_returns_info(api_client, db_session: Session, mock_user: AccessTokenClaims):
    movie = create_completed_movie(db_session, user_id=mock_user.user_id)

    response = api_client.get(f"/api/movies/{movie.id}/download")

    assert response.status_code == 200
    body = response.json()
    assert body["movie_id"] == movie.id
    assert body["title"] == "나의 실제 생성 영화"
    assert body["output_url"] == "/generated/videos/video_123.mp4"
    assert "message" in body


def test_download_movie_not_found_returns_problem_detail(api_client):
    response = api_client.get(
        "/api/movies/9999/download",
        headers={"X-Request-ID": "req_dl_not_found"},
    )

    assert response.status_code == 404


def test_request_id_propagated_in_movie_response(api_client):
    response = api_client.get(
        "/api/movies",
        headers={"X-Request-ID": "req_movie_id_test"},
    )

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "req_movie_id_test"


def test_get_similar_movies_returns_200(api_client, db_session: Session, mock_user: AccessTokenClaims):
    movie = create_completed_movie(db_session, user_id=mock_user.user_id, theme_id=1)

    response = api_client.get(f"/api/movies/{movie.id}/similar")

    assert response.status_code == 200


def test_get_similar_movies_response_shape(api_client, db_session: Session, mock_user: AccessTokenClaims):
    movie = create_completed_movie(db_session, user_id=mock_user.user_id, theme_id=1)

    response = api_client.get(f"/api/movies/{movie.id}/similar")

    body = response.json()
    assert body["movie_id"] == movie.id
    assert isinstance(body["similar_movies"], list)


def test_get_similar_movies_item_shape(api_client, db_session: Session, mock_user: AccessTokenClaims):
    movie = create_completed_movie(db_session, user_id=mock_user.user_id, theme_id=1)

    response = api_client.get(f"/api/movies/{movie.id}/similar")

    movies = response.json()["similar_movies"]
    assert len(movies) > 0
    first = movies[0]
    assert "id" in first
    assert "title" in first
    assert "thumbnail" in first


def test_get_similar_movies_limit(api_client, db_session: Session, mock_user: AccessTokenClaims):
    movie = create_completed_movie(db_session, user_id=mock_user.user_id, theme_id=1)

    response = api_client.get(f"/api/movies/{movie.id}/similar")

    movies = response.json()["similar_movies"]
    assert len(movies) <= 4


def test_get_similar_movies_genre_based(api_client, db_session: Session, mock_user: AccessTokenClaims):
    first_movie = create_completed_movie(
        db_session,
        user_id=mock_user.user_id,
        title="하이틴 영화",
        theme_id=1,
    )
    second_movie = create_completed_movie(
        db_session,
        user_id=mock_user.user_id,
        title="사이버펑크 영화",
        theme_id=2,
    )
    res1 = api_client.get(f"/api/movies/{first_movie.id}/similar")
    res2 = api_client.get(f"/api/movies/{second_movie.id}/similar")

    ids1 = {m["id"] for m in res1.json()["similar_movies"]}
    ids2 = {m["id"] for m in res2.json()["similar_movies"]}
    assert ids1.isdisjoint(ids2)


def test_get_similar_movies_not_found_returns_problem_detail(api_client):
    response = api_client.get(
        "/api/movies/9999/similar",
        headers={"X-Request-ID": "req_similar_not_found"},
    )

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "MOVIE_NOT_FOUND"
    assert body["request_id"] == "req_similar_not_found"
