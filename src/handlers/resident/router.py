from aiogram import Router

from src.middlewares.auth import AuthMiddleware
from src.middlewares.resident import ResidentMiddleware


router = Router()
router.message.middleware(AuthMiddleware())
router.message.middleware(ResidentMiddleware())
