from . import errors as e
from ..base_validator import BaseTgValidator

MAX_TITLE_LENGTH = 50
MAX_DESCRIPTION_LENGTH = 200


class TitleValidator(BaseTgValidator):
    def _do_validate(self, message: str):
        if len(message) > MAX_TITLE_LENGTH:
            raise e.TooLongTitleError


class DescriptionValidator(BaseTgValidator):
    def _do_validate(self, message: str):
        if len(message) > MAX_DESCRIPTION_LENGTH:
            raise e.TooLongDescriptionError
