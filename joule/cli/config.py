import click
import os
import json
from typing import Dict
from joule.api.session import Session
from joule.cli.helpers import (get_node_configs, get_default_node)


class Config:
    def __init__(self):
        self._session: Session = None
        self.name = ""

    def set_node_name(self, name):
        self.name = name

    @property
    def session(self):
        # lazy session construction, raise error if it cannot be created
        if self._session is None:
            node_config = get_node(self.name)
            self._session = Session(node_config.url, node_config.key)
        return self._session

pass_config = click.make_pass_decorator(Config, ensure=True)


def get_node(name):
    try:
        configs = get_node_configs()
        if name == "":
            return get_default_node(configs)
    except ValueError as e:
        raise click.ClickException(str(e))
    if name not in configs:
        raise click.ClickException("Node [%s] is not available, add it with [joule master add]")
    return configs[name]
