
from typing import List
from dataclasses import dataclass
from sqlalchemy.orm import Session
from joule.utilities import parse_time_interval
from joule.models.data_store.data_store import DataStore
from joule.models.data_store.event_store import EventStore
from joule.models.data_movement.export.exporter_state import ExporterStateService
from joule.models.data_movement.targets import (DataTarget, EventTarget, ModuleTarget,
                                                event_target_from_config,
                                                data_target_from_config,
                                                module_target_from_config)
import logging
import re
import tarfile
import os
import shutil
import itertools
from datetime import datetime

logger = logging.getLogger('joule')
"""
Configuration File:
[Main]
name = exporter name

[Target]
# export to a node
url = http://...
importer_api_key = XXXX
# export to a directory
path = /file/path
retain = 5m|all

frequency = 1h
backlog = 3h|all|none

[DataStream.1]
source_label = source name
path = /path/to/stream
decimation_factor = 4

[EventStream.1]
source_label = source name
path = /path/to/stream
filter = <filter syntax>

[Module.1]
source_label = source name
module = <module_name>
parameters = ... <custom string passed to module>
"""

@dataclass
class NodeExport:
    url: str
    importer_api_key: str
    backlog: int
    backlog_path: str

@dataclass
class FolderExport:
    path: str
    retain: int
    backlog: int
    backlog_path: str

class Exporter:

    def __init__(
            self, name, 
            event_targets: List['EventTarget'],
            module_targets: List['ModuleTarget'],
            data_targets: List['DataTarget'],
            
            destination_node: NodeExport,
            destination_folder: FolderExport,
            
            frequency_us: int,
            backlog_us: int,
            retain_us: int,

            work_path: str,
            next_run_timestamp: int):

        self.event_targets = event_targets
        self.module_targets = module_targets
        self.data_targets = data_targets
        self.name = name
        self.destination_node = destination_node
        self.destination_folder = destination_folder
        self.frequency_us = frequency_us
        self.backlog_us = backlog_us
        self.retain_us = retain_us
        self.work_path = work_path
        self.next_run_timestamp = next_run_timestamp

        # directory structure in the work path
        # - staging
        # - output
        #   - datasets <-- actual data
        #   - node_backlog   <-- symlinks to datasets
        #   - folder_backlog <-- `
        self._staging_path = None
        self._output_path = None
        self._output_datasets_path = None
        self._output_node_backlog_path = None
    
        self._initialized = False

        

    def _initialize(self):
        """Lazy directory creation to facilitate testing"""
        if self._initialized:
            return
        # create the staging and output directories
        self._staging_path = os.path.join(self.work_path, "staging")
        self._output_path = os.path.join(self.work_path, "output")
        self._output_datasets_path = os.path.join(self._output_path, "datasets")
        self._output_node_backlog_path = os.path.join(self._output_path, "node_backlog")
        self._output_folder_backlog_path = os.path.join(self._output_path, "folder_backlog")
        os.makedirs(self._staging_path)
        os.makedirs(self._output_datasets_path)
        os.makedirs(self._output_node_backlog_path)
        os.makedirs(self._output_folder_backlog_path)
        self._initialized = True

    async def run(self,
                  db: Session,
                  event_store: EventStore,
                  data_store: DataStore,
                  state_service: ExporterStateService) -> bool:
        self._initialize()
        self._clean_directories()

        idx = 0
        # create a path for each event target and run the export task
        for event_target in self.event_targets:
            target_data_path = os.path.join(self._staging_path, "events", str(idx))
            os.makedirs(target_data_path)
            await event_target.run_export(target_data_path)
            idx += 1
        idx = 0
        # create a path for each module target and run the export task
        for module_target in self.module_targets:
            target_data_path = os.path.join(self._staging_path, "modules", str(idx))
            os.makedirs(target_data_path)
            await module_target.run_export(target_data_path)
            idx += 1
        idx = 0
        # create a path for each data target and run the export task
        for data_target in self.data_targets:
            target_data_path = os.path.join(self._staging_path, "data", str(idx))
            os.makedirs(target_data_path)
            last_state = state_service.get(self.name, 'data', data_target.source_label)
            new_state=await data_target.run_export(
                db=db, 
                data_store=data_store,
                work_path=target_data_path,
                state=last_state)
            state_service.save(self.name, 'data', data_target.source_label, new_state)
            idx += 1

        # bundle _staging_path directory into a compressed tarball and store in /backlog/datasets
        timestamp = datetime.now().strftime("%Y_%m_%d-%H-%M-%S")
        archive_name = f"ww-data_{timestamp}.tgz"
        archive_file_path = os.path.join(self._output_datasets_path,archive_name)
        with tarfile.open(archive_file_path, "w:gz") as tar:
            # Add the source directory to the tarball.
            # arcname ensures that the directory structure inside the tarball
            # starts with the directory name rather than the full source path.
            tar.add(self._staging_path, arcname=os.path.basename('ww-data'))

        success = True
        if not self._export_to_node(archive_file_path):
            # create a symlink in the node backlog
            os.symlink(archive_file_path, os.path.join(self._output_node_backlog_path,archive_name))
            success=False
        if not self._export_to_folder(archive_file_path):
            # create a symlink in the folder backlog
            os.symlink(archive_file_path, os.path.join(self._output_folder_backlog_path,archive_name))
            success=False
        if success:
            # remove the archive_file since it was exported successfully
            os.remove(archive_file_path)
        

    def _export_to_folder(self, archive_file: str) -> bool:
        if self.destination_folder is None:
            return True # data is not exported to a folder
        try:
            shutil.copy(archive_file, self.destination_folder)
            return True
        except Exception as e:
            logging.error(f"failed to copy {archive_file} to {self.destination_folder}: {e}")
            return False
    
    def _export_to_node(self, archive_file: str) -> bool:
        if self.destination_node is None:
            return True # data is not exported to a node
        print("TODO!")
        return True

    def _clean_directories(self):
        # clear the entire staging directory
        shutil.rmtree(self._staging_path, ignore_errors=True)
        # remove any symlinks that are older than the retain time in the backlog directories
        referenced_datasets = []
        now = datetime.now()
        with(os.scandir(self._output_node_backlog_path) as node_backlog, 
             os.scandir(self._output_folder_backlog_path) as folder_backlog):
            for entry in itertools.chain(node_backlog, folder_backlog):
                if entry.is_symlink():
                    if os.path.getmtime(entry.path) < now - self.backlog_us/1e6:
                        logger.warning(f"dropping {entry.name} from backlog, older than retain time")
                        os.remove(entry.path)
                    else:
                        st = entry.stat(follow_symlinks=True)
                        referenced_datasets.append((st.st_dev, st.st_ino))
                else:
                    logger.warning(f"unexpected file {entry.path}, not a symlink")
            
        # remove any datasets that are not referenced by symlinks in the backlog directories
        with os.scandir(self._output_datasets_path) as datasets:
            for entry in datasets:
                st = entry.stat(follow_symlinks=True)
                if (st.st_dev, st.st_ino) not in referenced_datasets:
                    logger.warning(f"removing unreferenced dataset {entry.path}")
                    os.remove(entry.path)
        
