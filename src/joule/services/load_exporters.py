import logging
import shutil
import os
from typing import List
from joule.errors import ConfigurationError
from sqlalchemy.orm import Session
from joule.services.helpers import (Configurations,
                                    load_configs)
from joule.models.data_movement.exporting.exporter import Exporter, exporter_from_config

logger = logging.getLogger('joule')
def run(configs_path: str, exporters_work_path: str) -> List[Exporter]:
    configs = load_configs(configs_path)
    exporters = []
    # flush the work_path directory, remove all files and folders
    shutil.rmtree(exporter_work_path, ignore_errors=True)
    idx = 0
    # create a subfolder for each exporter and initialize the Exporter object
    for config in configs:
        try:
            exporter_work_path = os.path.join(exporters_work_path, str(idx))
            os.makedirs(exporter_work_path)
            exporters.append(exporter_from_config(config=config, 
                                                  work_path=exporter_work_path))
            idx += 1
        except (ConfigurationError, ValueError) as e:
            logger.error("Invalid exporter [%s]: %s" % (config, e))
    return exporters