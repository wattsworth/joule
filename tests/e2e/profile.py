import psutil
import time

pid = 27557

while True:
    now = time.time()
    proc = psutil.Process(pid)
    memory = proc.memory_percent()
    with open('joule_stats.dat', 'a') as f:
        f.write("%d, %f\n" % (now, memory))
    time.sleep(1)