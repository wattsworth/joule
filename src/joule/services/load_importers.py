import logging
import shutil
import os
from typing import List
from joule.errors import ConfigurationError
from joule.services.helpers import load_configs, flush_directory
from joule.models.data_movement.importing.importer import Importer, importer_from_config

logger = logging.getLogger('joule')
def run(configs_path: str, importers_work_path: str) -> List[Importer]:
    configs = load_configs(configs_path)
    importers = []
    # flush the work_path directory, remove all files and folders
    flush_directory(importers_work_path)

    idx = 0
    # create a subfolder for each importer and initialize the Exporter object
    for config in configs:
        try:
            importer_work_path = os.path.join(importers_work_path, str(idx))
            os.makedirs(importer_work_path)
            importers.append(importer_from_config(config=config, 
                                                  work_path=importer_work_path))
            idx += 1
        except (ConfigurationError, ValueError) as e:
            logger.error("Invalid importer [%s]: %s" % (config, e))
    return importers