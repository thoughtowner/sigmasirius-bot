from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from .router import router


@router.callback_query()
async def callback_test(callback_query: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await callback_query.answer('Hello from callback!')  # as popup
    await callback_query.message.answer('Hello from callback!')  # as message
