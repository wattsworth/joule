import enum
import json
from typing import TYPE_CHECKING, List, Dict, Tuple
from joule.models.data_movement.exporting.exporter_state import ExporterState
from joule.models.data_store.event_store import EventStore
from joule.models import event_stream 
from joule.models.folder import find_stream_by_path, parse_stream_path
from joule.services.load_event_streams import save_event_stream
from joule.utilities.validators import validate_stream_path, validate_event_filter
from joule.utilities.archive_tools import ImportLogger
import os
import json
from sqlalchemy.orm import Session
from dataclasses import dataclass
import logging

logger = logging.getLogger('joule')

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
        self.export_summary = None

    async def run_export(self,
                         db: Session,
                         store: EventStore, 
                         work_path: str, 
                         state: ExporterState) -> ExporterState:
        stream_model = find_stream_by_path(self.path, db, event_stream.EventStream)
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
        self.export_summary = EventExportSummary(event_fields=stream_model.event_fields)
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
            self.export_summary.end_ts = events[-1]['end_time']
            if self.export_summary.start_ts is None:
                self.export_summary.start_ts = events[0]['start_time']
            self.export_summary.event_count += len(events)
            last_ts = events[-1]['start_time']+1
        return ExporterState(last_timestamp=last_ts)
    
    def summarize_export(self):
        if self.export_summary is None:
            return {} # nothing has been exported yet
        if self.export_summary.start_ts is not None:
            start_ts = int(self.export_summary.start_ts)
        else:
            start_ts = None
        if self.export_summary.end_ts is not None:
            end_ts = int(self.export_summary.end_ts)
        else:
            end_ts = None
        return {
            "source_label": self.source_label,
            "stream_path": self.path,
            "event_fields": self.export_summary.event_fields,
            "start_ts": start_ts,
            "end_ts": end_ts,
            "event_count": self.export_summary.event_count
        }
    
    async def run_import(self,
                         db: Session,
                         store: 'EventStore',
                         metadata: dict,
                         source_directory: str,
                         logger: ImportLogger):
        
        logger.set_metadata(self.source_label,self.path,'event_stream')
        # retrieve the stream or create it based on the metadata
        stream = find_stream_by_path(self.path, db, stream_type=event_stream.EventStream)
        if stream is None:
            stream = event_stream.from_json(metadata['stream_model'], reset_parameters=True)
            dest_folder, name = parse_stream_path(self.path)
            stream.name = name # the model is based of the received metadata so reset the name
            save_event_stream(stream, dest_folder, db)
            db.commit() 
            await store.create(stream)
            logger.info(f"creating event stream {self.path}")


        data_files = os.listdir(source_directory)
        nevents = 0
        for file in sorted(data_files):
            with open(os.path.join(source_directory,file),'r') as f:
                events = json.load(f)
            nevents+=len(events)
            await store.upsert(stream, events)
        logger.info(f"imported {nevents} events into {self.path}")

    
def _write_data(events: List[Dict], data_dir):
    with open(os.path.join(data_dir, str(events[-1]['start_time']))+".json", 'w') as f:
        json.dump(events, f, indent=2)
    
def event_target_from_config(config: dict, type:str) -> EventTarget:
    if type=="exporter":
        on_conflict =ON_EVENT_CONFLICT.NA
        event_filter_str = config.get('filter')
        if event_filter_str is not None:
            event_filter = validate_event_filter(event_filter_str)
        else:
            event_filter = None
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

@dataclass
class EventExportSummary:
    event_count: int = 0
    start_ts: int = None
    end_ts: int = None
    event_fields: str = ''