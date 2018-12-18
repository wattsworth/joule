import time
import signal
import sys


def main():
    while(True):
        time.sleep(0.1)
        print("in run_forever")
        sys.stdout.flush()


def handler(signum, frame):
    print("caught %d, ignoring" % signum)
    sys.stdout.flush()


if __name__ == "__main__":
    print("running forever!!!\n")
    signal.signal(signal.SIGTERM, handler)
    main()

