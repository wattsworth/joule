import yarl


class Proxy:

    def __init__(self, name: str, uuid: int, url: yarl.URL):
        self.name = name
        self.uuid = uuid
        self.url = url

    def __repr__(self):
        return "<joule.models.Proxy name=%r uuid=%r url=%r>" % (self.name, self.uuid, self.url)
    
    def to_json(self):
        """
        Returns: Dictionary of Proxy attributes
        """
        return {
            'id': self.uuid,
            'name': self.name,
            'url': str(self.url)
        }
