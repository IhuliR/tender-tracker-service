from typing import Literal

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


class AnalysisTaskAccepted(BaseModel):
    task_id: str
    status: Literal["queued"] = "queued"


class AnalysisTaskStatus(BaseModel):
    task_id: str
    status: Literal["pending", "processing", "completed", "failed"]
    result: StatusChangeAnalysis | None = None
    error: str | None = None
