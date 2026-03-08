from aiogram import Router

from src.middlewares.auth import AuthMiddleware


router = Router()
router.message.middleware(AuthMiddleware())
