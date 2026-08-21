from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Tender
from app.schemas import TenderCreate, TenderRead


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
