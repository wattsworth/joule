import configparser
from joule.models import config


def parse_config_file(f, verify=True):
    if(f is None):
        return config.load_configs(verify=verify)
    else:
        configs = configparser.ConfigParser()
        configs.read(f)
        return config.load_configs(configs, verify=verify)
