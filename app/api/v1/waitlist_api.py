"""
Waitlist API — 베타 대기 리스트 + 텍스트 데모

Phase 3 (W15):
- POST /waitlist: 이메일 등록 + 레퍼럴 코드 발급
- GET /waitlist/status: 전체 대기자 수 (공개)
- POST /waitlist/demo: 텍스트 미니 데모 (3턴, 비로그인)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.waitlist import (
    WaitlistRegisterRequest,
    WaitlistRegisterResponse,
    WaitlistStatusResponse,
)
from app.services import waitlist_service

router = APIRouter(prefix="/waitlist", tags=["waitlist"])


@router.post("", response_model=WaitlistRegisterResponse)
async def register_waitlist(
    body: WaitlistRegisterRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Waitlist 등록 — 이메일 + 관심 언어/상황 수집.

    로그인 불필요. 레퍼럴 코드 발급 + 대기 순번 반환.
    """
    try:
        result = await waitlist_service.register(
            email=body.email,
            interested_languages=body.interested_languages,
            interested_situation=body.interested_situation,
            referred_by=body.referred_by,
            session=session,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get("/status", response_model=WaitlistStatusResponse)
async def get_waitlist_status(
    session: AsyncSession = Depends(get_session),
):
    """
    전체 대기자 수 조회 (공개 API, 인증 불필요).

    랜딩 페이지 "현재 N명이 대기 중이에요" 표시에 사용.
    """
    total = await waitlist_service.get_total_count(session)
    return {"total_count": total}


@router.post("/demo")
async def demo_chat(
    body: dict,
):
    """
    텍스트 미니 데모 — 3턴 제한 대화 (비로그인).

    Waitlist 등록 직후 체험용. 프론트엔드에서 직접 OpenAI 호출하는
    방식으로 전환 가능하나, CORS 보안을 위해 백엔드 프록시로 구현.

    Request body:
        { "message": "...", "turn": 1, "language": "ja", "history": [...] }

    Returns:
        { "reply": "...", "turn": N, "hint": "...", "is_last": bool }
    """
    from app.core.openai_client import get_openai_client

    message = body.get("message", "")
    turn = body.get("turn", 1)
    language = body.get("language", "ja")
    history = body.get("history", [])

    # 3턴 제한
    max_turns = 3
    is_last = turn >= max_turns

    # 데모용 시스템 프롬프트
    if language == "en":
        system_prompt = (
            "You are Emma, a friendly 24-year-old café barista in LA. "
            "Keep responses short (1-2 sentences), conversational, and encouraging. "
            "If the user makes a grammar mistake, gently correct it."
        )
        hint_prompt = "Provide a short English hint phrase the user could say next."
    else:
        system_prompt = (
            "あなたは유이(ユイ)、東京の大学生(22歳)です。"
            "친근하고 밝은 성격으로, 짧게(1~2문장) 자연스럽게 대화하세요. "
            "상대가 문법 실수를 하면 부드럽게 교정해주세요."
        )
        hint_prompt = "ユーザーが次に言えそうな日本語のヒントフレーズを1つ提供してください。"

    # 대화 히스토리 구성
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    try:
        client = get_openai_client()

        # AI 응답 생성
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.8,
            max_tokens=150,
        )
        reply = response.choices[0].message.content

        # 힌트 생성
        hint_response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": hint_prompt},
                {"role": "user", "content": f"Previous AI message: {reply}"},
            ],
            temperature=0.7,
            max_tokens=50,
        )
        hint = hint_response.choices[0].message.content

        return {
            "reply": reply,
            "turn": turn,
            "hint": hint,
            "is_last": is_last,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"데모 대화 생성 실패: {str(e)}",
        )