def exporter_from_config(config: dict, work_path: str) -> Exporter:
    try:
        name = config['Main']['name']
        target_config = config['Target']
        destination_node = None
        backlog_us = parse_time_interval(target_config,'backlog')
        retain_us = parse_time_interval(target_config,'retain')
        frequency_us = parse_time_interval(target_config['frequency'])
        if 'url' in target_config:
            destination_node = NodeExport(
                url=target_config['url'],
                importer_api_key=target_config['importer_api_key'])
        destination_folder = None
        if 'path' in target_config:
            destination_folder = FolderExport(
                path=target_config['path'],
                retain=parse_time_interval(target_config['retain'])
            )
    except KeyError:
        raise ValueError("missing 'name' in [Main] section")
    
   
    event_target_configs = [config[section] for section in 
                            filter(lambda sec: re.match(r"EventStream\d", sec),
                            config.sections())]
    event_targets = [event_target_from_config(etc) for etc in event_target_configs]

    module_target_configs = [config[section] for section in 
                             filter(lambda sec: re.match(r"Module\d", sec),
                             config.sections())]
    module_targets = [module_target_from_config(mtc) for mtc in module_target_configs]

    data_target_configs = [config[section] for section in 
                             filter(lambda sec: re.match(r"DataStream\d", sec),
                             config.sections())]
    data_targets = [data_target_from_config(dtc) for dtc in data_target_configs]

    return Exporter(name=name, 
                    event_targets=event_targets,
                    module_targets=module_targets,
                    data_targets=data_targets,
                    destination_node=destination_node,
                    destination_folder=destination_folder,
                    frequency_us=frequency_us,
                    backlog_us=backlog_us,
                    retain_us=retain_us,
                    next_run_timestamp=0,
                    work_path=work_path)
