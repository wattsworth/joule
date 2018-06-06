class DaemonError(Exception):
    """Base class for exceptions in this module"""
    pass


class ConfigError(DaemonError):

    def __init__(self, message):
        self.message = "Error in config file: %s" % message


class UnworkedStreamError(DaemonError):
    pass
