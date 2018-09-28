class ConfigurationError(Exception):
    """
    Error setting up an object due to incorrect configuration
    """
    pass


class SubscriptionError(Exception):
    """
    Error subscribing to a stream that is not available
    """
    pass


class ConnectionError(Exception):
    """
    Error connecting to a Joule server
    """