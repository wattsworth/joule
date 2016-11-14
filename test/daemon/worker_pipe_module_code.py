"""
Take in 2 sources and add them 
"""
import json
import argparse
import sys
import numpy as np

def main():
  
  parser = argparse.ArgumentParser("demo")
  parser.add_argument("--pipes")
  args = parser.parse_args()

  pipes = json.loads(args.pipes)
  with open(pipes['sources']['path1'],'rb') as f:
    x = f.read(5)
    assert(x==b'test1')

  with open(pipes['sources']['path2'],'rb') as f:
    x = f.read(5)
    assert(x==b'test2')

  with open(pipes['destination'],'wb') as f:
    f.write(np.array([[1.0,2.0],[3.0,4.0]]).tobytes())
    
    
if __name__=="__main__":
  main()
