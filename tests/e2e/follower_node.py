#!/usr/bin/env -S python3 -u

"""
Run the configuration in follower
"""

import os
import sys
import subprocess
import shutil
from helpers import wait_for_joule_host
SOURCE_DIR = "/joule"
MODULE_SCRIPT_DIR = "/joule/tests/e2e/module_scripts"
JOULE_CONF_DIR = "/joule/tests/e2e/follower"
JOULE_CMD = "coverage run --rcfile=/joule/.coveragerc -m joule.cli".split(" ")



def main():
    subprocess.run(("joule admin erase --yes").split(" "))

    # make module scripts available
    os.symlink(MODULE_SCRIPT_DIR, "/module_scripts")

    # get API permissions
    os.environ["LOGNAME"] = "e2e"
    os.environ["JOULE_USER_CONFIG_DIR"] = "/tmp/joule_user"
    
    # copy module configurations (no stream configs)
    shutil.rmtree("/etc/joule/module_configs")
    shutil.copytree(os.path.join(JOULE_CONF_DIR, "module_configs"), "/etc/joule/module_configs")

    jouled = subprocess.Popen("jouled",
                              stdout=sys.stdout,
                              stderr=sys.stderr,
                              universal_newlines=True)
    
    ## The follower tests out the built-in HTTP server
    wait_for_joule_host('node2.joule', port=8080)

    subprocess.run(JOULE_CMD+"admin authorize".split(" "))

    # follow node1.joule
    wait_for_joule_host('node1.joule')
    result = subprocess.run("joule master add joule http://node1.joule/joule".split(" "))  # ,
    if result.returncode != 0:
        print("ERROR: failed to add master node")
        jouled.send_signal(subprocess.signal.SIGINT)

    # this will just hang, node1 exits and terminates this container
    stdout, stderr = jouled.communicate()
    print("---- jouled stdout ----")
    print(stdout)
    print("---- jouled stderr ----")
    print(stderr)
    return 0


if __name__ == "__main__":
    exit(main())
