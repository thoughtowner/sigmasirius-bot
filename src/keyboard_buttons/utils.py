from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton

# Note: previously used ReplyKeyboardMarkup. Switch to inline keyboards so the
# cancel button is an inline button (callback 'cancel_state').
OK = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Ok', callback_data='ok')]])

def create_single_row_buttons(buttons: list[KeyboardButton]) -> InlineKeyboardMarkup:
    # convert provided KeyboardButton list (text-only) to inline buttons
    row = [InlineKeyboardButton(text=b.text, callback_data=b.text) for b in buttons]
    # append a cancel inline button row so users can cancel from any question
    cancel_btn = InlineKeyboardButton(text='Отменить', callback_data='cancel_state')
    return InlineKeyboardMarkup(inline_keyboard=[row, [cancel_btn]])

def create_single_button(text: str) -> InlineKeyboardMarkup:
    btn = InlineKeyboardButton(text=text, callback_data=text)
    cancel_btn = InlineKeyboardButton(text='Отменить', callback_data='cancel_state')
    return InlineKeyboardMarkup(inline_keyboard=[[btn], [cancel_btn]])
