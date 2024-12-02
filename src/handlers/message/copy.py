from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from .router import router
from ..states.auth import AuthGroup


@router.message()
async def echo_handler(message: Message, state: FSMContext) -> None:
    """
    Handler will forward receive a message back to the sender

    By default, message handler will handle all message types (like a text, photo, sticker etc.)
    """
    await state.set_state(AuthGroup.no_authorized)
    try:
        # Send a copy of the received message
        await message.send_copy(chat_id=message.chat.id)
    except TypeError:
        # But not all the types is supported to be copied so need to handle it
        await message.answer("Nice try!")
