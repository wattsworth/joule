class NodeInfo:

    def __init__(self, version: str, name: str, path: str, size_reserved: int,
                 size_other: int, size_free: int, size_db: int):
        self.version = version
        self.name = name
        self.path = path
        self.size_free = size_free
        self.size_reserved = size_reserved
        self.size_db = size_db
        self.size_other = size_other
