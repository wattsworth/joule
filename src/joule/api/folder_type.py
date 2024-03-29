from typing import List, TYPE_CHECKING
from joule import errors

if TYPE_CHECKING:
    from .data_stream import DataStream
    from .event_stream import EventStream


class Folder:
    """
    API Folder model. See :ref:`sec-node-folder-actions` for details on using the API to
    manipulate folders. Folders are locked if they contain locked streams (streams that are active
    or statically configured). Folder objects should not be created directly. They should be received
    via API calls.

    Parameters:
        name (str): folder name, must be unique in the parent
        description (str): optional field
        locked (bool): folder may not be moved, deleted, or changed
        data_streams (List[DataStream]): data streams in the folder
        event_streams (List[EventStream]): event streams in the folder
        children (List[Folder]): subfolders in the folder

    """
    # folder params
    def __init__(self, name=""):
        self._id = None
        self.name: str = name
        self.description: str = ""
        self.locked: bool = False
        self.data_streams: List['DataStream'] = []
        self.event_streams: List['EventStream'] = []
        self.children: List['Folder'] = []

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
            "streams": [s.to_json() for s in self.data_streams],
            "event_streams": [s.to_json() for s in self.event_streams],
            "children": [c.to_json() for c in self.children],
            "locked": self.locked
        }
