import click
import os
import configparser
import requests
from joule import api, errors


@click.command(name="authorize")
@click.option("-c", "--config", help="main configuration file", default="/etc/joule/main.conf")
@click.option("-u", "--url", help="joule API URL (optional)")
def admin_authorize(config, url):
    """Grant a local user CLI access."""
    # expensive imports so only execute if the function is called
    from joule.services import load_config
    from joule.models import (Base, master)
    from sqlalchemy import create_engine, text
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
    except errors.ConfigurationError as e:
        raise click.ClickException("Invalid configuration: %s" % e)

    # create a connection to the database
    engine = create_engine(config.database)
    with engine.connect() as conn:
        with conn.begin():
            conn.execute(text('CREATE SCHEMA IF NOT EXISTS data'))
            conn.execute(text('CREATE SCHEMA IF NOT EXISTS metadata'))

    Base.metadata.create_all(engine)
    db = Session(bind=engine)

    if 'SUDO_USER' in os.environ:
        username = os.environ["SUDO_USER"]
    else:
        username = os.environ["LOGNAME"]

    try:
        nodes = api.get_nodes()
    except ValueError as e:
        raise click.ClickException(str(e))

    # check if this name is associated with a master entry
    my_master = db.query(master.Master). \
        filter(master.Master.type == master.Master.TYPE.USER). \
        filter(master.Master.name == username).first()
    if my_master is None:
        # create a new master entry
        my_master = master.Master()
        my_master.key = master.make_key()
        my_master.type = master.Master.TYPE.USER
        my_master.name = username
        db.add(my_master)

    # if a URL is specified use it
    if url is not None:
        joule_url = url
    # if the Joule server is not hosting a TCP server try to
    # determine the proxy address, show an error if it cannot be found
    elif config.ip_address is None:
        joule_url = "https://localhost/joule"
        # try to get this page, if it fails then try again using http
        try:
            r = requests.get(joule_url, verify=False)
            # make sure the response is a 403 forbidden
            if r.status_code != 403:
                raise requests.exceptions.ConnectionError()
        except requests.exceptions.ConnectionError:
            joule_url = "http://localhost/joule"
            try:
                r = requests.get(joule_url, verify=False)
            # make sure the response is a 403 forbidden
                if r.status_code != 403:
                    raise requests.exceptions.ConnectionError()
            except requests.exceptions.ConnectionError:
                raise click.ClickException("Cannot determine Joule URL, please specify with --url")
    # otherwise use the server information in the config file
    else:
        if config.security is not None and config.security.cafile != "":
            addr = config.name
        elif config.ip_address != "0.0.0.0":
            addr = config.ip_address
        else:
            addr = "127.0.0.1"

        if config.security is None:
            scheme = "http"
        else:
            scheme = "https"
        joule_url = "%s://%s:%d" % (scheme, addr, config.port)
    my_node = api.create_tcp_node(joule_url, my_master.key, config.name)
    api.save_node(my_node)

    db.commit()
    db.close()

    click.echo("Access to node [%s] granted to user [%s]" % (
        config.name, username))
