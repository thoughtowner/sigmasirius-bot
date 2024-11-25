from fastapi import APIRouter

from src.api.v1.auth.router import router as auth_router

router = APIRouter()
router.include_router(auth_router)