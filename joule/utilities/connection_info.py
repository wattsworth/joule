from typing import Dict
from joule.errors import ApiError


class ConnectionInfo:
    """
    Encapsulates database connection information
    """

    def __init__(self, username: str, password: str, port: int, database: str, host: str):
        """
        Attributes:
            username (str): database username
            password (str): database password
            port (int): database port
            database (str): database namne
            host (str): hostname

        """
        self.username = username
        self.password = password
        self.port = port
        self.database = database
        self.host = host

    def to_json(self) -> Dict:
        """
        Convert connection parameters to a dictionary of attributes appropriate
        for transmission as JSON

        """
        return {
            "username": self.username,
            "password": self.password,
            "port": self.port,
            "database": self.database,
            "host": self.host
        }

    def to_dsn(self) -> str:
        """
        Convert connection parameters to a DSN string used by SQLAlchemy and other
        database engines.

        """
        return "postgresql://%s:%s@%s:%s/%s" % (self.username, self.password,
                                                self.host, self.port, self.database)


def from_json(data: Dict) -> 'ConnectionInfo':
    try:
        info = ConnectionInfo(username=data["username"],
                       password=data["password"],
                       port=data["port"],
                       database=data["database"],
                       host=data["host"])
    except KeyError as e:
        raise ApiError("invalid connection info, missing [%s]" % str(e))
    return info
