import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.persona import Persona
from app.models.scenario import Scenario
from app.services.persona_service import build_system_prompt


async def create_conversation(
    user_id: uuid.UUID,
    persona_id: uuid.UUID,
    scenario_id: uuid.UUID,
    session: AsyncSession,
) -> tuple[Conversation, Message]:
    """Create a new conversation and generate the AI's first greeting message."""
    from app.core.openai_client import chat_stream

    # Fetch persona and scenario
    persona_result = await session.execute(select(Persona).where(Persona.id == persona_id))
    persona = persona_result.scalar_one_or_none()
    scenario_result = await session.execute(select(Scenario).where(Scenario.id == scenario_id))
    scenario = scenario_result.scalar_one_or_none()

    if not persona or not scenario:
        raise ValueError("Persona or scenario not found")

    conversation = Conversation(
        user_id=user_id,
        persona_id=persona_id,
        scenario_id=scenario_id,
    )
    session.add(conversation)
    await session.flush()

    # Generate AI first message (non-streaming for the greeting)
    system_prompt = build_system_prompt(persona, scenario)
    greeting_parts = []
    async for chunk in chat_stream(
        system_prompt=system_prompt,
        messages=[{"role": "user", "content": "(The learner just arrived. Greet them in character and start the conversation.)"}],
        max_tokens=150,
    ):
        greeting_parts.append(chunk)
    greeting = "".join(greeting_parts)

    # Use intro_line as fallback if API fails
    if not greeting and persona.intro_line:
        greeting = persona.intro_line

    ai_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=greeting,
    )
    session.add(ai_message)
    conversation.message_count = 1
    await session.commit()
    await session.refresh(conversation)
    await session.refresh(ai_message)
    return conversation, ai_message


async def get_conversations(user_id: uuid.UUID, session: AsyncSession, limit: int = 20, offset: int = 0) -> list[Conversation]:
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_messages(conversation_id: uuid.UUID, session: AsyncSession) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def save_user_message(conversation_id: uuid.UUID, content: str, session: AsyncSession) -> Message:
    msg = Message(conversation_id=conversation_id, role="user", content=content)
    session.add(msg)

    # Update message count
    conv_result = await session.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = conv_result.scalar_one()
    conv.message_count += 1
    await session.commit()
    await session.refresh(msg)
    return msg


async def save_ai_message(conversation_id: uuid.UUID, content: str, session: AsyncSession) -> Message:
    msg = Message(conversation_id=conversation_id, role="assistant", content=content)
    session.add(msg)

    conv_result = await session.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = conv_result.scalar_one()
    conv.message_count += 1
    await session.commit()
    await session.refresh(msg)
    return msg


async def end_conversation(conversation_id: uuid.UUID, session: AsyncSession) -> Conversation:
    conv_result = await session.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = conv_result.scalar_one()
    conv.ended_at = datetime.utcnow()
    if conv.started_at:
        conv.duration_sec = int((conv.ended_at - conv.started_at).total_seconds())
    await session.commit()
    await session.refresh(conv)
    return conv


async def get_conversation_context(conversation_id: uuid.UUID, session: AsyncSession) -> tuple[Persona, Scenario, list[dict]]:
    """Get persona, scenario, and message history for a conversation."""
    conv_result = await session.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = conv_result.scalar_one()

    persona_result = await session.execute(select(Persona).where(Persona.id == conv.persona_id))
    persona = persona_result.scalar_one()

    scenario_result = await session.execute(select(Scenario).where(Scenario.id == conv.scenario_id))
    scenario = scenario_result.scalar_one()

    messages = await get_messages(conversation_id, session)
    history = [{"role": m.role, "content": m.content} for m in messages]

    return persona, scenario, history
