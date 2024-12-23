from aiogram import Router

from src.middlewares.admin import AdminMiddleware


router = Router()
router.message.middleware(AdminMiddleware())
