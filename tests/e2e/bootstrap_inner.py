#!/usr/bin/python3

"""
Run through each scenario in scenarios
"""
import os
import sys
import subprocess
import shlex
import shutil
import signal
import time

SOURCE_DIR = "/joule"
SCENARIO_DIR = "/joule/tests/e2e/scenarios"
MODULE_SCRIPT_DIR = "/joule/tests/e2e/module_scripts"
JOULE_CONF_DIR = "/etc/joule"

FORCE_DUMP = True


def prep_system():
    os.symlink(MODULE_SCRIPT_DIR, "/module_scripts")

    
def run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL):
    return subprocess.run(shlex.split(cmd), stdout=stdout, stderr=stderr)


def main():

    prep_system()
    for entry in os.scandir(SCENARIO_DIR):
        if not entry.name.startswith('.') and entry.is_dir():
            if(os.path.exists("/etc/joule/")):
                if(os.path.islink("/etc/joule")):
                    os.unlink("/etc/joule")  # this is a symlink
                else:
                    shutil.rmtree("/etc/joule/")
            os.symlink(entry.path, "/etc/joule")
            jouled = subprocess.Popen(["jouled", "--config",
                                       "/etc/joule/main.conf"],
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT,
                                      universal_newlines=True)
            print("---------[%s]---------" % entry.name)
            sys.stdout.flush()
            test = subprocess.run(os.path.join(entry.path, "test.py"))
            jouled.send_signal(signal.SIGINT)
            if test.returncode != 0 or FORCE_DUMP:
                print("----dump from jouled----")
                stdout, _ = jouled.communicate()
                for line in stdout.rstrip().split('\n'):
                    print("> %s" % line)
                if test.returncode !=0:
                    return test.returncode
            time.sleep(6)
    return 0  # success


if __name__ == "__main__":
    exit(main())
