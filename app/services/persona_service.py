import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.persona import Persona
from app.models.scenario import Scenario


async def list_personas(language: str | None, session: AsyncSession) -> list[Persona]:
    stmt = select(Persona)
    if language:
        stmt = stmt.where(Persona.language == language)
    stmt = stmt.order_by(Persona.created_at)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_persona(persona_id: uuid.UUID, session: AsyncSession) -> Persona | None:
    result = await session.execute(select(Persona).where(Persona.id == persona_id))
    return result.scalar_one_or_none()


async def list_scenarios(persona_id: uuid.UUID | None, session: AsyncSession) -> list[Scenario]:
    stmt = select(Scenario)
    if persona_id:
        stmt = stmt.where(Scenario.persona_id == persona_id)
    stmt = stmt.order_by(Scenario.difficulty, Scenario.created_at)
    result = await session.execute(stmt)
    return list(result.scalars().all())


def build_system_prompt(persona: Persona, scenario: Scenario, memory_context: list[str] | None = None) -> str:
    parts = [
        f"You are {persona.name}, a {persona.age}-year-old {persona.job}.",
        f"Personality: {persona.personality}",
        f"Speech style: {persona.speech_style}",
        "",
        f"Current scenario: {scenario.title}",
        f"Location: {scenario.location}",
        f"Situation: {scenario.situation}",
        f"Goal for the learner: {scenario.goal}",
        "",
        "Instructions:",
        f"- Always respond in {persona.language} (the language you speak).",
        "- Keep responses conversational and natural, 1-3 sentences.",
        "- Match the difficulty level to the learner's ability.",
        "- Stay in character at all times.",
        "- If the learner makes a language mistake, gently correct it within the conversation.",
    ]
    if persona.personality_prompt:
        parts.insert(0, persona.personality_prompt)
        parts.insert(1, "")
    if memory_context:
        parts.append("")
        parts.append("Previous context with this learner:")
        parts.extend(f"- {m}" for m in memory_context)
    return "\n".join(parts)
