import click
import os
import configparser
import json

import joule.errors


@click.command(name="authorize-local-user")
@click.option("-c", "--config", help="main configuration file", default="/etc/joule/main.conf")
def cmd(config_file):
    # expensive imports so only execute if the function is called
    from joule.services import load_config
    from joule.models import (Base, master)
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    parser = configparser.ConfigParser()

    # load the Joule configuration file
    try:
        with open(config_file, 'r') as f:
            parser.read_file(f, config_file)
            config = load_config.run(custom_values=parser)
    except FileNotFoundError:
        raise click.ClickException("Cannot load joule configuration file at [%s]" % config_file)
    except PermissionError:
        raise click.ClickException("Cannot read joule configuration file at [%s] (run as root)" % config_file)
    except joule.errors.ConfigurationError as e:
        raise click.ClickException("Invalid configuration: %s" % e)

    # create a connection to the database
    engine = create_engine(config.database)
    Base.metadata.create_all(engine)
    db = Session(bind=engine)

    # check if $JOULE_USER_CONFIG is defined, if so use it
    # otherwise use $HOME/.joule
    if "JOULE_USER_CONFIG_DIR" in os.environ:
        config_dir = os.environ["JOULE_USER_CONFIG_DIR"]
    else:
        config_dir = os.path.join(os.environ["HOME"], ".joule")
    if not os.path.isdir(config_dir):
        os.mkdir(config_dir, mode=0o660)

    # check if a nodes.json file exists, if so read it
    nodes_path = os.path.join(config_dir, "nodes.json")
    try:
        if os.path.isfile(nodes_path):
            with open(nodes_path, "r") as f:
                node_data = json.load(f)
        else:
            node_data = []
    except json.decoder.JSONDecodeError:
        raise click.ClickException("Cannot parse [%s], fix syntax or remove it" % nodes_path)

    # check if this node is already authorized
    for elem in node_data:
        if elem["name"] == config.name:
            raise click.ClickException("The local node [%s] is already authorized for [%s]" % (
                config.name, os.environ["LOGNAME"]))

    # create a new master
    my_master = master.Master()
    my_master.key = master.make_key()
    my_master.type = master.Master.TYPE.USER
    my_master.name = os.environ["LOGNAME"]
    db.add(my_master)

    # add the key data to nodes.txt
    if config.ip_address != "0.0.0.0":
        addr = config.ip_address
    else:
        addr = "127.0.0.1"
    location = "%s:%d" % (addr, config.port)
    node_data.append({
        "name": config.name,
        "location": location,
        "key": my_master.key
    })

    # write out the key into nodes.json
    with open(nodes_path, "w") as f:
        json.dump(node_data, f, indent=2)

    # save the database entry now that everything is written out
    db.commit()
    db.close()

    click.echo("Access to the local node [%s] granted to user [%s]" % (
        config.name, os.environ["LOGNAME"]))
