from aiogram.types import KeyboardButton
from .utils import create_single_row_buttons
from .texts import BUILDINGS, ENTRANCES, ROOM_NUMBERS_BY_FLOOR


BUILDINGS_ROW_BUTTONS = create_single_row_buttons(
    [KeyboardButton(text=building) for building in BUILDINGS]
)

ENTRANCES_ROW_BUTTONS = create_single_row_buttons(
    [KeyboardButton(text=entrance) for entrance in ENTRANCES]
)

FLOORS_ROW_BUTTONS = create_single_row_buttons(
    [KeyboardButton(text=floor) for floor in ROOM_NUMBERS_BY_FLOOR.keys()]
)

ROOM_NUMBERS_BY_FLOOR_ROW_BUTTONS = {
    floor: create_single_row_buttons([KeyboardButton(text=room) for room in rooms])
    for floor, rooms in ROOM_NUMBERS_BY_FLOOR.items()
}
