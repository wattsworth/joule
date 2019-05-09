#!/usr/bin/python3

"""
Run the configuration in follower
"""
import os
import sys
import subprocess
import time
import shlex
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from joule.models import Base, master
SOURCE_DIR = "/joule"
MODULE_SCRIPT_DIR = "/joule/tests/e2e/module_scripts"
JOULE_CONF_DIR = "/joule/tests/e2e/follower"

FORCE_DUMP = False
MASTER_KEY = "gPSGE1EIbKuu2G9_AYnYLZ2I2pqZlfSRMrILpS0R4EA"

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
    subprocess.run(("joule admin authorize --config %s" % config_file).split(" "))


    jouled = subprocess.Popen(["jouled", "--config",
                               config_file],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,
                              universal_newlines=True)
    time.sleep(2)
    subprocess.run("joule master add joule node1.joule".split(" "))
    stdout, _ = jouled.communicate()
    for line in stdout.rstrip().split('\n'):
        print("> %s" % line)


    return 0  # success


if __name__ == "__main__":
    exit(main())
