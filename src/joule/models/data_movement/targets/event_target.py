import enum
import json
from typing import TYPE_CHECKING, List, Dict
from joule.models.data_movement.exporting.exporter_state import ExporterState
from joule.models.data_store.event_store import EventStore
from joule.models.event_stream import EventStream
from joule.models.folder import find_stream_by_path
from joule.utilities.validators import validate_stream_path, validate_event_filter
import os
import json
from sqlalchemy.orm import Session


BLOCK_SIZE=1000
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
                         db: Session,
                         store: EventStore, 
                         work_path: str, 
                         state: ExporterState) -> ExporterState:
        stream_model = find_stream_by_path(self.path, db, EventStream)
        # save the stream metadata
        with open(os.path.join(work_path, 'metadata.json'), 'w') as f:
            f.write(json.dumps({
                    "source_label": self.source_label,
                    "stream_path": self.path,
                    "stream_model": stream_model.to_json()
                }, indent=2))
        # make a subdirectory for the data
        data_path = os.path.join(work_path, "data")
        os.makedirs(data_path, exist_ok=True)
        last_ts = state.last_timestamp
        while True:
            events = await store.extract(stream_model, 
                                         start=last_ts,
                                         end=None,
                                         json_filter=self.filter,
                                         limit=BLOCK_SIZE,
                                         include_on_going_events=False)
            if len(events)==0:
                break
            _write_data(events, data_path)
            last_ts = events[-1]['start_time']+1
        return ExporterState(last_timestamp=last_ts)
    
    async def run_import(self,
                         store: 'EventStore',
                         metadata: dict,
                         source_directory: str) -> bool:
        return True
    
def _write_data(events: List[Dict], data_dir):
    with open(os.path.join(data_dir, str(events[-1]['start_time']))+".json", 'w') as f:
        json.dump(events, f, indent=2)
    
def event_target_from_config(config: dict, type:str) -> EventTarget:
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