
from typing import TYPE_CHECKING, List
from dataclasses import dataclass
from joule.utilities import parse_time_interval
if TYPE_CHECKING:
    from joule.models.targets import EventTarget, DataTarget, ModuleTarget
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

    def __init__(self, name, 
        event_targets: List['EventTarget'],
        module_targets: List['ModuleTarget'],
        data_targets: List['DataTarget'],
        destination_node: NodeExport,
        destination_folder: FolderExport,
        frequency: int,
        staging_path: str,
        output_path: str,
        next_run_timestamp: int):

        self.event_targets = event_targets
        self.module_targets = module_targets
        self.data_targets = data_targets
        self.name = name
        self.destination_node = destination_node
        self.destination_folder = destination_folder
        self.frequency = frequency
        self.staging_path = staging_path
        self.output_path = output_path
        self.next_run_timestamp = next_run_timestamp

    async def run(self) -> bool:
        return True
    
def exporter_from_config(config: dict) -> Exporter:
    try:
        name = config['Main']['name']
        target_config = config['Target']
        destination_node = None
        backlog = _validate_time_interval(target_config,'backlog')
        retain = _validate_time_interval(target_config,'retain')
        frequency = parse_time_interval(target_config['frequency'])
        if 'url' in target_config:
            destination_node = NodeExport(
                url=target_config['url'],
                importer_api_key=target_config['importer_api_key'],
                backlog=parse_time_interval(target_config['backlog']),
                backlog_path=target_config['backlog'].split('|')[1]
            )
        destination_folder = None
        if 'path' in target_config:
            destination_folder = FolderExport(
                path=target_config['path'],
                retain=int(target_config['retain'].split('|')[0]),
                backlog=int(target_config['backlog'].split('|')[0]),
                backlog_path=target_config['backlog'].split('|')[1]
            )
    except KeyError:
        raise ValueError("missing 'name' in [Main] section")