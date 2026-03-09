import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.database import get_session
from app.core.openai_client import chat_stream
from app.core.security import get_current_user
from app.models.persona import Persona
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
        is_benchmark=body.is_benchmark,
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

    # Get conversation context + Phase 3 기억 컨텍스트
    persona, scenario, history = await chat_service.get_conversation_context(conversation_id, session)
    memory_context = None
    try:
        from app.services.memory_service import get_relevant_memories
        context_text = f"{scenario.title} {scenario.situation}"
        memories = await get_relevant_memories(
            user.id, persona.id, context_text, session
        )
        if memories:
            memory_context = [m.content for m in memories]
    except Exception:
        pass  # 기억 로드 실패해도 대화는 계속
    system_prompt = build_system_prompt(persona, scenario, memory_context=memory_context)

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


# Phase 3.5: 음성 메시지 — 오디오 수신 → STT 변환 → 기존 채팅 파이프라인
@router.post("/{conversation_id}/audio")
async def send_audio_message(
    conversation_id: uuid.UUID,
    audio: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    음성 메시지 전송: 오디오 → STT(Whisper) → 텍스트 → AI 스트리밍 응답.

    1. 오디오 파일 수신 (webm/opus)
    2. Whisper API로 텍스트 변환
    3. 변환된 텍스트를 유저 메시지로 저장
    4. 기존 채팅 파이프라인과 동일한 SSE 스트리밍 응답

    SSE 이벤트:
    - {"type": "transcription", "text": "..."} — STT 변환 결과 (프론트에서 말풍선 표시)
    - {"type": "chunk", "text": "..."} — AI 응답 청크
    - {"type": "done", "full_text": "..."} — AI 응답 완료
    """
    from app.services.stt_service import transcribe

    # 1. 오디오 파일 읽기
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty audio file")

    # 2. 대화의 페르소나 언어 확인 (STT 언어 힌트)
    from app.models.conversation import Conversation
    conv_check = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = conv_check.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    persona_result = await session.execute(select(Persona).where(Persona.id == conv.persona_id))
    persona = persona_result.scalar_one_or_none()
    stt_language = persona.language if persona else "en"

    # 3. Whisper STT 변환
    transcribed_text = await transcribe(audio_bytes, language=stt_language)
    if not transcribed_text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not transcribe audio")

    # 4. 유저 메시지 저장 (변환된 텍스트)
    await chat_service.save_user_message(conversation_id, transcribed_text, session)

    # 5. 대화 컨텍스트 + 기억 로드 (send_message와 동일한 로직)
    persona_obj, scenario, history = await chat_service.get_conversation_context(conversation_id, session)
    memory_context = None
    try:
        from app.services.memory_service import get_relevant_memories
        context_text = f"{scenario.title} {scenario.situation}"
        memories = await get_relevant_memories(
            user.id, persona_obj.id, context_text, session
        )
        if memories:
            memory_context = [m.content for m in memories]
    except Exception:
        pass  # 기억 로드 실패해도 대화는 계속
    system_prompt = build_system_prompt(persona_obj, scenario, memory_context=memory_context)

    # 6. SSE 스트리밍 응답 (transcription 이벤트 추가)
    async def event_stream():
        # 먼저 STT 결과를 프론트에 전달 (말풍선 표시용)
        transcription_data = json.dumps(
            {"type": "transcription", "text": transcribed_text}, ensure_ascii=False
        )
        yield f"data: {transcription_data}\n\n"

        # AI 응답 스트리밍 (기존과 동일)
        full_text = []
        try:
            async for chunk in chat_stream(system_prompt=system_prompt, messages=history):
                full_text.append(chunk)
                data = json.dumps({"type": "chunk", "text": chunk}, ensure_ascii=False)
                yield f"data: {data}\n\n"

            complete = "".join(full_text)
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
