from aiogram.types import KeyboardButton
from .utils import create_single_row_buttons
from .texts import STUDY_GROUPS, BUILDINGS, ENTRANCES, ROOMS_BY_FLOOR


STUDY_GROUPS_ROW_BUTTONS = create_single_row_buttons(
    [KeyboardButton(text=study_group) for study_group in STUDY_GROUPS]
)

BUILDINGS_ROW_BUTTONS = create_single_row_buttons(
    [KeyboardButton(text=building) for building in BUILDINGS]
)

ENTRANCES_ROW_BUTTONS = create_single_row_buttons(
    [KeyboardButton(text=entrance) for entrance in ENTRANCES]
)

FLOORS_ROW_BUTTONS = create_single_row_buttons(
    [KeyboardButton(text=floor) for floor in ROOMS_BY_FLOOR.keys()]
)

ROOMS_BY_FLOOR_ROW_BUTTONS = {
    floor: create_single_row_buttons([KeyboardButton(text=room) for room in rooms])
    for floor, rooms in ROOMS_BY_FLOOR.items()
}
