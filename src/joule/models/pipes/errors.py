from joule.errors import EmptyPipeError


class PipeError(Exception):
    """base class for numpypipe exceptions"""


# inherit from both for backwards compatibility
class EmptyPipe(PipeError, EmptyPipeError):
    pass
