#!/usr/bin/python3 -u

"""
Run through each scenario in scenarios
"""
import os
import socket
import sys
import subprocess
import shlex
import shutil
import signal
import tempfile
import asyncio
import configparser
import time
import argparse

import joule
from joule import api

SOURCE_DIR = "/joule"
SCENARIO_DIR = "/joule/tests/e2e/scenarios"
MODULE_SCRIPT_DIR = "/joule/tests/e2e/module_scripts"
JOULE_CONF_DIR = "/etc/joule"
SECURITY_DIR = "/joule/tests/e2e/pki"

JOULED_CMD ="coverage run --rcfile=/joule/.coveragerc -m joule.daemon".split(" ")
JOULE_CMD = "coverage run --rcfile=/joule/.coveragerc -m joule.cli".split(" ")

FORCE_DUMP = False


def prep_system():
    os.symlink(MODULE_SCRIPT_DIR, "/module_scripts")


def run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL):
    return subprocess.run(shlex.split(cmd), stdout=stdout, stderr=stderr)


async def wait_for_follower():
    node1 = api.get_node("node1.joule")
    while True:
        try:
            followers = await node1.follower_list()
            if len(followers) == 1:
                break
        except joule.errors.ApiError:
            # wait until node is online
            await asyncio.sleep(1)
    await node1.close()
    return 0 # success

def main():
    prep_system()
    tests = []
    for entry in os.scandir(SCENARIO_DIR):
        if not (entry.name.startswith('.') and entry.is_dir()):
            if entry.name in ["__pycache__", "__init__.py"]:
                continue
            tests.append((entry.name, entry.path))

    # override to run only particular test(s)
    # tests = [("multinodes", "/joule/tests/e2e/scenarios/multiple_node_tests")]
    # tests = [("standalone modules", "/joule/tests/e2e/scenarios/standalone_modules")]
    # tests = [("API", "/joule/tests/e2e/scenarios/api_tests")]
    # tests = [("Basic Operation", "/joule/tests/e2e/scenarios/basic_operation")]

    first_test = True
    for (test_name, test_path) in tests:
        if os.path.exists("/etc/joule/"):
            if os.path.islink("/etc/joule"):
                os.unlink("/etc/joule")  # this is a symlink
            else:
                shutil.rmtree("/etc/joule/")
        os.symlink(test_path, "/etc/joule")
        try:
            os.unlink("/etc/joule/security")
        except FileNotFoundError:
            pass
        os.symlink(SECURITY_DIR, "/etc/joule/security")

        main_conf = "/etc/joule/main.conf"

        if first_test:
            # get API permissions
            os.environ["LOGNAME"] = "e2e"
            os.environ["JOULE_USER_CONFIG_DIR"] = "/tmp/joule_user"
            with open(os.devnull, 'w') as devnull:
                subprocess.run(JOULE_CMD+"admin authorize".split(" "),
                               stdout=devnull)
            shutil.copy("/etc/joule/security/ca.joule.crt", "/tmp/joule_user/ca.crt")

        
            jouled = subprocess.Popen(JOULED_CMD+["--config", main_conf],
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT,
                                      universal_newlines=True)
            result = asyncio.run(wait_for_follower())
            jouled.send_signal(signal.SIGINT)
            stdout, _ = jouled.communicate()
            if result != 0:
                print("ERROR!")
                print(stdout)
                return result
        # clear the existing database (keeping master/follower tables)
        subprocess.run(JOULE_CMD+"admin erase --yes".split(" "))
        subprocess.run(JOULE_CMD+"admin authorize".split(" "))

        jouled = subprocess.Popen(JOULED_CMD+["--config", main_conf],
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT,
                                  universal_newlines=True)
        result = asyncio.run(wait_for_follower())

        print("---------[%s]---------" % test_name)
        sys.stdout.flush()
        test = subprocess.run(("coverage run --rcfile=/joule/.coveragerc "+os.path.join(test_path, "test.py")).split(" "))
        jouled.send_signal(signal.SIGINT)
        stdout, _ = jouled.communicate()
        if test.returncode != 0 or FORCE_DUMP:
            print("----dump from jouled----")
            for line in stdout.rstrip().split('\n'):
                print("> %s" % line)
            if test.returncode != 0:
                return test.returncode
    return 0  # success


if __name__ == "__main__":
    exit(main())
