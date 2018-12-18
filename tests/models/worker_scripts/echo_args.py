import sys
import time

sys.stdout.write(' '.join(sys.argv[1:])+'\n')
sys.stdout.flush()
time.sleep(0.1)