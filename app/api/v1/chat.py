import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.openai_client import chat_stream
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.chat import ConversationCreate, ConversationDetailRead, ConversationRead, MessageRead, SendMessageRequest
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


@router.get("/{conversation_id}", response_model=ConversationDetailRead)
async def get_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    대화 상세 조회 — 페르소나/시나리오 메타데이터 포함.

    '대화 이어하기' 기능에서 사용. 기존 대화의 메타데이터(페르소나 이름/이모지,
    시나리오 제목/이모지)를 반환하여 채팅 UI를 복원한다.
    소유권이 다르거나 존재하지 않으면 404.
    """
    detail = await chat_service.get_conversation_detail(conversation_id, user.id, session)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return detail


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    대화 삭제 — 메시지 + 분석결과 모두 Hard delete.

    마이페이지에서 대화 삭제 시 호출. 소유권 검증 후
    conversation + messages + learning_analytics를 모두 삭제한다.
    """
    deleted = await chat_service.delete_conversation(conversation_id, user.id, session)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return None


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


@router.patch("/{conversation_id}/end")
async def end_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    대화 종료 + 게이미피케이션 보상.

    Returns:
        {
            "conversation_id": str,
            "duration_sec": int,
            "xp": { earned_xp, total_xp, level, leveled_up, xp_to_next },
            "streak": { streak_days, streak_updated }
        }
    """
    return await chat_service.end_conversation(conversation_id, session)
