from aiogram import Router

from src.middlewares.resident import ResidentMiddleware
from src.middlewares.auth import AuthMiddleware


router = Router()
router.message.middleware(ResidentMiddleware())
router.message.middleware(AuthMiddleware())
