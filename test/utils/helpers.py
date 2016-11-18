import configparser




def parse_configs(config_str):
  config = configparser.ConfigParser()
  config.read_string(config_str)
  return config

default_config = parse_configs(
      """
        [NilmDB]:
          URL = http://localhost/nilmdb
          InsertionPeriod = 5
        [ProcDB]:
          DbPath = /tmp/joule-proc-db.sqlite
          MaxLogLines = 100
        [Jouled]:
          ModuleDirectory = /etc/joule/module_configs
          StreamDirectory = /etc/joule/stream_configs
    """)
