from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.application.grounding import NOT_FOUND
from app.core.config import Settings
from app.domain.entities import GroundedAnswer
from app.domain.exceptions import AIProviderError
from app.main import create_app
from tests.unit.test_documents import make_pdf


@pytest.fixture
def client(setup_services):
    services, _, _ = setup_services
    with TestClient(create_app(Settings(_env_file=None), services)) as client:
        yield client


@pytest.mark.parametrize(
    "filename,mime,content",
    [
        ("doc.txt", "text/plain", b"El proyecto reduce el consumo de agua."),
        ("doc.pdf", "application/pdf", make_pdf()),
    ],
)
def test_complete_flow_and_recover_history(client, filename, mime, content):
    session = client.post("/sessions").json()["session_id"]
    uploaded = client.post(
        "/documents",
        data={"session_id": session},
        files={"file": (filename, content, mime)},
    )
    assert uploaded.status_code == 201
    document = uploaded.json()
    assert document["status"] == "processed"
    response = client.post(
        "/ask",
        json={
            "session_id": session,
            "document_id": document["document_id"],
            "question": "¿Cuál es el objetivo?",
        },
    )
    assert response.status_code == 200
    assert "agua" in response.json()["answer"]
    assert response.json()["sources"][0]["quote"]
    history = client.get(f"/history/{session}").json()
    assert [message["role"] for message in history["messages"]] == ["user", "assistant"]
    assert history["documents"][0]["document_id"] == document["document_id"]
    assert history["messages"][1]["sources"] == response.json()["sources"]


def test_unknown_question_and_provider_error(client, setup_services):
    _, _, llm = setup_services
    session = client.post("/sessions").json()["session_id"]
    document = client.post(
        "/documents",
        data={"session_id": session},
        files={"file": ("doc.txt", b"Text", "text/plain")},
    ).json()["document_id"]
    payload = {
        "session_id": session,
        "document_id": document,
        "question": "Algo fuera del documento",
    }
    llm.result = GroundedAnswer(NOT_FOUND, [], False)
    assert client.post("/ask", json=payload).json()["answer"] == NOT_FOUND
    llm.error = AIProviderError()
    response = client.post("/ask", json=payload)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "AI_PROVIDER_ERROR"
    assert len(client.get(f"/history/{session}").json()["messages"]) == 2


def test_consistent_errors(client):
    assert client.get(f"/history/{uuid4()}").status_code == 404
    assert client.get("/history/invalid").json()["error"]["code"] == "VALIDATION_ERROR"
    assert client.post("/ask", json={}).status_code == 422
    assert client.get("/missing").json()["error"]["code"] == "HTTP_ERROR"
    session = client.post("/sessions").json()["session_id"]
    invalid = client.post(
        "/documents",
        data={"session_id": session},
        files={"file": ("script.py", b"print(1)", "text/plain")},
    )
    assert invalid.status_code == 415
    assert set(invalid.json()) == {"error"}


def test_swagger_health_and_cors(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}
    response = client.options(
        "/ask",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_oversized_streamed_request(setup_services):
    services, _, _ = setup_services
    with TestClient(
        create_app(Settings(_env_file=None, max_upload_mb=1), services)
    ) as client:
        response = client.post(
            "/documents",
            content=iter([b"x" * 600_000] * 2),
            headers={"Content-Type": "application/octet-stream"},
        )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "DOCUMENT_TOO_LARGE"
