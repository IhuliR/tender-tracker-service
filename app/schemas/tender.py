from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import TenderStatus


class TenderCreate(BaseModel):
    title: str
    description: str


class TenderStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_status: TenderStatus
    changed_by: str
    reason: str


class TenderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    status: TenderStatus
    created_at: datetime
    updated_at: datetime


class StatusHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tender_id: int
    old_status: TenderStatus
    new_status: TenderStatus
    changed_by: str
    reason: str
    changed_at: datetime
