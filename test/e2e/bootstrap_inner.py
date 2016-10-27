#!/usr/bin/python3

"""
Run through each scenario in scenarios
"""
import os
import sys
import subprocess
import shlex

SOURCE_DIR="/src"
SCENARIO_DIR = "/src/test/e2e/scenarios"
MODULE_SCRIPT_DIR="/src/test/e2e/module_scripts"
JOULE_CONF_DIR="/etc/joule"

def prep_system():
  run("apache2ctl start")
  os.symlink(MODULE_SCRIPT_DIR,"/module_scripts")
  os.chdir(SOURCE_DIR)
  run("python3 setup.py install")
  os.removedirs(JOULE_CONF_DIR)

def run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL):
  return subprocess.run(shlex.split(cmd),stdout=stdout,stderr=stderr)
  
def main():
  prep_system()
  for entry in os.scandir(SCENARIO_DIR):
    if not entry.name.startswith('.') and entry.is_dir():
      os.symlink(entry.path, "/etc/joule")
      jouled = subprocess.Popen(["jouled","--config","/etc/joule/main.conf"],
                                stdout = subprocess.PIPE,stderr = subprocess.STDOUT,
                                universal_newlines=True)
      print("---------[%s]---------"%entry.name)
      sys.stdout.flush()
      test = subprocess.run(os.path.join(entry.path,"test.py"))
      jouled.terminate()
      if(test.returncode!=0):
        print("----dump from jouled----")
        stdout,_ = jouled.communicate()
        for line in stdout.rstrip().split('\n'):
            print("> %s"%line)

        return test.returncode

  return 0 #success
  
if __name__=="__main__":
  exit(main())