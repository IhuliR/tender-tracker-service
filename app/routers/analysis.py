from typing import Annotated

from celery.exceptions import BackendError
from fastapi import APIRouter, Depends, HTTPException, status
from kombu.exceptions import OperationalError
from pydantic import ValidationError
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import celery_app
from app.db import get_session
from app.schemas import (
    AnalysisTaskAccepted,
    AnalysisTaskStatus,
    StatusChangeAnalysis,
)
from app.services import (
    TenderHistoryNotFoundError,
    TenderNotFoundError,
    build_status_change_analysis_input,
)
from app.tasks.analysis import analyze_status_change

router = APIRouter(tags=["ai-analysis"])

PUBLIC_TASK_STATES = {
    "PENDING": "pending",
    "STARTED": "processing",
    "RETRY": "processing",
    "SUCCESS": "completed",
    "FAILURE": "failed",
    "REVOKED": "failed",
}


@router.post(
    "/tenders/{tender_id}/history/{history_id}/ai-analysis",
    response_model=AnalysisTaskAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        404: {"description": "Tender or status history not found"},
        503: {"description": "AI analysis service is unavailable"},
    },
)
async def enqueue_status_change_analysis(
    tender_id: int,
    history_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AnalysisTaskAccepted:
    try:
        analysis_input = await build_status_change_analysis_input(
            session,
            tender_id,
            history_id,
        )
    except TenderNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tender not found",
        ) from error
    except TenderHistoryNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tender status history not found",
        ) from error

    try:
        task = analyze_status_change.delay(
            analysis_input.model_dump(mode="json")
        )
    except OperationalError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI analysis service is unavailable",
        ) from error

    return AnalysisTaskAccepted(task_id=task.id)


@router.get(
    "/ai-analysis/{task_id}",
    response_model=AnalysisTaskStatus,
    status_code=status.HTTP_200_OK,
)
def get_analysis_task(task_id: str) -> AnalysisTaskStatus:
    try:
        task = celery_app.AsyncResult(task_id)
        task_state = task.state
    except (BackendError, RedisError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI analysis service is unavailable",
        ) from error

    public_state = PUBLIC_TASK_STATES.get(task_state, "pending")
    if task_state == "SUCCESS":
        try:
            result = StatusChangeAnalysis.model_validate(task.result)
        except ValidationError:
            return AnalysisTaskStatus(
                task_id=task_id,
                status="failed",
                error="AI analysis failed",
            )
        return AnalysisTaskStatus(
            task_id=task_id,
            status="completed",
            result=result,
        )

    if public_state == "failed":
        return AnalysisTaskStatus(
            task_id=task_id,
            status="failed",
            error="AI analysis failed",
        )

    return AnalysisTaskStatus(task_id=task_id, status=public_state)
