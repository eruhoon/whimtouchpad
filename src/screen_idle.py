"""Android-compatible lower-panel blackout, swallowing the wake gesture."""
TIMES=(5,10,15,30,60,120,300,0)
LABELS=('5초','10초','15초','30초','1분','2분','5분','안 꺼짐')
class ScreenIdle:
 def __init__(self,now,timeout=30):
  self.timeout=timeout if timeout in TIMES else 30
  self.last=now;self.blank=False;self.waking=False;self.touching=False
 def cycle(self,now):
  self.timeout=TIMES[(TIMES.index(self.timeout)+1)%len(TIMES)]
  self.reset(now)
 def reset(self,now):
  self.last=now;self.blank=False;self.waking=False;self.touching=False
 def consume(self,contacts,now):
  if contacts or self.touching:self.last=now
  self.touching=contacts>0
  if self.blank:
   if not contacts:return True
   self.blank=False;self.waking=contacts>0
   return True
  if self.waking:
   if not contacts:self.waking=False
   return True
  return False
 def tick(self,now,busy=False):
  if busy:self.last=now
  if self.timeout and not busy and now-self.last>=self.timeout:self.blank=True
  return self.blank
 def label(self):return '화면 보호 · '+LABELS[TIMES.index(self.timeout)]
