import click
import os
import configparser
import json

import joule.errors
from joule.cli.helpers import (get_node_configs, NodeConfig,
                               write_node_configs, set_config_owner)


@click.command(name="authorize")
@click.option("-c", "--config", help="main configuration file", default="/etc/joule/main.conf")
def admin_authorize(config):
    # expensive imports so only execute if the function is called
    from joule.services import load_config
    from joule.models import (Base, master)
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    parser = configparser.ConfigParser()

    # load the Joule configuration file
    try:
        with open(config, 'r') as f:
            parser.read_file(f, config)
            config = load_config.run(custom_values=parser)
    except FileNotFoundError:
        raise click.ClickException("Cannot load joule configuration file at [%s]" % config)
    except PermissionError:
        raise click.ClickException("Cannot read joule configuration file at [%s] (run as root)" % config)
    except joule.errors.ConfigurationError as e:
        raise click.ClickException("Invalid configuration: %s" % e)

    # create a connection to the database
    engine = create_engine(config.database)
    Base.metadata.create_all(engine)
    db = Session(bind=engine)

    if 'SUDO_USER' in os.environ:
        username = os.environ["SUDO_USER"]
    else:
        username = os.environ["LOGNAME"]

    try:
        node_configs = get_node_configs()
    except ValueError as e:
        raise click.ClickException(str(e))

    # check if this node is already authorized
    names = [n.name for n in node_configs.values()]
    if config.name in names:
        raise click.ClickException("[%s] is already authorized for [%s]" % (
            config.name, username))

    # check if this name is associated with a master entry
    my_master = db.query(master.Master). \
        filter(master.Master.TYPE == master.Master.TYPE.USER). \
        filter(master.Master.name == username).first()
    if my_master is None:
        # create a new master entry
        my_master = master.Master()
        my_master.key = master.make_key()
        my_master.type = master.Master.TYPE.USER
        my_master.name = username
        db.add(my_master)

    # add the key data to nodes.json
    if config.ip_address != "0.0.0.0":
        addr = config.ip_address
    else:
        addr = "127.0.0.1"
    if config.ssl_context is None:
        scheme = "http"
    else:
        scheme = "https"
    location = "%s://%s:%d" % (scheme, addr, config.port)
    node_config = NodeConfig(config.name, location, my_master.key)
    node_configs[config.name] = node_config

    write_node_configs(node_configs)
    # fix permissions since this was run by root
    if 'SUDO_USER' in os.environ:
        uid = int(os.environ["SUDO_UID"])
        gid = int(os.environ["SUDO_GID"])
        set_config_owner(uid, gid)

    # save the database entry now that everything is written out
    db.commit()
    db.close()

    click.echo("Access to node [%s] granted to user [%s]" % (
        config.name, username))
