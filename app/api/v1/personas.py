import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.persona import PersonaDetailRead, PersonaRead, ScenarioRead
from app.services import persona_service

router = APIRouter(prefix="/personas", tags=["personas"])


@router.get("", response_model=list[PersonaRead])
async def list_personas(
    language: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    personas = await persona_service.list_personas(language, session)
    return personas


@router.get("/{persona_id}", response_model=PersonaDetailRead)
async def get_persona(
    persona_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    persona = await persona_service.get_persona(persona_id, session)
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")
    scenarios = await persona_service.list_scenarios(persona_id, session)
    result = PersonaDetailRead.model_validate(persona, from_attributes=True)
    result.scenarios = [ScenarioRead.model_validate(s, from_attributes=True) for s in scenarios]
    return result


@router.get("/{persona_id}/scenarios", response_model=list[ScenarioRead])
async def list_scenarios(
    persona_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    scenarios = await persona_service.list_scenarios(persona_id, session)
    return scenarios
