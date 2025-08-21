from typing import TYPE_CHECKING
from joule.utilities.validators import validate_stream_path
from joule.utilities.misc import parse_time_interval
from joule.models.data_movement.exporting.exporter_state import ExporterState
from joule.models.folder import find_stream_by_path
from joule.models.data_stream import DataStream
from joule.models.pipes import interval_token as compute_interval_token
from joule.utilities import timestamp_to_human as ts2h
from joule.errors import ConfigurationError
import os
import json
import numpy as np
from dataclasses import dataclass
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from joule.models.data_store.data_store import DataStore
class DataTarget:
    def __init__(self, 
                 source_label: str,
                 path: str,
                 merge_gap: int = 0, # only for imports
                 decimation_factor: int = 1 # only for exports
                 ):
        self.source_label = source_label
        self.path = path
        self.merge_gap = merge_gap 
        self.decimation_factor = decimation_factor
        self.export_summary = None

    async def run_export(self,
                         db: Session,
                         store: 'DataStore', 
                         work_path: str, 
                         state: ExporterState) -> ExporterState:
        stream_model = find_stream_by_path(self.path, db, DataStream)
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
        interval_token = compute_interval_token(stream_model.layout)
        last_ts = state.last_timestamp
        self.export_summary = DataExportSummary(stream_layout=stream_model.layout)
        async def _write_data(data: np.array, layout, decimation_level):
            nonlocal last_ts
            # data is a numpy array that may end with a pipe interval token (all 0's)
            # if there is data write it out to a .dat file
            # if there is an interval boundary write it out as a interval file

            if len(data)==0:
                return # nothing to save
            close_interval = False
            if data[-1]==interval_token:
                close_interval = True
                data = data[:-1]
            if len(data)>1:
                with open(os.path.join(data_path, str(data['timestamp'][-1]))+".dat", 'wb') as f:
                    np.save(f, data)
                last_ts = data['timestamp'][-1] +1
                self.export_summary.end_ts = data['timestamp'][-1]
                if self.export_summary.start_ts is None:
                    self.export_summary.start_ts = data['timestamp'][0]
                self.export_summary.row_count += len(data)
            if close_interval:
                with open(os.path.join(data_path, str(last_ts))+"_interval_break.dat", 'w') as f:
                    f.write(" ")
                self.export_summary.interval_count+=1
            
        await store.extract(stream=stream_model, start=state.last_timestamp, end=None,
                            callback=_write_data, max_rows=None, decimation_level=1)

        return ExporterState(last_timestamp=last_ts)
        
    def summarize_export(self):
        if self.export_summary is None:
            return {} # nothing has been exported yet
        return {
            "source_label": self.source_label,
            "stream_path": self.path,
            "stream_layout": self.export_summary.stream_layout,
            "start_ts": int(self.export_summary.start_ts),
            "end_ts": int(self.export_summary.end_ts),
            "row_count": self.export_summary.row_count,
            "interval_count": self.export_summary.interval_count
        }
    async def run_import(self,
                         store: 'DataStore',
                         metadata: dict,
                         source_directory: str) -> bool:
        return True
    
    def validate(self, db:Session):
        if not find_stream_by_path(self.path, db, DataStream):
            raise ConfigurationError(f"the data stream [{self.path}] does not exist ")
    
def data_target_from_config(config: dict, type: str) -> DataTarget:
    if type == "exporter":
        merge_gap = 0
    elif type == "importer":
        if 'merge_gap' in config:
            merge_gap = parse_time_interval(config['merge_gap'])
        else:
            merge_gap = 0
   
    return DataTarget(config['source_label'],
                      validate_stream_path(config['path']),
                      merge_gap, # only used for import
                      int(config.get('decimation_factor', 1)) # only used for export
                      ) 
@dataclass
class DataExportSummary:
    row_count: int = 0
    interval_count: int = 1
    start_ts: int = None
    end_ts: int = None
    stream_layout: str = ''