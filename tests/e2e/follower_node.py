#!/usr/bin/python3

"""
Run the configuration in follower
"""

import os
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

    jouled = subprocess.Popen(["jouled", "--config",
                               config_file],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,
                              universal_newlines=True)
    # wait until local node is online
    max_tries = 6
    num_tries = 0
    while num_tries<max_tries:
        num_tries += 1
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        result = sock.connect_ex(('localhost', 8088))
        sock.close()
        if result == 0:
            break
        time.sleep(0.5)
    # local node failure, print the log
    if num_tries == max_tries:
        exit(dump_logs(jouled))

    # wait until the master node is online
    max_tries = 10
    num_tries = 0
    while num_tries < max_tries:
        num_tries += 1
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('node1.joule', 8088))
        sock.close()
        if result == 0:
            break
        else:
            print("cannot find node1.joule %d" % result)
        time.sleep(0.5)
    # remote node failure, print the log
    if num_tries == max_tries:
        print("Cannot find node1.joule, exiting follower")
        exit(dump_logs(jouled))

    # follow node1.joule
#    with open(os.devnull, 'w') as devnull:
    subprocess.run("joule master add joule https://node1.joule:8088".split(" "))#,
#                       #stderr=devnull, stdout=devnull)

    # this will just hang, node1 exits and terminates this container
    stdout, _ = jouled.communicate()
    # execution should not reach here
    return 0

def dump_logs(proc):
    proc.send_signal(signal.SIGINT)
    stdout, _ = proc.communicate()
    for line in stdout.rstrip().split('\n'):
        print("> %s" % line)

if __name__ == "__main__":
    exit(main())
