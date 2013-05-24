
from vulcanforge.common.exceptions import ForgeError


class MailError(ForgeError):
    pass


class AddressException(MailError):
    pass
