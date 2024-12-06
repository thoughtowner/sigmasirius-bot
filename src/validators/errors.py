class ValidationError(Exception):
    def __init__(self) -> None:
        super().__init__()


class FullNameCannotContainMultipleSpacesError(ValidationError):
    pass


class InvalidFullNameFormatError(ValidationError):
    pass


class NameShouldContainOnlyLettersError(ValidationError):
    pass


class TooLongNameError(ValidationError):
    pass


class TooShortNameError(ValidationError):
    pass


class NameBeginCannotBeLowercaseError(ValidationError):
    pass


class AgeShouldBePositiveNumberError(ValidationError):
    pass


class AgeShouldBeNumberError(ValidationError):
    pass


class AgeTooOldError(ValidationError):
    pass


class InvalidPhoneNumberFormatError(ValidationError):
    pass
