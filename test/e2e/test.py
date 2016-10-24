#!/usr/bin/python3
import subprocess
import time
def main():
  p = subprocess.Popen(["jouled","--config","/etc/joule/main.conf"])
  time.sleep(1)
  subprocess.call(["joule","status"])
  p.terminate()

if __name__=="__main__":
  main()
