from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Tender, TenderStatus, TenderStatusHistory
from app.schemas import TenderStatusUpdate
from app.services import update_tender_status

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


async def change_status(
    client: AsyncClient,
    tender_id: int,
    *,
    new_status: str,
    changed_by: str,
    reason: str,
) -> Response:
    return await client.patch(
        f"{TENDERS_URL}/{tender_id}/status",
        json={
            "new_status": new_status,
            "changed_by": changed_by,
            "reason": reason,
        },
    )


async def test_create_tender(client: AsyncClient) -> None:
    response = await client.post(
        TENDERS_URL,
        json={
            "title": "School renovation",
            "description": "Renovation of classrooms and common areas",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert set(data) == {
        "id",
        "title",
        "description",
        "status",
        "created_at",
        "updated_at",
    }
    assert data["id"] == 1
    assert data["title"] == "School renovation"
    assert data["description"] == "Renovation of classrooms and common areas"
    assert data["status"] == "draft"
    assert data["created_at"]
    assert data["updated_at"]


async def test_get_created_tender(client: AsyncClient) -> None:
    created = await create_tender(client)

    response = await client.get(f"{TENDERS_URL}/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


async def test_get_nonexistent_tender_returns_404(client: AsyncClient) -> None:
    response = await client.get(f"{TENDERS_URL}/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Tender not found"}


async def test_update_status_creates_history(client: AsyncClient) -> None:
    created = await create_tender(client)

    response = await change_status(
        client,
        created["id"],
        new_status="active",
        changed_by="publisher-1",
        reason="Tender published",
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["id"] == created["id"]
    assert updated["title"] == created["title"]
    assert updated["description"] == created["description"]
    assert updated["status"] == "active"

    history_response = await client.get(
        f"{TENDERS_URL}/{created['id']}/history"
    )
    assert history_response.status_code == 200
    history = history_response.json()
    assert len(history) == 1
    assert history[0]["tender_id"] == created["id"]
    assert history[0]["old_status"] == "draft"
    assert history[0]["new_status"] == "active"
    assert history[0]["changed_by"] == "publisher-1"
    assert history[0]["reason"] == "Tender published"
    assert history[0]["changed_at"]


async def test_history_keeps_business_order(client: AsyncClient) -> None:
    created = await create_tender(client)

    first_response = await change_status(
        client,
        created["id"],
        new_status="active",
        changed_by="publisher-1",
        reason="Tender published",
    )
    second_response = await change_status(
        client,
        created["id"],
        new_status="won",
        changed_by="manager-2",
        reason="Contract awarded",
    )
    assert first_response.status_code == 200
    assert second_response.status_code == 200

    response = await client.get(f"{TENDERS_URL}/{created['id']}/history")

    assert response.status_code == 200
    history = response.json()
    assert len(history) == 2
    assert [entry["old_status"] for entry in history] == ["draft", "active"]
    assert [entry["new_status"] for entry in history] == ["active", "won"]
    assert [entry["changed_by"] for entry in history] == [
        "publisher-1",
        "manager-2",
    ]
    assert [entry["reason"] for entry in history] == [
        "Tender published",
        "Contract awarded",
    ]


async def test_same_status_conflict_preserves_state(client: AsyncClient) -> None:
    created = await create_tender(client)

    response = await change_status(
        client,
        created["id"],
        new_status="draft",
        changed_by="publisher-1",
        reason="Duplicate status",
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Tender already has the requested status"
    }

    tender_response = await client.get(f"{TENDERS_URL}/{created['id']}")
    history_response = await client.get(
        f"{TENDERS_URL}/{created['id']}/history"
    )
    assert tender_response.status_code == 200
    assert tender_response.json()["status"] == "draft"
    assert history_response.status_code == 200
    assert history_response.json() == []


async def test_new_tender_has_empty_history(client: AsyncClient) -> None:
    created = await create_tender(client)

    response = await client.get(f"{TENDERS_URL}/{created['id']}/history")

    assert response.status_code == 200
    assert response.json() == []


async def test_nonexistent_tender_history_returns_404(
    client: AsyncClient,
) -> None:
    response = await client.get(f"{TENDERS_URL}/999/history")

    assert response.status_code == 404
    assert response.json() == {"detail": "Tender not found"}


async def test_invalid_status_returns_422_without_changes(
    client: AsyncClient,
) -> None:
    created = await create_tender(client)

    response = await change_status(
        client,
        created["id"],
        new_status="in_progress",
        changed_by="publisher-1",
        reason="Invalid status",
    )

    assert response.status_code == 422

    tender_response = await client.get(f"{TENDERS_URL}/{created['id']}")
    history_response = await client.get(
        f"{TENDERS_URL}/{created['id']}/history"
    )
    assert tender_response.status_code == 200
    assert tender_response.json()["status"] == "draft"
    assert history_response.status_code == 200
    assert history_response.json() == []


async def test_status_and_history_are_rolled_back_on_persistence_failure(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        tender = Tender(
            title="Bridge inspection",
            description="Annual structural inspection services",
        )
        session.add(tender)
        await session.commit()
        tender_id = tender.id

        executed_statements: list[str] = []

        def fail_history_insert(
            connection: Any,
            cursor: Any,
            statement: str,
            parameters: Any,
            context: Any,
            executemany: bool,
        ) -> None:
            normalized_statement = statement.strip().upper()
            if normalized_statement.startswith("UPDATE TENDERS"):
                executed_statements.append("tender update")
            if normalized_statement.startswith(
                "INSERT INTO TENDER_STATUS_HISTORY"
            ):
                executed_statements.append("history insert")
                raise RuntimeError("simulated history persistence failure")

        bind = session.get_bind()
        event.listen(bind, "before_cursor_execute", fail_history_insert)
        try:
            with pytest.raises(
                RuntimeError,
                match="simulated history persistence failure",
            ):
                await update_tender_status(
                    session,
                    tender_id,
                    TenderStatusUpdate(
                        new_status=TenderStatus.ACTIVE,
                        changed_by="publisher-1",
                        reason="Tender published",
                    ),
                )
        finally:
            event.remove(bind, "before_cursor_execute", fail_history_insert)

    assert executed_statements == ["tender update", "history insert"]

    async with session_factory() as verification_session:
        persisted_tender = await verification_session.get(Tender, tender_id)
        history_result = await verification_session.execute(
            select(TenderStatusHistory).where(
                TenderStatusHistory.tender_id == tender_id
            )
        )

        assert persisted_tender is not None
        assert persisted_tender.status == TenderStatus.DRAFT
        assert history_result.scalars().all() == []
