from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram import F

from config.settings import settings
from consumers.registration_consumer.schema.registration import RegistrationData
from ..states.registration import Registration
from .router import router
from src.keyboard_buttons.registration import STUDY_GROUPS_ROW_BUTTONS, BUILDINGS_ROW_BUTTONS, ENTRANCES_ROW_BUTTONS, FLOORS_ROW_BUTTONS, ROOMS_BY_FLOOR_ROW_BUTTONS
from aiogram.types import ReplyKeyboardRemove
from src.validators.validators import FullNameValidator, AgeValidator, PhoneNumberValidator
from src.validators import errors as validation
from src.messages import registration as msg
from src.keyboard_buttons.texts import STUDY_GROUPS, BUILDINGS, ENTRANCES, ROOMS_BY_FLOOR
from src.commands import REGISTRATION
from src.logger import LOGGING_CONFIG, logger
import logging


logging.config.dictConfig(LOGGING_CONFIG)

@router.message(F.text == REGISTRATION)
async def start_registration(message: Message, state: FSMContext):
    await state.set_state(Registration.full_name)
    await message.answer(msg.ENTER_FULL_NAME)

@router.message(Registration.full_name)
async def enter_full_name(message: Message, state: FSMContext):
    answer = msg.ENTER_AGE
    try:
        full_name = FullNameValidator().validate(message)
        await state.update_data(full_name=full_name)
        await state.set_state(Registration.age)
    except validation.FullNameCannotContainMultipleSpacesError:
        answer = msg.FULL_NAME_CANNOT_CONTAIN_MULTIPLE_SPACES
    except validation.InvalidFullNameFormatError:
        answer = msg.INVALID_FULL_NAME_FORMAT
    except validation.NameShouldContainOnlyLettersError:
        answer = msg.NAME_SHOULD_CONTAIN_ONLY_LETTERS
    except validation.TooLongNameError:
        answer = msg.TOO_LONG_NAME
    except validation.TooShortNameError:
        answer = msg.TOO_SHORT_NAME
    except validation.NameBeginCannotBeLowercaseError:
        answer = msg.NAME_BEGIN_CANNOT_BE_LOWER
    finally:
        await message.answer(answer)

@router.message(Registration.age)
async def enter_age(message: Message, state: FSMContext):
    answer = msg.CHOOSE_STUDY_GROUP
    reply_markup=None
    try:
        age = AgeValidator().validate(message)
        await state.update_data(age=age)
        await state.set_state(Registration.study_group)
        reply_markup = STUDY_GROUPS_ROW_BUTTONS
    except validation.AgeShouldBePositiveNumberError:
        answer = msg.AGE_SHOULD_BE_POSITIVE_NUMBER
    except validation.AgeShouldBeNumberError:
        answer = msg.AGE_SHOULD_BE_NUMBER
    except validation.AgeTooOldError:
        answer = msg.AGE_TOO_OLD
    finally:
        await message.answer(answer, reply_markup=reply_markup)

@router.message(Registration.study_group)
async def enter_study_group(message: Message, state: FSMContext):
    study_group = message.text
    if study_group not in STUDY_GROUPS:
        await message.answer(msg.INVALID_STUDY_GROUP)
        return
    await state.update_data(study_group=study_group)
    await state.set_state(Registration.building)
    await message.answer(msg.CHOOSE_BUILDING, reply_markup=BUILDINGS_ROW_BUTTONS)

# @router.message(Registration.room)
# async def enter_room(message: Message, state: FSMContext):
#     answer = msg.WHAT_YOUR_PHONE_NUMBER
#     try:
#         room = RoomValidator().validate(message)
#         await state.update_data(room=room)
#         await state.set_state(Registration.phone_number)
#     except validation.WrongRoomFormatError:
#         answer = msg.WHAT_YOUR_ROOM
#     finally:
#         await message.answer(answer, reply_markup=ReplyKeyboardRemove())

@router.message(Registration.building)
async def enter_building(message: Message, state: FSMContext):
    building = message.text
    if building not in BUILDINGS:
        await message.answer(msg.INVALID_BUILDING)
        return
    await state.update_data(building=building)
    await state.set_state(Registration.entrance)
    await message.answer(msg.CHOOSE_ENTRANCE, reply_markup=ENTRANCES_ROW_BUTTONS)

@router.message(Registration.entrance)
async def enter_entrance(message: Message, state: FSMContext):
    entrance = message.text
    if entrance not in ENTRANCES:
        await message.answer(msg.INVALID_ENTRANCE)
        return
    await state.update_data(entrance=entrance)
    await state.set_state(Registration.floor)
    await message.answer(msg.CHOOSE_FLOOR, reply_markup=FLOORS_ROW_BUTTONS)

@router.message(Registration.floor)
async def enter_floor(message: Message, state: FSMContext):
    floor = message.text
    if floor not in ROOMS_BY_FLOOR.keys():
        await message.answer(msg.INVALID_FLOOR)
        return
    await state.update_data(floor=floor)
    await state.set_state(Registration.room)
    await message.answer(msg.CHOOSE_ROOM, reply_markup=ROOMS_BY_FLOOR_ROW_BUTTONS)

@router.message(Registration.room)
async def enter_room(message: Message, state: FSMContext):
    room = message.text
    data = await state.get_data()
    floor = data.get("floor")
    if room not in ROOMS_BY_FLOOR['floor']:
        await message.answer(msg.INVALID_ROOM)
        return
    await state.update_data(data=data)
    await state.set_state(Registration.phone_number)
    await message.answer(msg.ENTER_PHONE_NUMBER, reply_markup=ReplyKeyboardRemove())

@router.message(Registration.phone_number)
async def enter_phone_number(message: Message, state: FSMContext):
    try:
        phone_number = PhoneNumberValidator().validate(message)
        await state.update_data(phone_number=phone_number)
        await state.clear()

        user_id = message.from_user.id

        data = await state.get_data()
        reg_data = RegistrationData(user_id=user_id, **data)

    except validation.InvalidPhoneNumberFormatError:
        await message.answer(msg.ENTER_PHONE_NUMBER)

async def __push_register_answer(is_success_reg: bool, message: Message):
    answer = msg.SUCCESS_REGISTER if is_success_reg else msg.ALREADY_REGISTER
    await message.answer(answer)
