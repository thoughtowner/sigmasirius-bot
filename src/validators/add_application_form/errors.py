class ValidationError(Exception):
    def __init__(self) -> None:
        super().__init__()


class TooLongTitleError(ValidationError):
    pass


class TooLongDescriptionError(ValidationError):
    pass
