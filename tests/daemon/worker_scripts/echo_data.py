"""
Take in 2 sources and add them 
"""
import json
import argparse
import os


def main():
    print("starting up...")
    parser = argparse.ArgumentParser("demo")
    parser.add_argument("--pipes")
    args = parser.parse_args()

    pipes = json.loads(args.pipes)
    fd1_in = pipes['sources']['path1']['fd']
    fd1_out = pipes['destinations']['path1']['fd']
    x = os.read(fd1_in, 100000)
    os.write(fd1_out, x)

    fd2_in = pipes['sources']['path2']['fd']
    fd2_out = pipes['destinations']['path2']['fd']
    x = os.read(fd2_in, 100000)
    os.write(fd2_out, x)

    print("all done")

if __name__ == "__main__":
    main()
