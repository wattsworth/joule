from typing import TYPE_CHECKING, Tuple, List
from joule.utilities.validators import validate_stream_path
from joule.utilities.misc import parse_time_interval
from joule.models.data_movement.exporting.exporter_state import ExporterState
from joule.models.data_store.errors import DataError
from joule.models.folder import find_stream_by_path
from joule.models import data_stream
from joule.models.pipes import interval_token as compute_interval_token
from joule.models.pipes import LocalPipe
from joule.services.load_data_streams import save_data_stream
from joule.utilities import timestamp_to_human as ts2h
from joule.utilities.archive_tools import ImportLogger
from joule.errors import ConfigurationError, PipeError
from joule.models import DataStream, folder

import os
import json
import asyncio
import numpy as np
from dataclasses import dataclass
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger('joule')

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
            "stream_layout": self.export_summary.stream_layout,
            "start_ts": start_ts,
            "end_ts": end_ts,
            "row_count": self.export_summary.row_count,
            "interval_count": self.export_summary.interval_count
        }
    async def run_import(self,
                         db: Session,
                         store: 'DataStore',
                         metadata: dict,
                         source_directory: str,
                         logger: ImportLogger):
        nrows = 0
        logger.set_metadata(self.source_label,self.path,'data_stream')
        # retrieve the stream or create it based on the metadata
        stream = find_stream_by_path(self.path, db, stream_type=DataStream)
        if stream is None:
            stream = data_stream.from_json(metadata['stream_model'], reset_parameters=True)
            dest_folder, name = folder.parse_stream_path(self.path)
            stream.name = name # the model is based of the received metadata so reset the name
            save_data_stream(stream, dest_folder, db)
            db.commit()
            logger.info(f"creating data stream {self.path}")
        
        data_files = os.listdir(source_directory)
        pipe = LocalPipe(layout=stream.layout)
        inserter_task = await store.spawn_inserter(stream,pipe)
        try:
            for file in sorted(data_files):
                if file.endswith("_interval_break.dat"):
                    #print("closing interval")
                    await pipe.close_interval()
                    continue
                with open(os.path.join(source_directory,file),'rb') as f:
                    data = np.load(f)
                    await pipe.write(data)        
                    nrows+=len(data)
                    await asyncio.sleep(0.1) # allow errors in other coroutines to bubble up
            logger.info(f"imported {nrows} rows of data into {self.path}")
        except PipeError as e:
            logger.error(f"cannot import data over range {ts2h(data[0][0])}-- {ts2h(data[-1][0])}: {str(e)}")
        finally:
            await pipe.close()
        try:
            await inserter_task
        except Exception as e:
            logger.error(f"cannot import data into {self.path}: {e}")
    
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