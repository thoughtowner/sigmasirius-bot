import re
from . import errors as e
from .base_validator import BaseTgValidator

MIN_NAME_LEN = 2
MAX_NAME_LEN = 100

MAX_AGE = 200

PHONE_NUMBER_PATTERN = r'^\+7 \(\d{3}\) \d{3}-\d{2}-\d{2}$'


class FullNameValidator(BaseTgValidator):
    def _do_validate(self, message: str):
        full_name_parts = message.split()

        if message.count(' ') > 2:
            raise e.FullNameCannotContainMultipleSpacesError

        if len(full_name_parts) != 3:
            raise e.InvalidFullNameFormatError

        for part in full_name_parts:
            if not part.isalpha():
                raise e.NameShouldContainOnlyLettersError
            if len(part) >= MAX_NAME_LEN:
                raise e.TooLongNameError
            if len(part) < MIN_NAME_LEN:
                raise e.TooShortNameError
            if part[0].islower():
                raise e.NameBeginCannotBeLowercaseError


class AgeValidator(BaseTgValidator):
    def _do_validate(self, message: str):
        if not message.isdigit():
            if message[0] == '-' and message[1:].isdigit():
                raise e.AgeShouldBePositiveNumberError
            raise e.AgeShouldBeNumberError
        if int(message) >= MAX_AGE:
            raise e.AgeTooOldError


class PhoneNumberValidator(BaseTgValidator):
    def _do_validate(self, message: str):
        if not re.match(PHONE_NUMBER_PATTERN, message):
            raise e.InvalidPhoneNumberFormatError
