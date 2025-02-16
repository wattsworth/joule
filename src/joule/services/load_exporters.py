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
    # Delete the contents of the directory
    for item in os.listdir(exporters_work_path):
        item_path = os.path.join(exporters_work_path, item)
        if os.path.isfile(item_path) or os.path.islink(item_path):
            os.unlink(item_path)  # Remove file or symbolic link
        elif os.path.isdir(item_path):
            shutil.rmtree(item_path)  # Remove directory and its contents

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