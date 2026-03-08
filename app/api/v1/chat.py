import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.openai_client import chat_stream
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.chat import ConversationCreate, ConversationRead, MessageRead, SendMessageRequest
from app.services import chat_service
from app.services.persona_service import build_system_prompt

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationRead)
async def create_conversation(
    body: ConversationCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    conversation, first_message = await chat_service.create_conversation(
        user_id=user.id,
        persona_id=body.persona_id,
        scenario_id=body.scenario_id,
        session=session,
    )
    return conversation


@router.get("", response_model=list[ConversationRead])
async def list_conversations(
    limit: int = 20,
    offset: int = 0,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await chat_service.get_conversations(user.id, session, limit, offset)


@router.get("/{conversation_id}/messages", response_model=list[MessageRead])
async def get_messages(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await chat_service.get_messages(conversation_id, session)


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: uuid.UUID,
    body: SendMessageRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Send a user message and stream the AI response via SSE."""
    # Save user message
    await chat_service.save_user_message(conversation_id, body.content, session)

    # Get conversation context
    persona, scenario, history = await chat_service.get_conversation_context(conversation_id, session)
    system_prompt = build_system_prompt(persona, scenario)

    async def event_stream():
        full_text = []
        try:
            async for chunk in chat_stream(system_prompt=system_prompt, messages=history):
                full_text.append(chunk)
                data = json.dumps({"type": "chunk", "text": chunk}, ensure_ascii=False)
                yield f"data: {data}\n\n"

            complete = "".join(full_text)
            # Save AI message in a new session to avoid closed session issues
            from app.core.database import async_session_factory

            async with async_session_factory() as save_session:
                await chat_service.save_ai_message(conversation_id, complete, save_session)

            done_data = json.dumps({"type": "done", "full_text": complete}, ensure_ascii=False)
            yield f"data: {done_data}\n\n"
        except Exception as e:
            error_data = json.dumps({"type": "error", "message": str(e)})
            yield f"data: {error_data}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.patch("/{conversation_id}/end", response_model=ConversationRead)
async def end_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await chat_service.end_conversation(conversation_id, session)
