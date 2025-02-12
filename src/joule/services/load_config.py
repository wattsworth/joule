import os
import configparser
import ipaddress
import psycopg2
import yarl
import ssl
import aiohttp
import asyncio
import logging
from joule.models import config, Proxy
from joule.errors import ConfigurationError

log = logging.getLogger('joule')
"""
# Example configuration (including optional lines)

[Main]
  Name = joule_node
  ModuleDirectory = /etc/joule/module_configs
  DataStreamDirectory = /etc/joule/stream_configs
  EventStreamDirectory = /etc/joule/event_configs
  SocketDirectory = /tmp/joule
  ImporterConfigsDirectory = /etc/joule/importer_configs
  ImporterDataDirectory = /var/run/joule/importer_data
  # ImporterInboxDirectory = /opt/joule/importer_inbox
  ImporterKey = XXXX

  ExporterConfigsDirectory = /etc/joule/exporter_configs
  ExporterDataDirectory = /var/run/joule/exporter_data
    
  UsersFile = /etc/joule/users.conf

  IPAddress = 127.0.0.1
  Port = 8088
  Database = joule:joule@localhost:5432/joule
  InsertPeriod = 5
  CleanupPeriod = 60
  MaxLogLines = 100
[Security]
   Certificate =  /etc/joule/security/server.crt
   Key = /etc/joule/security/server.key
   CertificateAuthority = /etc/joule/security/ca.crt
[Proxies]
  site1 = http://localhost:3000
  site2 = https://othersite.com
"""


def run(custom_values=None, verify=True) -> config.JouleConfig:
    """provide a dict INI configuration to override defaults
       if verify is True, perform checks on settings to make sure they are appropriate"""
    my_configs = configparser.ConfigParser()
    my_configs.read_dict(config.DEFAULT_CONFIG)
    if custom_values is not None:
        my_configs.read_dict(custom_values)

    main_config = my_configs['Main']
    # Node name
    node_name = main_config['Name']

    # Make sure mandatory directories exist
    if verify:
        for config_name in ['ModuleDirectory', 'DataStreamDirectory', 'EventStreamDirectory',
                       'ImporterConfigsDirectory','ImporterDataDirectory',
                       'ExporterConfigsDirectory','ExporterDataDirectory']:
            directory = main_config.get(config_name, None)
            if directory is None:
                raise ConfigurationError("Missing [%s] configuration" % config_name)
            if not os.path.isdir(directory):
                raise ConfigurationError("Invalid [%s] configuration" % config_name)
    
    # Specify IPAddress and Port to listen on network interface
    # IPAddress
    if 'IPAddress' in main_config:
        ip_address = main_config['IPAddress']
        try:
            ipaddress.ip_address(ip_address)
        except ValueError as e:
            raise ConfigurationError("IPAddress is invalid") from e
        # Port
        try:
            port = int(main_config['Port'])
            if port < 0 or port > 65535:
                raise ValueError()
        except ValueError as e:
            raise ConfigurationError("Port must be between 0 - 65535") from e
    else:
        port = None
        ip_address = None

    # SocketDirectory
    socket_directory = main_config['SocketDirectory']
    if not os.path.isdir(socket_directory) and verify:
        try:
            os.mkdir(socket_directory)
            # make sure the ownership is correct
            os.chmod(socket_directory, 0o750)
        except FileExistsError:
            raise ConfigurationError("SocketDirectory [%s] is a file" % socket_directory)
        except PermissionError:
            raise ConfigurationError("Cannot create SocketDirectory at [%s]" % socket_directory)

    if not os.access(socket_directory, os.W_OK) and verify:
        raise ConfigurationError(
            "SocketDirectory [%s] is not writable" % socket_directory)

    # Database
    if 'Database' in main_config:
        database = "postgresql://" + main_config['Database']
    elif verify:
        raise ConfigurationError("Missing [Database] configuration")
    else:  
        database = ''  # this is invalid of course, just used in unit testing
    if verify:
        # check to see if this is a valid database DSN
        try:
            conn = psycopg2.connect(database)
            conn.close()
        except psycopg2.Error:
            raise ConfigurationError("Cannot connect to database [%s]" % database)

    # InsertPeriod
    try:
        insert_period = int(main_config['InsertPeriod'])
        if insert_period <= 0:
            raise ValueError()
    except ValueError:
        raise ConfigurationError("InsertPeriod must be a postive number")

    # CleanupPeriod
    try:
        cleanup_period = int(main_config['CleanupPeriod'])
        if cleanup_period <= 0 or cleanup_period < insert_period:
            raise ValueError()
    except ValueError:
        raise ConfigurationError("CleanupPeriod must be a postive number > InsertPeriod")

    # Max Log Lines
    try:
        max_log_lines = int(main_config['MaxLogLines'])
        if max_log_lines <= 0:
            raise ValueError()
    except ValueError:
        raise ConfigurationError("MaxLogLines must be a postive number")

    # Authorized Users File
    users_file = None
    if 'UsersFile' in main_config:
        users_file = main_config['UsersFile']
        if not os.path.isfile(users_file) and verify:
            raise ConfigurationError(
                "UsersFile [%s] does not exist" % users_file)

    # Importer Inbox Directory (accept local archive files)
    importer_inbox_directory = None
    if 'ImporterInboxDirectory' in main_config:
        importer_inbox_directory = main_config['ImporterInboxDirectory']
        if not os.path.isdir(importer_inbox_directory) and verify:
            raise ConfigurationError("ImporterInboxDirectory [%s] does not exist" % importer_inbox_directory)
    
    # Importer Key
    importer_api_key = main_config.get('ImporterKey', None)
    if importer_api_key is None:
        log.warning("No ImporterKey specified, API access for data import will be disabled")

    # Security configuration
    if 'Security' in my_configs:
        security = config.SecurityConfig(my_configs['Security']['Certificate'],
                                         my_configs['Security']['Key'],
                                         my_configs.get('Security',
                                                        'CertificateAuthority', fallback=""))
    else:
        security = None

    # Proxies
    uuid = 0
    proxies = []
    if 'Proxies' in my_configs:
        for name in my_configs['Proxies']:
            url_str = my_configs['Proxies'][name]
            # make sure proxy url ends with /
            if url_str[-1] != '/':
                url_str += '/'
            url = yarl.URL(url_str)
            proxies.append(Proxy(name, uuid, url))
            uuid += 1

    return config.JouleConfig(
        name=node_name,
        module_directory=main_config['ModuleDirectory'],
        stream_directory=main_config['DataStreamDirectory'],
        event_directory = main_config['EventStreamDirectory'],
        importer_configs_directory=main_config['ImporterConfigsDirectory'],
        exporter_configs_directory=main_config['ExporterConfigsDirectory'],
        importer_data_directory=main_config.get('ImporterDataDirectory',"/var/run/joule/importer_data"),
        exporter_data_directory=main_config.get('ExporterDataDirectory',"/var/run/joule/exporter_data"),
        importer_inbox_directory=importer_inbox_directory,
        importer_api_key = importer_api_key,
        ip_address=ip_address,
        port=port,
        socket_directory=socket_directory,
        database=database,
        insert_period=insert_period,
        cleanup_period=cleanup_period,
        max_log_lines=max_log_lines,
        proxies=proxies,
        security=security,
        users_file=users_file
    )
