"""
Default settings
"""

import configparser

config_file="""
[main]
InputModuleDir /etc/joule/modules
"""

config = configparser.ConfigParser(config_file)

