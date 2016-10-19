import random

def ctx():
  count = 0
  while(count<10):
    x = random.random()
    yield x
    count += 1

print("in exec'd module")
if __name__=="__mains__":
  for val in ctx():
    print(val)
  
