import click
from .initialize import admin_initialize
from .erase import admin_erase
from .authorize import admin_authorize
from .backup import admin_backup
from .ingest import admin_ingest


@click.group(name="admin")
def admin():
    pass  # pragma: no cover


admin.add_command(admin_initialize)
admin.add_command(admin_authorize)
admin.add_command(admin_erase)
admin.add_command(admin_backup)
admin.add_command(admin_ingest)
