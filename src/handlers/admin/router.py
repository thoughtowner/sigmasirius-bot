from aiogram import Router

from src.middlewares.auth import AuthMiddleware
from src.middlewares.admin import AdminMiddleware


router = Router()
router.message.middleware(AuthMiddleware())
router.message.middleware(AdminMiddleware())
