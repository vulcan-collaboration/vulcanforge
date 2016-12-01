
from vulcanforge.common.exceptions import ForgeError


class PasswordAlreadyUsedError(ForgeError):
    pass


class PasswordInvalidError(ForgeError):
    pass


class PasswordCannotBeChangedError(ForgeError):
    pass
