import click
import asyncio

from joule import errors
from joule.cli.config import pass_config
from joule.api import BaseNode


@click.command(name="add")
@click.argument("type", type=click.Choice(['user', 'joule', 'lumen']))  # , help="type of master")
@click.argument("identifier")  # help="username or URL for joule/lumen masters")
@click.option('-k', "--key", help="desired API key, must be 32 characters, omit for a random key")
@pass_config
def cli_add(config, type, identifier, key):
    """Authorize a new node master.

    For users specify a username (for documentation only).
    For joule/lumen masters specify an domain name or IP address. If the master node is not
    hosted at the default location, specify the full URL."""
    try:
        if type == 'user':
            coro = _add_user(config.node, identifier, key)
        elif type == 'joule':
            coro = _add_node(config.node, identifier)
        elif type == 'lumen':
            coro = _add_lumen(config.node, identifier)
        else:
            raise click.ClickException("invalid type [%s]" % type)
        asyncio.run(coro)
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        asyncio.run(
            config.close_node())
        


async def _add_lumen(node: BaseNode, host):
    # add the node and see what error comes back
    req_credentials = "unset"
    try:
        await node.master_add("lumen", host, {})
    except errors.ApiError as e:
        if "auth_key" in str(e):
            req_credentials = "key"
        elif "first_name" in str(e):
            req_credentials = "user"
        else:
            raise e
    if req_credentials == "unset":
        raise errors.ApiError("Lumen node did not specify required credentials")
    lumen_params = {}
    if req_credentials == "key":
        key = click.prompt("Lumen authorization key")
        lumen_params = {"auth_key": key}
    else:
        click.echo("This a new Lumen instance, create a user account")
        first_name = click.prompt("First Name")
        last_name = click.prompt("Last Name")
        email = click.prompt("E-mail")
        password = click.prompt("Password", hide_input=True, confirmation_prompt=True)
        lumen_params = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "password": password}
    await node.master_add("lumen", host, lumen_params)
    click.echo("Access to [%s] granted to Lumen Node [%s]" % (node.name, host))
    if req_credentials == "user":
        click.echo("Log into the Lumen server using your e-mail and password")


async def _add_node(node: BaseNode, host):
    result = await node.master_add("joule", host)
    click.echo("Access to [%s] granted to Joule Node [%s]" % (node.name, result.name))


async def _add_user(node: BaseNode, name, key):
    result = await node.master_add("user", name, None, key)
    click.echo("Access to node [%s] granted to user [%s]" % (node.name, name))
    click.echo("")
    click.echo("Key:\t%s" % result.key)
    click.echo("")
    click.echo("Run the following command to install the key on the user's machine")
    click.echo("\t$> joule node add %s %s %s" % (node.name, node.url, result.key))
    click.echo("* IP address may differ based on network setup")
