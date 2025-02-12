from typing import TYPE_CHECKING
from joule.utilities.validators import validate_stream_path
from joule.utilities.misc import parse_time_interval
from joule.models.data_movement.exporting.exporter_state import ExporterState
from joule.models.folder import find_stream_by_path
from joule.models.data_stream import DataStream
from joule.utilities import timestamp_to_human as ts2h
import os
import json
import numpy as np
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

    async def run_export(self,
                         db: Session,
                         store: 'DataStore', 
                         work_path: str, 
                         state: ExporterState) -> ExporterState:
        stream_model = find_stream_by_path(self.path, db, DataStream)
        pipe = await store.data_read(start=state.last_timestamp)
        # save the stream metadata
        with open(os.path.join(work_path, 'metadata.json'), 'w') as f:
            f.write(json.dumps({
                    "source_label": self.source_label,
                    "stream_path": self.path,
                    "stream_model": stream_model.to_json()
                }, indent=2))

        empty_interval = False
        # make a subdirectory for the data
        data_path = os.path.join(work_path, "data")
        os.makedirs(data_path, exist_ok=True)
        while await pipe.not_empty():
            data = await pipe.read()
            pipe.consume(len(data))
            if len(data)==0:
                if not pipe.end_of_interval: 
                    print("WARNING: empty pipe read!")
                # this is just closing the interval, it's ok that it's empty
            else:
                #print(f"read {len(data)} samples from {stream}: {ts2h(data['timestamp'][0])}-{ts2h(data['timestamp'][-1])}")
                _write_data(data, data_path)
                last_ts = data['timestamp'][-1]+1 # so we don't re-read the same data next time
                empty_interval = False
            if pipe.end_of_interval:
                _write_interval_break(last_ts, data_path)
                if empty_interval:
                    print(f"WARNING: empty interval(s) detected in {self.path} starting at {ts2h(last_ts)}")
                empty_interval=True
        return ExporterState(last_timestamp=last_ts)
        
    
    async def run_import(self,
                         store: 'DataStore',
                         metadata: dict,
                         source_directory: str) -> bool:
        return True
    
    
def data_target_from_config(config: dict) -> DataTarget:
    if 'merge_gap' in config:
        merge_gap = parse_time_interval(config['merge_gap'])
    else:
        merge_gap = 0
    return DataTarget(config['source_label'],
                      validate_stream_path(config['path']),
                      merge_gap, # only used for import
                      int(config.get('decimation_factor', 1)) # only used for export
                      ) 


def _write_data(data: np.array, stream_dir):
    # save the numpy array as a binary file
    if len(data)==0:
        return # nothing to save
    with open(os.path.join(stream_dir, str(data['timestamp'][-1]))+".dat", 'wb') as f:
        np.save(f, data)

def _write_interval_break(ts, stream_dir):
    with open(os.path.join(stream_dir, str(ts))+"_interval_break.dat", 'w') as f:
        f.write(" ")