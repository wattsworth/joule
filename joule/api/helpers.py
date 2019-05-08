import os
from typing import List, Union, Dict
import json
import logging
from asyncio import AbstractEventLoop

from joule.api.node.tcp_node import TcpNode
from joule.api.node.unix_node import UnixNode
from joule.api.node.node_config import NodeConfig
from joule import errors

from joule.api.node.base_node import BaseNode


def get_node(name: str = "") -> BaseNode:
    try:
        configs = _get_node_configs()
        if name == "":
            config = _get_default_node(configs)
        else:
            config = configs[name]
    except ValueError as e:
        raise errors.ApiError(str(e))
    except KeyError as e:
        raise errors.ApiError("Node [%s] is not available, add it with [joule master add]" % str(e))
    return TcpNode(config.name, config.url, config.key, _get_cafile())


def get_nodes() -> List[BaseNode]:
    nodes = []
    cafile = _get_cafile()
    for config in _get_node_configs().values():
        my_node = TcpNode(config.name,
                          config.url,
                          config.key,
                          cafile=cafile
                          )
        nodes.append(my_node)
    return nodes


def save_node(node: TcpNode) -> None:
    configs = _get_node_configs()
    configs[node.name] = node.to_config()
    _write_node_configs(configs)


def delete_node(node: Union[str, BaseNode]) -> None:
    configs = _get_node_configs()
    if type(node) is str:
        name = node
    else:
        name = node.name
    if name not in configs:
        raise errors.ApiError("Node [%s] does not exist" % name)
    del configs[name]
    _write_node_configs(configs)
    # if this is the default node, pick a new one
    try:
        default_config = _get_default_node(configs)
        if default_config.name == name:
            set_default_node("")
    except ValueError:
        # this was the last node, no other nodes available
        pass


def set_default_node(node: Union[str, BaseNode]) -> None:
    if type(node) is str:
        name = node
    else:
        name = node.name

    config_dir = _user_config_dir()
    default_node_path = os.path.join(config_dir, "default_node.txt")

    node_configs = _get_node_configs()
    if len(name) > 0 and name not in node_configs.keys():
        raise ValueError("Invalid node name, view nodes with [joule node list]")
    if name == "":
        if len(node_configs) == 0:
            return  # nothing to do, no nodes available
        # pick a new default node
        with open(default_node_path, 'w') as f:
            first_name = list(node_configs.keys())[0]
            f.write(first_name + "\n")
            return

    with open(default_node_path, 'w') as f:
        f.write(name + "\n")


def create_tcp_node(url: str, key: str, name: str = "node",
                    loop: AbstractEventLoop = None) -> TcpNode:
    return TcpNode(name, url, key, _get_cafile(), loop)


def create_unix_node(path: str, name: str = "node",
                     loop: AbstractEventLoop = None) -> BaseNode:
    return UnixNode(name, path, loop)


def _get_cafile():
    config_dir = _user_config_dir()
    cafile = os.path.join(config_dir, "ca.crt")
    if os.path.isfile(cafile):
        return cafile
    else:
        return ""


def _get_node_configs() -> Dict[str, NodeConfig]:
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


def _get_default_node(configs: Dict[str, NodeConfig]) -> NodeConfig:
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
        raise ValueError("No nodes available, use [joule admin authorize] or [joule node add]")
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
        # change the default node to a valid choice
        with open(default_node_path, 'w') as f:
            first_name = list(configs.keys())[0]
            f.write(first_name + "\n")
        os.chmod(default_node_path, 0o600)
        return configs[first_name]

    # OK, return the default node
    return configs[name]


def _write_node_configs(node_configs: Dict[str, NodeConfig]):
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
    _fix_config_ownership()

# save the database entry now that everything is written out


def _fix_config_ownership():
    # fix permissions if this was run by root
    if 'SUDO_USER' not in os.environ:
        return

    uid = int(os.environ["SUDO_UID"])
    gid = int(os.environ["SUDO_GID"])

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
