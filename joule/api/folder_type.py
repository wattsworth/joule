

class Folder:
    # folder params
    def __init__(self):
        self.id = None
        self.name = ""
        self.description = ""
        self.streams = []
        self.children = []

    def to_json(self):
        # only include write-able attributes
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description
        }