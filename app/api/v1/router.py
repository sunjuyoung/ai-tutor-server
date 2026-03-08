from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.health import router as health_router
from app.api.v1.personas import router as personas_router
from app.api.v1.users import router as users_router

v1_router = APIRouter()
v1_router.include_router(health_router, tags=["health"])
v1_router.include_router(auth_router)
v1_router.include_router(users_router)
v1_router.include_router(personas_router)
v1_router.include_router(chat_router)
