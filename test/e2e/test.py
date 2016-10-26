#!/usr/bin/python3
import subprocess
import time
import sys
def main():
  p = subprocess.Popen(["jouled","--config","/etc/joule/main.conf"],stdout=sys.stdout)
  time.sleep(8)
  subprocess.call(["joule","status"])
  subprocess.call(["joule","logs","Basic Demo"])
  p.terminate()

if __name__=="__main__":
  main()
