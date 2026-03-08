from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, SignupRequest, TokenResponse
from app.schemas.user import UserRead
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def user_to_dict(user) -> dict:
    return UserRead.model_validate(user, from_attributes=True).model_dump(mode="json")


@router.post("/signup", response_model=TokenResponse)
async def signup(body: SignupRequest, session: AsyncSession = Depends(get_session)):
    user, access, refresh = await auth_service.signup(body.email, body.password, session)
    return TokenResponse(access_token=access, refresh_token=refresh, user=user_to_dict(user))


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)):
    user, access, refresh = await auth_service.login(body.email, body.password, session)
    return TokenResponse(access_token=access, refresh_token=refresh, user=user_to_dict(user))


@router.post("/refresh")
async def refresh(body: RefreshRequest, session: AsyncSession = Depends(get_session)):
    access, refresh = await auth_service.refresh_tokens(body.refresh_token, session)
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}


@router.post("/logout")
async def logout():
    return {"detail": "Logged out"}
