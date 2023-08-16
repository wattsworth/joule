#!/usr/bin/python3

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

from joule import api

SOURCE_DIR = "/joule"
SCENARIO_DIR = "/joule/tests/e2e/scenarios"
MODULE_SCRIPT_DIR = "/joule/tests/e2e/module_scripts"
JOULE_CONF_DIR = "/etc/joule"
SECURITY_DIR = "/joule/tests/e2e/pki"

FORCE_DUMP = False


def prep_system():
    os.symlink(MODULE_SCRIPT_DIR, "/module_scripts")


def run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL):
    return subprocess.run(shlex.split(cmd), stdout=stdout, stderr=stderr)


async def wait_for_follower():
    # wait until the local node is online
    max_tries = 10
    num_tries = 0
    while num_tries < max_tries:
        num_tries += 1
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', 8088))
        sock.close()
        if result == 0:
            break
        time.sleep(0.5)
    if num_tries == max_tries:
        print("error, local node is not online")
        return -1

    node1 = api.get_node("node1.joule")
    while True:
        followers = await node1.follower_list()
        if len(followers) == 1:
            break
        await asyncio.sleep(0.5)
    await node1.close()
    return 0 # success

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--nilmdb", help="use nilmdb backend", action="store_true")
    args = parser.parse_args()

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


        if first_test:
            # get API permissions
            os.environ["LOGNAME"] = "e2e"
            os.environ["JOULE_USER_CONFIG_DIR"] = "/tmp/joule_user"
            with open(os.devnull, 'w') as devnull:
                subprocess.run("joule admin authorize".split(" "),
                               stdout=devnull)
            shutil.copy("/etc/joule/security/ca.joule.crt", "/tmp/joule_user/ca.crt")

        main_conf = "/etc/joule/main.conf"
        if args.nilmdb:
            # parse the main.conf file and enable nilmdb
            configs = configparser.ConfigParser()
            configs.read("/etc/joule/main.conf")
            configs["Main"]["NilmdbUrl"] = "http://nilmdb"
            (f, path) = tempfile.mkstemp()
            configs.write(os.fdopen(f, mode='w'))
            main_conf = path
        if first_test:
            jouled = subprocess.Popen(["jouled", "--config",
                                       main_conf],
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT,
                                      universal_newlines=True)

            result = asyncio.run(wait_for_follower())
            jouled.send_signal(signal.SIGINT)
            stdout, _ = jouled.communicate()
            if result != 0:
                return result

        # clear the existing database (keeping master/follower tables)
        subprocess.run("joule admin erase --yes".split(" "))
        subprocess.run("joule admin authorize".split(" "))

        jouled = subprocess.Popen(["jouled", "--config",
                                   main_conf],
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT,
                                  universal_newlines=True)
        result = asyncio.run(wait_for_follower())

        print("---------[%s]---------" % test_name)
        sys.stdout.flush()

        test = subprocess.run(os.path.join(test_path, "test.py"))
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
