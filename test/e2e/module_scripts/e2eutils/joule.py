
import subprocess
import shlex
import json

STATUS_NAME_FIELD="Module Name"
STATUS_STATUS_FIELD="Status"
STATUS_STATUS_RUNNING="running"
STATUS_STATUS_FAILED="failed"

LOG_STARTING_STRING="---starting module---"

def status():
  output = _run("joule status -f json")
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

                  
  
