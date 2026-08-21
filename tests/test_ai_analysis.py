from types import SimpleNamespace
from typing import Any

import pytest
from httpx import AsyncClient
from kombu.exceptions import OperationalError

from app.routers import analysis as analysis_router

TENDERS_URL = "/api/v1/tenders"
pytestmark = pytest.mark.asyncio


async def create_tender(
    client: AsyncClient,
    *,
    title: str = "Bridge inspection",
    description: str = "Annual structural inspection services",
) -> dict[str, Any]:
    response = await client.post(
        TENDERS_URL,
        json={"title": title, "description": description},
    )
    assert response.status_code == 201
    return response.json()


async def create_status_history(
    client: AsyncClient,
    tender_id: int,
) -> dict[str, Any]:
    response = await client.patch(
        f"{TENDERS_URL}/{tender_id}/status",
        json={
            "new_status": "active",
            "changed_by": "publisher-1",
            "reason": "Tender published",
        },
    )
    assert response.status_code == 200

    history_response = await client.get(
        f"{TENDERS_URL}/{tender_id}/history"
    )
    assert history_response.status_code == 200
    return history_response.json()[0]


async def test_enqueue_analysis_sends_json_compatible_input(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tender = await create_tender(client)
    history = await create_status_history(client, tender["id"])
    captured_payload: dict[str, object] = {}

    def fake_delay(payload: dict[str, object]) -> SimpleNamespace:
        captured_payload.update(payload)
        return SimpleNamespace(id="task-123")

    monkeypatch.setattr(
        analysis_router.analyze_status_change,
        "delay",
        fake_delay,
    )

    response = await client.post(
        f"{TENDERS_URL}/{tender['id']}/history/{history['id']}"
        "/ai-analysis"
    )

    assert response.status_code == 202
    assert response.json() == {"task_id": "task-123", "status": "queued"}
    assert captured_payload == {
        "title": tender["title"],
        "description": tender["description"],
        "old_status": "draft",
        "new_status": "active",
        "reason": "Tender published",
    }
    assert all(
        isinstance(value, str) for value in captured_payload.values()
    )


async def test_enqueue_analysis_returns_404_for_missing_tender(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        analysis_router.analyze_status_change,
        "delay",
        lambda payload: pytest.fail(f"Unexpected enqueue: {payload}"),
    )

    response = await client.post(
        f"{TENDERS_URL}/999/history/1/ai-analysis"
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Tender not found"}


async def test_enqueue_analysis_returns_404_for_missing_history(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tender = await create_tender(client)
    monkeypatch.setattr(
        analysis_router.analyze_status_change,
        "delay",
        lambda payload: pytest.fail(f"Unexpected enqueue: {payload}"),
    )

    response = await client.post(
        f"{TENDERS_URL}/{tender['id']}/history/999/ai-analysis"
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Tender status history not found"}


async def test_enqueue_analysis_hides_history_ownership(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_tender = await create_tender(client, title="First")
    second_tender = await create_tender(client, title="Second")
    history = await create_status_history(client, first_tender["id"])
    monkeypatch.setattr(
        analysis_router.analyze_status_change,
        "delay",
        lambda payload: pytest.fail(f"Unexpected enqueue: {payload}"),
    )

    response = await client.post(
        f"{TENDERS_URL}/{second_tender['id']}/history/{history['id']}"
        "/ai-analysis"
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Tender status history not found"}


async def test_enqueue_analysis_returns_503_for_broker_failure(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tender = await create_tender(client)
    history = await create_status_history(client, tender["id"])

    def fail_enqueue(payload: dict[str, object]) -> None:
        raise OperationalError("redis://private-host:6379 unavailable")

    monkeypatch.setattr(
        analysis_router.analyze_status_change,
        "delay",
        fail_enqueue,
    )

    response = await client.post(
        f"{TENDERS_URL}/{tender['id']}/history/{history['id']}"
        "/ai-analysis"
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "AI analysis service is unavailable"
    }
    assert "private-host" not in response.text


@pytest.mark.parametrize(
    ("celery_state", "public_status", "public_error"),
    [
        ("PENDING", "pending", None),
        ("STARTED", "processing", None),
        ("RETRY", "processing", None),
        ("FAILURE", "failed", "AI analysis failed"),
        ("REVOKED", "failed", "AI analysis failed"),
        ("CUSTOM", "pending", None),
    ],
)
async def test_get_analysis_maps_celery_states(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    celery_state: str,
    public_status: str,
    public_error: str | None,
) -> None:
    monkeypatch.setattr(
        analysis_router.celery_app,
        "AsyncResult",
        lambda task_id: SimpleNamespace(
            state=celery_state,
            result=RuntimeError("provider secret"),
        ),
    )

    response = await client.get("/api/v1/ai-analysis/task-123")

    assert response.status_code == 200
    assert response.json() == {
        "task_id": "task-123",
        "status": public_status,
        "result": None,
        "error": public_error,
    }
    assert "provider secret" not in response.text


async def test_get_analysis_returns_validated_success_result(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend_result = {
        "summary": "The transition is documented.",
        "observations": ["A reason was supplied."],
        "recommendations": ["Review the outcome later."],
    }
    monkeypatch.setattr(
        analysis_router.celery_app,
        "AsyncResult",
        lambda task_id: SimpleNamespace(
            state="SUCCESS",
            result=backend_result,
        ),
    )

    response = await client.get("/api/v1/ai-analysis/task-123")

    assert response.status_code == 200
    assert response.json() == {
        "task_id": "task-123",
        "status": "completed",
        "result": backend_result,
        "error": None,
    }


async def test_get_analysis_rejects_invalid_success_result(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        analysis_router.celery_app,
        "AsyncResult",
        lambda task_id: SimpleNamespace(
            state="SUCCESS",
            result={"unexpected": "data"},
        ),
    )

    response = await client.get("/api/v1/ai-analysis/task-123")

    assert response.status_code == 200
    assert response.json() == {
        "task_id": "task-123",
        "status": "failed",
        "result": None,
        "error": "AI analysis failed",
    }
