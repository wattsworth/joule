import click
import os
import shutil
import subprocess
from typing import Tuple
from OpenSSL import crypto
import secrets


@click.command(name="initialize")
@click.option("--dsn", help="PostgreSQL DSN", required=True)
def admin_initialize(dsn):  # pragma: no cover
    import pkg_resources
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
        shutil.copy(service_file, "/etc/systemd/system")
        subprocess.run("systemctl enable joule.service".split(" "), stderr=subprocess.PIPE)
        subprocess.run("systemctl start joule.service".split(" "), stderr=subprocess.PIPE)
    except PermissionError:
        _run_as_root()

    click.echo("[" + click.style("OK", fg="green") + "]")

    click.echo("3. copying configuration to /etc/joule ", nl=False)
    _make_joule_directory("/etc/joule")
    # check if main.conf exists
    if not os.path.isfile("/etc/joule/main.conf"):
        conf_template = pkg_resources.resource_filename(
            "joule", "resources/templates/main.conf")
        with open(conf_template, 'r') as template:
            with open("/etc/joule/main.conf", 'w') as conf:
                line = template.readline()
                while line:
                    if "REPLACE_WITH_DSN" in line:
                        conf.write("Database = %s\n" % dsn)
                    else:
                        conf.write(line)
                    line = template.readline()

    # set ownership to joule user
    shutil.chown("/etc/joule/main.conf", user="root", group="joule")
    # only root can write, and only joule members can read
    os.chmod("/etc/joule/main.conf", 0o640)

    # setup stream config directory
    _make_joule_directory("/etc/joule/stream_configs")
    example_file = pkg_resources.resource_filename(
        "joule", "resources/templates/stream.example")
    shutil.copy(example_file, "/etc/joule/stream_configs")
    # set ownership to joule user
    shutil.chown("/etc/joule/stream_configs/stream.example",
                 user="joule", group="joule")

    # setup module config directory
    _make_joule_directory("/etc/joule/module_configs")
    example_file = pkg_resources.resource_filename(
        "joule", "resources/templates/module.example")
    shutil.copy(example_file, "/etc/joule/module_configs")
    # set ownership to joule user
    shutil.chown("/etc/joule/module_configs/module.example",
                 user="joule", group="joule")
    click.echo("[" + click.style("OK", fg="green") + "]")

    click.echo("4. creating SSL keys and certificates", nl=False)
    SECURITY_FOLDER = "/etc/joule/security"
    _make_joule_directory(SECURITY_FOLDER)
    shutil.chown(SECURITY_FOLDER, user="root", group="joule")
    os.chmod(SECURITY_FOLDER, 0o750)
    # check if a certificate file exists
    CERT_PATH = os.path.join(SECURITY_FOLDER, "server.crt")
    KEY_PATH = os.path.join(SECURITY_FOLDER, "server.key")
    if not os.path.isfile(KEY_PATH):
        cert, key = _self_signed_cert("joule_node")
        with open(CERT_PATH, "wb") as f:
            f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
        with open(KEY_PATH, "wb") as f:
            f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))
        shutil.chown(CERT_PATH, user="root", group="joule")
        os.chmod(CERT_PATH, 0o640)
        shutil.chown(KEY_PATH, user="root", group="joule")
        os.chmod(KEY_PATH, 0o640)
        click.echo(" [" + click.style("OK", fg="green") + "]")
    else:
        click.echo(" [" + click.style("EXISTS", fg="yellow") + "]")


def _make_joule_directory(path):  # pragma: no cover
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


def _run_as_root():  # pragma: no cover
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
