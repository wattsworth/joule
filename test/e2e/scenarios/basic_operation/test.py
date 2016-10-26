#!/usr/bin/python3
import subprocess
import time

def main():
  time.sleep(8)
  subprocess.run(["joule","status"])
#  subprocess.run(["joule","logs","Basic Demo"])

if __name__=="__main__":
  print("hello world!")
  main()
  exit(2)
