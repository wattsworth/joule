import click
from joule.api.session import Session


class Config:
    def __init__(self):
        self.session: Session = None


pass_config = click.make_pass_decorator(Config, ensure=True)
