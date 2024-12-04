import enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from joule.models.data_store.event_store import EventStore

# Perform import and export operations for a module

class ON_EVENT_CONFLICT(enum.Enum):
    KEEP_SOURCE = enum.auto()
    KEEP_DESTINATION = enum.auto()
    KEEP_BOTH = enum.auto()
    MERGE = enum.auto()

class EventTarget:
    def __init__(self, 
                 source_label: str,
                 path: str,
                 on_conflict: ON_EVENT_CONFLICT,
                 filter: str):
        self.source_label = source_label
        self.path = path
        self.on_conflict = on_conflict
        self.filter = filter

    async def run_export(self,
                         store: 'EventStore', 
                         target_directory: str, 
                         last_ts: int) -> tuple[int, dict]:
        return 0,{}
    
    async def run_import(self,
                         store: 'EventStore',
                         metadata: dict,
                         source_directory: str) -> bool:
        return True