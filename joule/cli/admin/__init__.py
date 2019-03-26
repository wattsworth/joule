import click
from .initialize import admin_initialize
from .erase import admin_erase
from .authorize import admin_authorize


@click.group(name="admin")
def admin():
    pass  # pragma: no cover


admin.add_command(admin_initialize)
admin.add_command(admin_authorize)
admin.add_command(admin_erase)
