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


def test_openapi_documents_video_generation_contract(api_client: TestClient):
    document = api_client.get("/openapi.json").json()

    generate_operation = document["paths"]["/api/movies/{movie_id}/generate"]["post"]
    status_operation = document["paths"]["/api/movies/{movie_id}/generation"]["get"]
    cancel_operation = document["paths"]["/api/movies/{movie_id}/generation/cancel"]["post"]

    assert generate_operation["tags"] == ["영화"]
    assert generate_operation["summary"] == "영상 생성 요청"
    assert generate_operation["responses"]["401"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/ProblemDetailsResponse"
    )
    assert generate_operation["responses"]["409"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/ProblemDetailsResponse"
    )
    assert status_operation["summary"] == "영상 생성 상태 조회"
    assert status_operation["responses"]["404"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/ProblemDetailsResponse"
    )
    assert cancel_operation["summary"] == "영상 생성 취소"

    status_schema = document["components"]["schemas"]["GenerationStatusResponse"]
    assert status_schema["properties"]["status"]["enum"] == [
        "QUEUED",
        "RUNNING",
        "SUCCEEDED",
        "FAILED",
        "CANCELED",
    ]
    assert status_schema["properties"]["progress"]["maximum"] == 100
