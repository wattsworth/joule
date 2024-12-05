import logging
from typing import List
from joule.errors import ConfigurationError

from joule.services.helpers import (Configurations,
                                    load_configs)
from joule.models.exporter import Exporter, exporter_from_config

logger = logging.getLogger('joule')
def run(path: str) -> List[Exporter]:
    configs = load_configs(path)
    for config in configs:
        try:
            exporter = exporter_from_config(config)
        except (ConfigurationError, ValueError) as e:
            logger.error("Invalid data stream [%s]: %s" % (config, e))