from aiogram import Router

from src.middlewares.auth import AuthMiddleware
from src.middlewares.repairman import RepairmanMiddleware


router = Router()
router.message.middleware(AuthMiddleware())
router.message.middleware(RepairmanMiddleware())
