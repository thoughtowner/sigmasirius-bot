from aiogram import Router

from src.middlewares.resident import ResidentMiddleware


router = Router()
router.message.middleware(ResidentMiddleware())
