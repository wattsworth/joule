from joule import errors


class Folder:
    # folder params
    def __init__(self):
        self._id = None
        self.name = ""
        self.description = ""
        self.locked = False
        self.streams = []
        self.children = []

    def __repr__(self):
        return "<joule.api.Folder id=%r name=%r description=%r locked=%r>" % (
                self._id, self.name, self.description, self.locked)

    @property
    def id(self) -> int:
        if self._id is None:
            raise errors.ApiError("this is a local model with no ID. See API docs")
        return self._id

    @id.setter
    def id(self, value: int):
        self._id = value

    def to_json(self):
        return {
            "id": self._id,
            "name": self.name,
            "description": self.description,
            "streams": [s.to_json() for s in self.streams],
            "children": [c.to_json() for c in self.children],
            "locked": self.locked
        }
