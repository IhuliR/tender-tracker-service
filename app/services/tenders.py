from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tender, TenderStatusHistory
from app.schemas import TenderStatusUpdate


class TenderNotFoundError(Exception):
    pass


class TenderStatusConflictError(Exception):
    pass


async def get_tender_history(
    session: AsyncSession,
    tender_id: int,
) -> list[TenderStatusHistory]:
    tender = await session.get(Tender, tender_id)
    if tender is None:
        raise TenderNotFoundError

    statement = (
        select(TenderStatusHistory)
        .where(TenderStatusHistory.tender_id == tender_id)
        .order_by(TenderStatusHistory.changed_at, TenderStatusHistory.id)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def update_tender_status(
    session: AsyncSession,
    tender_id: int,
    status_data: TenderStatusUpdate,
) -> Tender:
    async with session.begin():
        tender = await session.get(Tender, tender_id)
        if tender is None:
            raise TenderNotFoundError

        old_status = tender.status
        if status_data.new_status == old_status:
            raise TenderStatusConflictError

        tender.status = status_data.new_status
        session.add(
            TenderStatusHistory(
                tender_id=tender.id,
                old_status=old_status,
                new_status=status_data.new_status,
                changed_by=status_data.changed_by,
                reason=status_data.reason,
            )
        )
        await session.flush()
        await session.refresh(tender)

    return tender
