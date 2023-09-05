class NodeConfig:
    def __init__(self, name, url, key):
        self.name = name
        self.url = url
        self.key = key

    def to_json(self):
        return {
            "name": self.name,
            "url": self.url,
            "key": self.key
        }
