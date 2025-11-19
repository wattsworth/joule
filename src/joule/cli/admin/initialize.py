import click
import os
import shutil
import subprocess
from typing import Tuple
from OpenSSL import crypto
from jinja2 import Environment, FileSystemLoader
from joule import constants
import secrets


@click.command(name="initialize")
@click.option("--dsn", help="PostgreSQL DSN", required=True)
@click.option("--bind", help="IP address (0.0.0.0 for all)")
@click.option("--port", help="TCP port (default is 8080)")
@click.option("--name", help="Node name (default is random)")
@click.option("--generate-user-file", help="Create file for dynamically managing users", is_flag=True)
def admin_initialize(dsn, bind, port, name, generate_user_file):
    """Run initial system configuration."""
    import pkg_resources

    # check arguments
    if bind is None and port is not None:
        raise click.ClickException("Must specify bind address with port")
    if bind is not None and port is None:
        port = "8080"
    if name is None:
        name = f"node_{secrets.token_hex(2)}"
    click.echo("1. creating joule user ", nl=False)
    proc = subprocess.run("useradd -r -G dialout joule".split(" "), stderr=subprocess.PIPE)
    if proc.returncode == 0:
        click.echo("[" + click.style("OK", fg="green") + "]")
    elif proc.returncode == 1:
        _run_as_root()
    elif proc.returncode == 9:
        click.secho("[" + click.style("EXISTS", fg='yellow') + "]")
    else:
        click.echo("[" + click.style("ERROR", fg='red') + "]\n unknown error [%d] see [man useradd]" % proc.returncode)
        exit(1)
    click.echo("2. registering system service ", nl=False)
    service_file = pkg_resources.resource_filename(
        "joule", "resources/joule.service")
    try:
        # don't overwrite existing service file
        if not os.path.exists("/etc/systemd/system/joule.service"):
            shutil.copy(service_file, "/etc/systemd/system")
        subprocess.run("systemctl enable joule.service".split(" "), stderr=subprocess.PIPE)
        subprocess.run("systemctl start joule.service".split(" "), stderr=subprocess.PIPE)
    except PermissionError:
        _run_as_root()

    click.echo("[" + click.style("OK", fg="green") + "]")

    click.echo("3. copying configuration to /etc/joule ", nl=False)
    _make_joule_directory("/etc/joule")
    # check if main.conf exists
    if not os.path.isfile(constants.ConfigFiles.main_config):
        template_path = pkg_resources.resource_filename(
            "joule", "resources/templates")
        # From https://stackoverflow.com/questions/11857530
        env = Environment(loader=FileSystemLoader(template_path), autoescape=True)
        env.trim_blocks = True
        env.lstrip_blocks = True
        env.keep_trailing_newline = True
        template = env.get_template('main.conf.jinja2')
        file_contents = template.render(name=name,
                                        bind=bind,
                                        port=port,
                                        dsn=dsn,
                                        importer_key = secrets.token_hex(16),
                                        generate_user_file=generate_user_file)
        with open(constants.ConfigFiles.main_config, 'w') as conf:
            conf.write(file_contents)
    
    # set ownership to root and joule group
    shutil.chown(constants.ConfigFiles.main_config, user="root", group="joule")
    # only root can write, and only joule members can read
    os.chmod(constants.ConfigFiles.main_config, 0o640)

    # create the configuration subfolders and populate with example configs
    items = [('module_configs', 'module.example'),
             ('data_stream_configs', 'data_stream.example'),
             ('event_stream_configs', 'event_stream.example'),
             ('importer_configs', 'importer.example'),
             ('exporter_configs', 'exporter.example')]
    for path, example in items:
        _make_joule_directory(f"/etc/joule/{path}")
        example_file = pkg_resources.resource_filename(
            "joule", f"resources/templates/{example}")
        shutil.copy(example_file, f"/etc/joule/{path}")
        # set ownership to joule user
        shutil.chown(f"/etc/joule/{path}/{example}", user="joule", group="joule")

    # create the data directories for importer and exporter
    _make_joule_directory("/var/run/joule/importer_data")
    _make_joule_directory("/var/run/joule/exporter_data")
    _make_joule_directory("/var/run/joule/importer_inbox")
    shutil.chown("/var/run/joule/importer_data", user="joule", group="joule")
    shutil.chown("/var/run/joule/exporter_data", user="joule", group="joule")
    
    # setup user file if configured
    if generate_user_file and not os.path.isfile("/etc/joule/users.conf"):
        user_file = pkg_resources.resource_filename(
            "joule", "resources/templates/users.conf")
        shutil.copy(user_file, "/etc/joule/users.conf")
        # set ownership to root and joule group
        shutil.chown(constants.ConfigFiles.main_config, user="root", group="joule")
        # only root can write, and only joule members can read
        os.chmod(constants.ConfigFiles.main_config, 0o640)

    click.echo("[" + click.style("OK", fg="green") + "]")


def _make_joule_directory(path):  
    try:
        if os.path.isfile(path):
            click.echo("\n " + click.style("ERROR", fg='red') +
                       " cannot create directory [%s], a file exists with the same name" % path)
            exit(1)
        # check if directory exists
        if not os.path.isdir(path):
            os.makedirs(path)
        # set ownership to joule user
        shutil.chown(path, user="joule", group="joule")
    except PermissionError:
        _run_as_root()


def _run_as_root():  
    click.echo("[" + click.style("ERROR", fg="red") + "]\n run as [sudo joule initialize]")
    exit(1)


def _self_signed_cert(cn: str) -> Tuple[crypto.X509, crypto.PKey]:
    # generate a key
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 2048)
    # generate a self signed certificate

    cert = crypto.X509()
    cert.get_subject().CN = cn
    cert.set_serial_number(secrets.randbits(128))
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(5 * 365 * 24 * 60 * 60)  # 5 years
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, 'sha256')
    return cert, k
