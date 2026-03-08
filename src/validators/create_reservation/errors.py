class ValidationError(Exception):
    def __init__(self) -> None:
        super().__init__()


class PeopleNumberShouldBeBetweenOneAndFour(ValidationError):
    pass

class PeopleNumberShouldBeNumber(ValidationError):
    pass
