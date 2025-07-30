import logging
import os
from typing import List
from joule.errors import ConfigurationError
from joule.services.helpers import load_configs, flush_directory
from joule.models.data_movement.exporting.exporter import Exporter, exporter_from_config

logger = logging.getLogger('joule')
def run(configs_path: str, exporters_work_path: str, node_name: str) -> List[Exporter]:
    configs = load_configs(configs_path)
    exporters = []
    # flush the work_path directory, remove all files and folders
    flush_directory(exporters_work_path)

    idx = 0
    # create a subfolder for each exporter and initialize the Exporter object
    for file_path, config in configs.items():
        try:
            exporter_work_path = os.path.join(exporters_work_path, str(idx))
            os.makedirs(exporter_work_path)
            exporters.append(exporter_from_config(config=config, 
                                                  work_path=exporter_work_path,
                                                  node_name=node_name))
            idx += 1
        except (ConfigurationError, ValueError) as e:
            logger.error("Invalid exporter [%s]: %s" % (file_path, e))
    return exporters