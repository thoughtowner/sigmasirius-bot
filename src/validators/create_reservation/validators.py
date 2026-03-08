import re
from . import errors as e
from ..base_validator import BaseTgValidator


class PeopleNumberValidator(BaseTgValidator):
    def _do_validate(self, message: str):
        try:
            number = int(message)
        except (TypeError, ValueError):
            raise e.PeopleNumberShouldBeNumber
        
        number = int(message)
        if not (number >= 1 and number <= 4):
            raise e.PeopleNumberShouldBeBetweenOneAndFour
