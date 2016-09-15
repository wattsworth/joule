import configparser

def parse_configs(config_str):
        config = configparser.ConfigParser()
        config.read_string(config_str)
        return config
