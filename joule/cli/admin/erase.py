import click
import asyncio

from joule.cli.config import pass_config


@click.command(name="erase")
@click.option("-c", "--config", help="main configuration file", default="/etc/joule/main.conf")
@pass_config
def admin_erase(config):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run(config))
    loop.close()


async def run(config):
    # --- DANGEROUS: COMPLETELY WIPE THE NODE ---
    try:
        await self.data_store.initialize([])
    except DataError as e:
        log.error("Database error: %s" % e)
        print("aborted")
        exit(1)
    # erase data
    await self.data_store.destroy_all()
    # erase metadata
    self.db.query(Element).delete()
    self.db.query(Stream).delete()
    self.db.query(Folder).delete()
    self.db.commit()