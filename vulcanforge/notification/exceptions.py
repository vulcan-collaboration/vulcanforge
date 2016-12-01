
from vulcanforge.common.exceptions import ForgeError


class MailError(ForgeError):
    pass


class AddressException(MailError):
    pass


class ContextError(ForgeError):
    """Not enough context to create/send notifications"""
    pass