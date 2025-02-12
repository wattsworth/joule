import enum
import json
from typing import TYPE_CHECKING, List
from joule.utilities.validators import validate_stream_path, validate_event_filter
if TYPE_CHECKING:
    from joule.models.data_store.event_store import EventStore

# Perform import and export operations for a module

class ON_EVENT_CONFLICT(enum.Enum):
    KEEP_SOURCE = enum.auto()
    KEEP_DESTINATION = enum.auto()
    KEEP_BOTH = enum.auto()
    MERGE = enum.auto()
    NA = enum.auto() # used for exporters (not applicable)

class EventTarget:
    def __init__(self, 
                 source_label: str,
                 path: str,
                 on_conflict: ON_EVENT_CONFLICT,
                 filter: List):
        self.source_label = source_label
        self.path = path
        self.on_conflict = on_conflict
        self.filter:List = filter

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
    
def event_target_from_config(config: dict, type) -> EventTarget:
    if type=="exporter":
        on_conflict =ON_EVENT_CONFLICT.NA
        event_filter = validate_event_filter(config.get('filter', ""))
    elif type=="importer":
        on_conflict = _validate_on_conflict(config['on_conflict'])
        event_filter = None

    return EventTarget(config['source_label'],
                       validate_stream_path(config['path']),
                       on_conflict, event_filter)

def _validate_on_conflict(value: str) -> ON_EVENT_CONFLICT:
    if value == "na":
        return ON_EVENT_CONFLICT.NA
    if value == "keep_source":
        return ON_EVENT_CONFLICT.KEEP_SOURCE
    if value == "keep_destination":
        return ON_EVENT_CONFLICT.KEEP_DESTINATION
    if value == "keep_both":
        return ON_EVENT_CONFLICT.KEEP_BOTH
    if value == "merge":
        return ON_EVENT_CONFLICT.MERGE
    raise ValueError(f"invalid on_conflict value: {value}")