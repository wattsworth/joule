
from typing import TYPE_CHECKING, Dict, List
import re
import os
from sqlalchemy.orm import Session
import logging
import json
from joule.models.data_store.data_store import DataStore
from joule.models.data_store.event_store import EventStore
from joule.models.data_movement.targets import (DataTarget, EventTarget, ModuleTarget,
                                                event_target_from_config,
                                                data_target_from_config,
                                                module_target_from_config)
from joule.utilities.archive_tools import ImportLogger

if TYPE_CHECKING:
    from joule.models.targets import EventTarget, DataTarget, ModuleTarget
log = logging.getLogger('joule')

"""
Configuration File:
[Main]
name = importer name
# accept archives from a specific node
# omit to match any archive source
node = node name

[DataStream.1]
source_label = source name
path = /path/to/stream
merge_gap = 5s

[EventStream.1]
source_label = source name
path = /path/to/stream
on_conflict = keep_source | keep_destination | keep_both | merge

[Module.1]
source_label = source name
module = <module_name>
parameters = ... <custom string passed to module>
"""

class Importer:

    def __init__(self, name, node_name, 
        event_targets: Dict[str,'EventTarget'],
        module_targets: Dict[str,'ModuleTarget'],
        data_targets: Dict[str,'DataTarget']):

        self.event_targets = event_targets
        self.module_targets = module_targets
        self.data_targets = data_targets
        self.node_name = node_name
        self.name = name

    async def run(self, path,
                  db: Session,
                  event_store: EventStore,
                  data_store: DataStore) -> ImportLogger:
        logger = ImportLogger()
        # go through the data directory to look for data streams
        for item in os.listdir(os.path.join(path,"data")):
            folder = os.path.join(path,"data",item)
            if not os.path.isdir(folder):
                logger.warning(f"Importer[{self.name}]: unexpected file in datastream folder, ignoring")
                continue
            with open(os.path.join(path,"data",item,"metadata.json"),'r') as f:
                metadata = json.load(f)
            target = self.data_targets.get(metadata['source_label'])
            if target is None:
                logger.warning(f"No match for data stream with label [{metadata['source_label']}]")
                continue
            await target.run_import(db=db,
                                    metadata=metadata, 
                                    store=data_store,
                                    source_directory=os.path.join(path,"data",item,"data"),
                                    logger=logger)

        # go through the events directory to look for event streams
        for item in os.listdir(os.path.join(path,"events")):
            folder = os.path.join(path,"events",item)
            if not os.path.isdir(folder):
                logger.warning(f"Importer[{self.name}]: unexpected file in datastream folder, ignoring")
                continue
            with open(os.path.join(path,"events",item,"metadata.json"),'r') as f:
                metadata = json.load(f)
            target = self.event_targets.get(metadata['source_label'])
            if target is None:
                logger.warning(f"No match for event stream with label [{metadata['source_label']}]")
                continue
            await target.run_import(db=db,
                                    metadata=metadata, 
                                    store=event_store,
                                    source_directory=os.path.join(path,"events",item,"data"),
                                    logger=logger)
            
        return logger
    
def importer_from_config(config: dict) -> Importer:
    try:
        name = config['Main']['name']
        node_name = config['Main'].get('node',None)
    except KeyError as e:
        raise ValueError(f"missing {e} in importer configuration")
    event_target_configs = [config[section] for section in 
                            filter(lambda sec: re.match(r"EventStream\.\d+", sec),
                            config.sections())]
    event_targets = [event_target_from_config(etc,type="importer") for etc in event_target_configs]

    module_target_configs = [config[section] for section in 
                             filter(lambda sec: re.match(r"Module\.\d+", sec),
                             config.sections())]
    module_targets = [module_target_from_config(mtc) for mtc in module_target_configs]

    data_target_configs = [config[section] for section in 
                             filter(lambda sec: re.match(r"DataStream\.\d+", sec),
                             config.sections())]
    data_targets = [data_target_from_config(dtc, type="importer") for dtc in data_target_configs]

    return Importer(name=name,
                    node_name=node_name, 
                    event_targets={t.source_label: t for t in event_targets},
                    module_targets={t.source_label: t for t in module_targets},
                    data_targets={t.source_label: t for t in data_targets})

