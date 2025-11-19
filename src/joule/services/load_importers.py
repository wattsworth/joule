import logging
from typing import Dict
from joule.errors import ConfigurationError
from joule.services.helpers import load_configs, flush_directory
from joule.models.data_movement.importing.importer import Importer, importer_from_config

logger = logging.getLogger('joule')
def run(configs_path: str) -> Dict[str, Importer]:
    configs = load_configs(configs_path)
    importers = {}

    for file_path, config in configs.items():
        try:
            importer = importer_from_config(config=config)
            importers[(importer.node_name,importer.name)] = importer
        except (ConfigurationError, ValueError) as e:
            logger.error("Invalid importer [%s]: %s" % (file_path, e))
    return importers