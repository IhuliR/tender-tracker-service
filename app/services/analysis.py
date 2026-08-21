from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tender, TenderStatusHistory
from app.schemas import StatusChangeAnalysisInput
from app.services.tenders import TenderNotFoundError


class TenderHistoryNotFoundError(Exception):
    pass


async def build_status_change_analysis_input(
    session: AsyncSession,
    tender_id: int,
    history_id: int,
) -> StatusChangeAnalysisInput:
    tender = await session.get(Tender, tender_id)
    if tender is None:
        raise TenderNotFoundError

    history = await session.get(TenderStatusHistory, history_id)
    if history is None or history.tender_id != tender_id:
        raise TenderHistoryNotFoundError

    return StatusChangeAnalysisInput(
        title=tender.title,
        description=tender.description,
        old_status=history.old_status,
        new_status=history.new_status,
        reason=history.reason,
    )
