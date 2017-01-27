
import subprocess
import shlex
import json

MODULES_TITLE_FIELD="Module"
MODULES_STATUS_FIELD="Status"
MODULES_STATUS_RUNNING="running"
MODULES_STATUS_FAILED="failed"

LOG_STARTING_STRING="---starting module---"

def modules():
  output = _run("joule modules -f json")
  assert(output is not None)
  return json.loads(output)

def logs(module_name):
  output = _run("joule logs %s"%module_name)
  return output

def _run(cmd,
         stdout=subprocess.PIPE,
         stderr=subprocess.PIPE):
  cmd = shlex.split(cmd)
  p = subprocess.run(cmd,stdout=stdout,stderr=stderr,universal_newlines=True)
  return p.stdout

                  
  
