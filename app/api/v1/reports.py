"""Report API endpoints for correction analysis."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.report import ReportRead
from app.services.analysis_service import get_report, trigger_analysis

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/conversations/{conversation_id}/analyze", status_code=202)
async def analyze_conversation(
    conversation_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """Trigger async CrewAI analysis for a completed conversation."""
    background_tasks.add_task(trigger_analysis, conversation_id, current_user.id)
    return {"status": "processing", "conversation_id": str(conversation_id)}


@router.get("/{conversation_id}", response_model=ReportRead | None)
async def get_conversation_report(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Get the correction report for a conversation.

    Returns 200 if completed, 202 if still processing, 404 if not found.
    """
    report = await get_report(conversation_id, session)

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if report.status == "processing":
        raise HTTPException(
            status_code=202,
            detail="Report is still being generated",
            headers={"Retry-After": "3"},
        )

    if report.status == "failed":
        raise HTTPException(status_code=500, detail="Report generation failed")

    return ReportRead(
        id=report.id,
        conversation_id=report.conversation_id,
        corrections=report.corrections,
        new_expressions=report.new_expressions,
        fluency_score=report.fluency_score,
        summary=report.summary,
        status=report.status,
        created_at=report.created_at,
        completed_at=report.completed_at,
    )
