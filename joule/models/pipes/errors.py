
class PipeError(Exception):
    """base class for numpypipe exceptions"""


class EmptyPipe(PipeError):
    pass
