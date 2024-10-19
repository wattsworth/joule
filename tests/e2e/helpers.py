import subprocess
import shlex
import socket
import time

def run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL):
    return subprocess.run(shlex.split(cmd), stdout=stdout, stderr=stderr)

def wait_for_joule_host(host, port=80, timeout=5):
    i=0
    while i < timeout:
        i+=1
        try:
            s = socket.create_connection((host, port))
            s.close()
            return
        except ConnectionRefusedError:
            time.sleep(1)

    raise Exception(f"timeout waiting for {host}:{port}")