from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Tender
from app.schemas import (
    StatusHistoryRead,
    TenderCreate,
    TenderRead,
    TenderStatusUpdate,
)
from app.services import (
    TenderNotFoundError,
    TenderStatusConflictError,
    get_tender_history,
    update_tender_status,
)

router = APIRouter(prefix="/tenders", tags=["tenders"])


@router.post("", response_model=TenderRead, status_code=status.HTTP_201_CREATED)
async def create_tender(
    tender_data: TenderCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Tender:
    tender = Tender(**tender_data.model_dump())
    session.add(tender)
    await session.commit()
    await session.refresh(tender)
    return tender


@router.get("/{id}", response_model=TenderRead, status_code=status.HTTP_200_OK)
async def get_tender(
    id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Tender:
    tender = await session.get(Tender, id)
    if tender is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tender not found",
        )
    return tender


@router.get(
    "/{id}/history",
    response_model=list[StatusHistoryRead],
    status_code=status.HTTP_200_OK,
)
async def read_tender_history(
    id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[StatusHistoryRead]:
    try:
        history = await get_tender_history(session, id)
    except TenderNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tender not found",
        ) from error
    return [StatusHistoryRead.model_validate(entry) for entry in history]


@router.patch(
    "/{id}/status",
    response_model=TenderRead,
    status_code=status.HTTP_200_OK,
)
async def change_tender_status(
    id: int,
    status_data: TenderStatusUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Tender:
    try:
        return await update_tender_status(session, id, status_data)
    except TenderNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tender not found",
        ) from error
    except TenderStatusConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tender already has the requested status",
        ) from error
