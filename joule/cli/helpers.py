from typing import Dict
import requests
import os
import json

from joule.errors import ConnectionError


class NodeConfig:
    def __init__(self, name, url, key):
        self.name = name
        self.url = url
        self.key = key

    def to_json(self):
        return {
            "name": self.name,
            "url": self.url,
            "key": self.key
        }


def get_node_configs() -> Dict[str, NodeConfig]:
    node_configs = {}
    config_dir = _user_config_dir()
    nodes_path = os.path.join(config_dir, "nodes.json")

    # if nodes.json does not exist try to create it

    try:
        with open(nodes_path, 'r')as f:
            nodes = json.load(f)
        for node in nodes:
            node_configs[node['name']] = NodeConfig(node['name'],
                                                    node['url'],
                                                    node['key'])
    except FileNotFoundError:
        node_configs = {}
    except json.decoder.JSONDecodeError:
        raise ValueError("Cannot parse [%s], fix syntax or remove it" % nodes_path)

    return node_configs


def get_default_node(configs: Dict[str, NodeConfig]) -> NodeConfig:
    # if default_node.txt is empty or does not exist set it
    # to the first entry in nodes
    config_dir = _user_config_dir()
    default_node_path = os.path.join(config_dir, "default_node.txt")
    # Case 1: No nodes in nodes.json
    if len(configs) == 0:
        # no nodes, remove the default
        with open(default_node_path, 'w') as f:
            f.write("")
        os.chmod(default_node_path, 0o600)
        raise ValueError("No nodes available, use [joule admin authorize] or [joule master add] to add a node")
    # Case 2: default_node.txt does not exist
    if not os.path.isfile(default_node_path):
        with open(default_node_path, 'w') as f:
            first_name = list(configs.keys())[0]
            f.write(first_name + "\n")
        os.chmod(default_node_path, 0o600)
        return configs[first_name]

    # Case 3: Default is not in the nodes.json file
    with open(default_node_path, 'r') as f:
        name = f.readline().strip()
    if name not in configs:
        raise ValueError("Invalid default node [%s], use [joule node default] to change" % name)

    # OK, return the default node
    return configs[name]


def get_cafile():
    config_dir = _user_config_dir()
    cafile = os.path.join(config_dir, "ca.crt")
    if os.path.isfile(cafile):
        return cafile
    else:
        return ""


def write_node_configs(node_configs: Dict[str, NodeConfig]):
    config_dir = _user_config_dir()
    nodes_path = os.path.join(config_dir, "nodes.json")
    default_node_path = os.path.join(config_dir, "default_node.txt")

    # write out the key into nodes.json
    with open(nodes_path, "w") as f:
        json_val = [n.to_json() for n in node_configs.values()]
        json.dump(json_val, f, indent=2)
    os.chmod(nodes_path, 0o600)

    # if the default file is missing or empty, add a node as the default
    if not os.path.isfile(default_node_path):
        with open(default_node_path, 'w') as f:
            f.write("")
    with open(default_node_path, 'r') as f:
        name = f.readline()
    if name == "":
        with open(default_node_path, 'w') as f:
            first_name = list(node_configs.keys())[0]
            f.write(first_name + "\n")
    os.chmod(default_node_path, 0o600)


def set_default_node(name: str):
    config_dir = _user_config_dir()
    default_node_path = os.path.join(config_dir, "default_node.txt")

    node_configs = get_node_configs()
    if name not in node_configs.keys():
        raise ValueError("Invalid node name, view nodes with [joule node list]")
    with open(default_node_path, 'w') as f:
        f.write(name + "\n")


def set_config_owner(uid: int, gid: int):
    config_dir = _user_config_dir()
    os.chown(config_dir, uid, gid)
    nodes_path = os.path.join(config_dir, "nodes.json")
    os.chown(nodes_path, uid, gid)
    default_node_path = os.path.join(config_dir, "default_node.txt")
    os.chown(default_node_path, uid, gid)


def _user_config_dir() -> str:
    # return path to user config directory
    # create it if it doesn't exist
    if "JOULE_USER_CONFIG_DIR" in os.environ:
        config_dir = os.environ["JOULE_USER_CONFIG_DIR"]
    else:
        config_dir = os.path.join(os.environ["HOME"], ".joule")
    if not os.path.isdir(config_dir):
        os.mkdir(config_dir, mode=0o700)
    return config_dir


# NOTE: These are only used by the copy command!

def get(url: str, params=None) -> requests.Response:
    try:
        return requests.get(url, params=params)
    # this method is used by data copy to check if the destination
    # stream is available, any connection errors should be caught by
    # the check for the source stream which occurs first
    except requests.ConnectionError:  # pragma: no cover
        msg = "Cannot contact Joule server at [%s]" % url
        raise ConnectionError(msg)


def get_json(url: str, params=None) -> Dict:
    try:
        resp = requests.get(url, params=params)
    except requests.ConnectionError as e:
        raise ConnectionError("Cannot contact Joule server at [%s]" % url) from e
    if resp.status_code != 200:
        raise ConnectionError("%s [%d]: %s" % (url,
                                               resp.status_code,
                                               resp.text))
    try:
        data = resp.json()
        return data
    except ValueError as e:
        raise ConnectionError("Invalid server response, check the URL") from e
