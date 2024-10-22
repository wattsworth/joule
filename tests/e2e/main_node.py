#!/usr/bin/env -S python3 -u

"""
Run through each scenario in scenarios
"""
import os
import sys
import subprocess
import shlex
import shutil
import signal
import asyncio
from helpers import wait_for_joule_host
import joule
import time
from joule import api

SOURCE_DIR = "/joule"
SCENARIO_DIR = "/joule/tests/e2e/scenarios"
MODULE_SCRIPT_DIR = "/joule/tests/e2e/module_scripts"
JOULE_CONF_DIR = "/etc/joule"
SECURITY_DIR = "/joule/tests/e2e/pki"

JOULED_CMD ="coverage run --rcfile=/joule/.coveragerc -m joule.daemon".split(" ")
JOULE_CMD = "coverage run --rcfile=/joule/.coveragerc -m joule.cli".split(" ")

FORCE_DUMP = True


async def wait_for_follower():
    node1 = api.get_node("node1.joule")
    try_count=0
    while try_count < 5:
        try:
            followers = await node1.follower_list()
            if len(followers) == 1:
                return 0 # success
        except joule.errors.ApiError:
            # wait until node is online
            await asyncio.sleep(1)
        finally:
            await node1.close()
    raise Exception("follower did not connect within 5 seconds")


def main():
    tests = []
    for entry in os.scandir(SCENARIO_DIR):
        if not (entry.name.startswith('.') and entry.is_dir()):
            if entry.name in ["__pycache__", "__init__.py"]:
                continue
            tests.append((entry.name, entry.path))

    # override to run only particular test(s)
    # tests = [("multinodes", "/joule/tests/e2e/scenarios/multiple_nodes")]
    # tests = [("standalone modules", "/joule/tests/e2e/scenarios/standalone_modules")]
    # tests = [("API", "/joule/tests/e2e/scenarios/api_tests")]
    # tests = [("Basic Operation", "/joule/tests/e2e/scenarios/basic_operation")]
    # tests = [("Data Management", "/joule/tests/e2e/scenarios/data_management")]
    # tests = [("Quick Start Pipeline", "/joule/tests/e2e/scenarios/quick_start_pipeline")]

    # make module scripts available
    os.symlink(MODULE_SCRIPT_DIR, "/module_scripts")

    # get API permissions
    os.environ["LOGNAME"] = "e2e"
    os.environ["JOULE_USER_CONFIG_DIR"] = "/tmp/joule_user"

    # wait for the follower to connect
    jouled = subprocess.Popen(JOULED_CMD,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT,
                                    universal_newlines=True)
    time.sleep(2) # wait for jouled to start

    ## The main node tests out the NGinx proxy functionality (follower uses built-in HTTP server)
    subprocess.run(JOULE_CMD+"admin authorize --url=http://localhost/joule".split(" "))
    wait_for_joule_host('node1.joule')
    asyncio.run(wait_for_follower())
    jouled.send_signal(signal.SIGINT)
            
    for (test_name, test_path) in tests:
        print("---------[%s]---------" % test_name)
        # remove the contents of /etc/joule/module_configs and replace with this test's configs
        shutil.rmtree("/etc/joule/module_configs")
        shutil.rmtree("/etc/joule/stream_configs")
        shutil.copytree(os.path.join(test_path, "module_configs"), "/etc/joule/module_configs")
        shutil.copytree(os.path.join(test_path, "stream_configs"), "/etc/joule/stream_configs")

        # clear the existing database (keeping master/follower tables)
        with open(os.devnull, 'w') as devnull:
            subprocess.run(JOULE_CMD+"admin erase --yes".split(" "), stdout=devnull)

        # start jouled
        jouled = subprocess.Popen(JOULED_CMD,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT,
                                  universal_newlines=True)
        wait_for_joule_host('node1.joule')
        time.sleep(15)  # wait for jouled to boot and collect data

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
