from vulcanforge.common.exceptions import ForgeError


class NoSuchProjectError(ForgeError):
    pass


class ProjectConflict(ForgeError):
    pass
