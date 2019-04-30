import click

from joule import api


class Config:
    def __init__(self):
        self._node: api.BaseNode = None
        self.name = ""

    def set_node_name(self, name):
        self.name = name

    @property
    def node(self):
        # lazy node construction, raise error if it cannot be created
        if self._node is None:
            self._node = api.get_node(self.name)
            click.echo("--connecting to [%s]--" % self._node.name)
            self.name = self._node.name
        return self._node


pass_config = click.make_pass_decorator(Config, ensure=True)
