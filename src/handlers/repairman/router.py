from aiogram import Router

from src.middlewares.repairman import RepairmanMiddleware


router = Router()
router.message.middleware(RepairmanMiddleware())
router.callback_query.middleware(RepairmanMiddleware())
