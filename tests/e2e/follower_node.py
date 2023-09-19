#!/usr/bin/python3 -u

"""
Run the configuration in follower
"""

import os
import sys
import subprocess
import time
import shlex
import socket
import signal

SOURCE_DIR = "/joule"
MODULE_SCRIPT_DIR = "/joule/tests/e2e/module_scripts"
JOULE_CONF_DIR = "/joule/tests/e2e/follower"


def prep_system():
    os.symlink(MODULE_SCRIPT_DIR, "/module_scripts")


def run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL):
    return subprocess.run(shlex.split(cmd), stdout=stdout, stderr=stderr)


def main():
    prep_system()

    config_file = os.path.join(JOULE_CONF_DIR, "main.conf")
    subprocess.run(("joule admin erase --yes --config %s" % config_file).split(" "))

    # add a key entry for the master node
    # get API permissions
    os.environ["LOGNAME"] = "e2e"
    os.environ["JOULE_USER_CONFIG_DIR"] = "/tmp/joule_user"
    with open(os.devnull, 'w') as devnull:
        subprocess.run(("joule admin authorize --config %s" % config_file).split(" "),
                       stdout=devnull)

    jouled = subprocess.Popen(["jouled", "--config", config_file],
                              stdout=sys.stdout,
                              stderr=sys.stderr,
                              universal_newlines=True)
    time.sleep(3)
    # follow node1.joule
    subprocess.run("joule master add joule https://node1.joule:8088".split(" "))  # ,

    # this will just hang, node1 exits and terminates this container
    stdout, _ = jouled.communicate()
    print(stdout)
    print(_)
    return 0


if __name__ == "__main__":
    exit(main())
