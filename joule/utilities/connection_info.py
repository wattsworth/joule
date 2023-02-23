from typing import Dict
from joule.errors import ApiError


class ConnectionInfo:
    """
    Encapsulates database connection information
    """

    def __init__(self, username: str, password: str, port: int, database: str, host: str, nilmdb_url):
        """
        Attributes:
            username (str): database username
            password (str): database password
            port (int): database port
            database (str): database name
            host (str): hostname
            nilmdb_url (str): NilmDB URL (empty if unused)

        """
        self.username = username
        self.password = password
        self.port = port
        self.database = database
        self.host = host
        self.nilmdb_url = nilmdb_url

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
            "host": self.host,
            "nilmdb_url": self.nilmdb_url
        }

    def to_dsn(self) -> str:
        """
        Convert connection parameters to a DSN string used by SQLAlchemy and other
        database engines.

        """
        return "postgresql://%s:%s@%s:%s/%s" % (self.username, self.password,
                                                self.host, self.port, self.database)


def from_json(data: Dict) -> 'ConnectionInfo':
    # keep client backwards compatible with earlier jouled versions
    if "nilmdb_url" not in data:
        data["nilmdb_url"] = ""
    try:
        info = ConnectionInfo(username=data["username"],
                              password=data["password"],
                              port=data["port"],
                              database=data["database"],
                              host=data["host"],
                              nilmdb_url=data["nilmdb_url"])
    except KeyError as e:
        raise ApiError("invalid connection info, missing [%s]" % str(e))
    return info
