import configparser
from joule.utils import config_manager


def parse_config_file(f, verify=True):
    if(f is None):
        return config_manager.load_configs(verify=verify)
    else:
        configs = configparser.ConfigParser()
        configs.read(f)
        return config_manager.load_configs(configs, verify=verify)
