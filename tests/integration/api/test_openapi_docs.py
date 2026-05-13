import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration


def test_openapi_document_has_api_metadata(api_client: TestClient):
    response = api_client.get("/openapi.json")

    assert response.status_code == 200
    document = response.json()
    assert document["info"]["title"] == "My Life Movie API"
    assert document["info"]["version"] == "0.1.0"
    assert {tag["name"] for tag in document["tags"]} >= {"시스템", "인증", "테마", "음악", "영화"}


def test_openapi_documents_problem_details_responses(api_client: TestClient):
    document = api_client.get("/openapi.json").json()

    assert "ProblemDetailsResponse" in document["components"]["schemas"]
    login_operation = document["paths"]["/auth/login"]["post"]

    assert login_operation["responses"]["401"]["description"]
    assert (
        login_operation["responses"]["401"]["content"]["application/json"]["schema"][
            "$ref"
        ]
        == "#/components/schemas/ProblemDetailsResponse"
    )
    assert (
        login_operation["responses"]["422"]["content"]["application/json"]["schema"][
            "$ref"
        ]
        == "#/components/schemas/ProblemDetailsResponse"
    )


def test_openapi_documents_bearer_auth_and_refresh_cookie(
    api_client: TestClient,
):
    document = api_client.get("/openapi.json").json()

    security_schemes = document["components"]["securitySchemes"]
    assert security_schemes["BearerAuth"]["type"] == "http"
    assert security_schemes["BearerAuth"]["scheme"] == "bearer"

    me_operation = document["paths"]["/auth/me"]["get"]
    assert me_operation["security"] == [{"BearerAuth": []}]

    refresh_operation = document["paths"]["/auth/refresh"]["post"]
    cookie_parameters = [
        parameter
        for parameter in refresh_operation["parameters"]
        if parameter["in"] == "cookie"
    ]
    assert cookie_parameters[0]["name"] == "refresh_token"


def test_swagger_docs_endpoint_is_available(api_client: TestClient):
    response = api_client.get("/docs")

    assert response.status_code == 200
    assert "swagger-ui" in response.text.lower()


def test_openapi_documents_theme_music_movie_tags(api_client: TestClient):
    document = api_client.get("/openapi.json").json()

    assert document["paths"]["/api/v1/themes"]["get"]["tags"] == ["테마"]
    assert document["paths"]["/api/v1/music"]["get"]["tags"] == ["음악"]
    assert document["paths"]["/api/v1/music/recommend"]["post"]["tags"] == ["음악"]
    assert document["paths"]["/api/movies"]["get"]["tags"] == ["영화"]
    assert document["paths"]["/api/movies/{movie_id}/chat"]["post"]["tags"] == ["영화"]


def test_openapi_documents_theme_music_movie_summaries(api_client: TestClient):
    document = api_client.get("/openapi.json").json()

    operations = [
        document["paths"]["/api/v1/themes"]["get"],
        document["paths"]["/api/v1/music"]["get"],
        document["paths"]["/api/v1/music/recommend"]["post"],
        document["paths"]["/api/movies/draft"]["post"],
        document["paths"]["/api/movies/{movie_id}/music"]["put"],
        document["paths"]["/api/movies/{movie_id}/files"]["post"],
        document["paths"]["/api/movies/{movie_id}/chat"]["post"],
        document["paths"]["/api/movies/{movie_id}/chat"]["get"],
        document["paths"]["/api/movies/{movie_id}/summary"]["get"],
        document["paths"]["/api/movies/{movie_id}/generate"]["post"],
        document["paths"]["/api/movies"]["get"],
        document["paths"]["/api/movies/{movie_id}"]["get"],
        document["paths"]["/api/movies/{movie_id}"]["delete"],
        document["paths"]["/api/movies/{movie_id}/download"]["get"],
        document["paths"]["/api/movies/{movie_id}/share"]["post"],
    ]

    for operation in operations:
        assert operation["summary"]
        assert operation["description"]


def test_openapi_documents_movie_problem_responses(api_client: TestClient):
    document = api_client.get("/openapi.json").json()

    upload_operation = document["paths"]["/api/movies/{movie_id}/files"]["post"]
    chat_operation = document["paths"]["/api/movies/{movie_id}/chat"]["post"]
    movie_detail_operation = document["paths"]["/api/movies/{movie_id}"]["get"]

    assert upload_operation["responses"]["400"]["description"]
    assert upload_operation["responses"]["401"]["description"]
    assert upload_operation["responses"]["403"]["description"]
    assert upload_operation["responses"]["404"]["description"]
    assert upload_operation["responses"]["422"]["description"]
    assert upload_operation["responses"]["500"]["description"]

    assert chat_operation["responses"]["401"]["description"]
    assert chat_operation["responses"]["403"]["description"]
    assert chat_operation["responses"]["404"]["description"]
    assert movie_detail_operation["responses"]["404"]["description"]

    assert (
        upload_operation["responses"]["400"]["content"]["application/json"]["schema"][
            "$ref"
        ]
        == "#/components/schemas/ProblemDetailsResponse"
    )
