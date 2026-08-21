from pydantic import BaseModel

from app.models import TenderStatus


class StatusChangeAnalysisInput(BaseModel):
    title: str
    description: str
    old_status: TenderStatus
    new_status: TenderStatus
    reason: str


class StatusChangeAnalysis(BaseModel):
    summary: str
    observations: list[str]
    recommendations: list[str]
