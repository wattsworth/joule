import click
import asyncio

from joule import errors
from joule.cli.config import pass_config
from joule.api import BaseNode


@click.command(name="add")
@click.argument("type", type=click.Choice(['user', 'joule', 'lumen']))
@click.argument("identifier")
@pass_config
def cli_add(config, type, identifier):
    loop = asyncio.get_event_loop()
    try:
        if type == 'user':
            coro = _add_user(config.node, identifier)
        elif type == 'joule':
            coro = _add_node(config.node, identifier)
        elif type == 'lumen':
            coro = _add_lumen(config.node, identifier)
        else:
            raise click.ClickException("invalid type [%s]" % type)
        loop.run_until_complete(coro)
    except errors.ApiError as e:
        raise click.ClickException(str(e)) from e
    finally:
        loop.run_until_complete(
            config.close_node())
        loop.close()


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


async def _add_user(node: BaseNode, name):
    result = await node.master_add("user", name)
    click.echo("Access to node [%s] granted to user [%s]" % (node.name, name))
    click.echo("")
    click.echo("Key:\t%s" % result.key)
    click.echo("")
    click.echo("Run [joule node add] with the above values on the user's machine")
    click.echo("* IP address may differ based on network setup")
