import math
from hangul import jamo,compose
from layout_loader import LayoutLoader
KEYS=dict(zip('qwertyuiop',[16,17,18,19,20,21,22,23,24,25]))
KEYS.update(dict(zip('asdfghjkl',[30,31,32,33,34,35,36,37,38])))
KEYS.update(dict(zip('zxcvbnm',[44,45,46,47,48,49,50])))
KEYS.update(dict(zip('1234567890',range(2,12))))
KEYS.update({'Back':14,'Enter':28,'Space':57,'Tab':15,'Left':105,'Right':106,'Up':103,'Down':108,',':51,'.':52,'Esc':1,'`':41,'-':12,'=':13,'[':26,']':27,'\\':43,';':39,"'":40,'/':53,'Del':111,'Home':102,'End':107})
KEYS.update(dict(zip(['F'+str(i) for i in range(1,13)],[59,60,61,62,63,64,65,66,67,68,87,88])))
class Controller:
 def __init__(self,send,unicode=None,clock=None,gain=1.5,layout_loader=None):
  self.loader=layout_loader or LayoutLoader()
  self._layouts={}
  self.send=send;self.clock=clock;self.unicode=unicode;self.mode=getattr(self.loader,'default_view','pad');self.korean=False;self.shift=False;self.caps=False;self.ctrl=False;self.alt=False;self.raw='';self.committed='';self.message='';self.gain=gain;self.natural=True;self.returnmode="pad";self.buttons=0;self.pending=[];self.seq=0;self.count=0;self.lastx=self.lasty=0;self.x=self.y=0;self.multi=False;self.travel=0;self.lasttap=-1;self.started=0;self.region=None;self.scrollx=self.scrolly=self.rx=self.ry=0;self.drag=False;self.lockdrag=False;self.finished=False;self.screen_sleep=False
 def mouse(self,dx=0,dy=0,w=0,h=0):self.send(f'm {dx} {dy} {self.buttons} {w} {h}')
 def key(self,c,down):self.send(f'k {c} {int(down)}')
 def schedule(self,t,f):self.seq+=1;self.pending.append((t,self.seq,f))
 def tick(self,t):
  due=sorted(x for x in self.pending if x[0]<=t);self.pending=[x for x in self.pending if x[0]>t]
  for _,_,f in due:f()
 def click(self,button,t,double=False):
  # Release is delayed so clients see distinct press/release frames.
  t=self.clock() if self.clock else t
  bit=button
  def down():self.buttons|=bit;self.mouse()
  def up():self.buttons&=~bit;self.mouse()
  down();self.schedule(t+.055,up)
  if double:self.schedule(t+.12,down);self.schedule(t+.175,up)
 def _send_combo(self,combo_str,t):
  parts=[p.strip() for p in combo_str.split('+')]
  mod_map={'Ctrl':29,'Control':29,'Alt':56,'Shift':42,'Super':125,'Win':125}
  mods=[mod_map[p] for p in parts[:-1] if p in mod_map]
  key_label=parts[-1]
  code=KEYS.get(key_label) or KEYS.get(key_label.lower())
  if not code:return
  for m in mods:self.key(m,True)
  self.key(code,True)
  def release():
   self.key(code,False)
   for m in reversed(mods):self.key(m,False)
  self.schedule(t+.055,release)
 def commit(self):self.raw='';self.committed=''
 def keytap(self,label,t):
  t=self.clock() if self.clock else t
  if label in ('Shift','Caps','Ctrl','Alt'):
   attr=label.lower();setattr(self,attr,not getattr(self,attr));return
  if label=='Mode':label='Keys' if self.mode=='pad' else 'Pad'
  if label=='Settings':self.returnmode=self.mode;self.mode='settings';self.buttons=0;self.mouse();return
  if label=='Return':self.mode=self.returnmode;return
  if label=='Gain-':self.gain=round(max(.5,self.gain-.1),1);return
  if label=='Gain+':self.gain=round(min(4.,self.gain+.1),1);return
  if label=='ScreenTimeout':return
  if label=='Natural':self.natural=not self.natural;return
  if label=='EN/KR':self.commit();self.korean=not self.korean;return
  if label=='Pad':self.commit();self.mode='pad';return
  if label=='Keys':self.mode='keys';self.buttons=0;self.mouse();return
  if label=='Custom':self.commit();self.mode=getattr(self.loader,'custom_id','custom');self.buttons=0;self.mouse();return
  if label=='Sleep':self.screen_sleep=True;return
  action=self.loader.get_action(label) if (self.mode==getattr(self.loader,'custom_id','custom') and hasattr(self.loader,'get_action')) else None
  if action:
   if action.startswith('combo:'):self._send_combo(action[6:],t);return
   elif action.startswith('key:'):label=action[4:]
   elif action.startswith('mouse:'):
    bt=action[6:]
    if bt=='left':self.click(1,t)
    elif bt=='right':self.click(2,t)
    elif bt=='double':self.click(1,t,True)
    return
   elif action=='sleep':self.screen_sleep=True;return
   elif action.startswith('switch:'):self.mode=action[7:];return
  if self.korean and label=='Back' and self.unicode:
   self.commit()
   try:self.unicode.text('',erase=1);self.message=''
   except Exception as error:self.message='삭제 전송 오류';print('Korean delete:',error,flush=True)
   return
  if self.korean and len(label)==1 and label.isalpha() and not(self.ctrl or self.alt):
   if not self.unicode:self.message='한글 전송 연결 실패 · 로그 확인';return
   self.raw+=jamo(label.upper() if self.shift or self.caps else label);self._compose();self.shift=False;return
  self.commit()
  if self.korean and self.unicode and label=='Space' and not(self.ctrl or self.alt):
   try:self.unicode.text(' ');self.shift=False;self.message=''
   except Exception as error:self.message='공백 전송 오류';print('Space input:',error,flush=True)
   return
  if label in KEYS:
   code=KEYS[label];mods=[]
   if self.ctrl:mods.append(29)
   if self.alt:mods.append(56)
   if self.shift ^ (self.caps and len(label)==1 and label.isalpha()):mods.append(42)
   for c in mods:self.key(c,True)
   self.key(code,True)
   def release():
    self.key(code,False)
    for c in mods:self.key(c,False)
   self.schedule(t+.055,release)
   if len(label)==1 or label=='Space':self.shift=False
 def _compose(self):
  new=compose(self.raw)
  # Update the upper input field; the lower keyboard has no composition strip.
  try:
   if hasattr(self.unicode,'replace'):self.unicode.replace(self.committed,new)
   else:self.unicode.text(new,len(self.committed))
   self.committed=new;self.message=''
  except Exception as e:self.message='한글 전송 오류';print('Unicode input:',e,flush=True)
 def cells(self):
  if self.mode not in self._layouts:self._layouts[self.mode]=self.loader.get_cells(self.mode)
  return self._layouts[self.mode]
 def _build_cells(self):
  return self.loader.get_cells(self.mode)
 def hit(self,x,y):
  return next((k for a,b,w,h,k in self.cells() if a<=x<a+w and b<=y<b+h),None)
 def label(self,k):
  if self.mode==getattr(self.loader,'custom_id','custom') and hasattr(self.loader,'get_label'):
   custom_lbl=self.loader.get_label(k)
   if custom_lbl:return custom_lbl
  labels={'Pad':'터치패드','Keys':'키보드','Custom':getattr(self.loader,'custom_title','단축키'),'EN/KR':'한글' if self.korean else '영문','L Click':'좌클릭','R Click':'우클릭','Double':'더블클릭','Drag':'드래그','Back':'⌫','Space':'Space','Mode':'키보드로 전환' if self.mode=='pad' else '터치패드로 전환','Settings':'⚙','Return':'돌아가기','Gain-':'−','Gain+':'+','Natural':'자연스러운 스크롤  '+('켜짐' if self.natural else '꺼짐'),'Sleep':'×','Left':'←','Right':'→','Up':'↑','Down':'↓'}
  if self.korean and len(k)==1 and k.isalpha():return jamo(k.upper() if self.shift or self.caps else k)
  if len(k)==1 and k.isalpha():return k.upper() if self.shift ^ self.caps else k.lower()
  shifted=dict(zip("`1234567890-=[]\\;',./",'~!@#$%^&*()_+{}|:"<>?'))
  if self.shift and k in shifted:return shifted[k]
  return labels.get(k,k)
 def active(self,k):return (k=='Mode') or (k in ['Enter','EN/KR','Return']) or (k=='Natural' and self.natural) or (k=='L Click' and self.buttons&1) or (k=='R Click' and self.buttons&2) or (k=='Pad' and self.mode=='pad') or (k=='Keys' and self.mode=='keys') or (k=='Custom' and self.mode==getattr(self.loader,'custom_id','custom')) or (k=='Drag' and self.lockdrag) or (k in ['Shift','Caps','Ctrl','Alt'] and getattr(self,k.lower()))
 def frame(self,n,x,y,t):
  self.tick(t);self.x=x;self.y=y
  if n and not self.count:
   self.started=t;self.travel=0;self.multi=n>1;self.region=self.hit(x,y);self.scrollx=self.scrolly=self.rx=self.ry=0
   if self.region in ('L Click','R Click'):
    self.buttons|=1 if self.region=='L Click' else 2;self.mouse()
   if self.mode=='pad' and not self.region:
    self.drag=t-self.lasttap<.32 and self.lasttap>=0
    if self.drag:
     self.pending=[];self.buttons|=1;self.mouse()
  elif n and self.count:
   if n!=self.count:
    self.multi|=n>1;self.scrollx=self.scrolly=0
    if n>1 and self.drag:self.buttons&=~1;self.mouse();self.drag=False
   else:
    dx,dy=x-self.lastx,y-self.lasty;self.travel+=math.hypot(dx,dy)
    if self.region=='Wheel':
     self.scrolly+=dy;w=int(self.scrolly/14);self.scrolly-=w*14
     if w:self.mouse(w=w if self.natural else -w)
    if self.mode=='pad' and not self.region:
     if n>=2:
      self.scrollx+=dx;self.scrolly+=dy;h=int(self.scrollx/22);w=int(self.scrolly/22);self.scrollx-=h*22;self.scrolly-=w*22
      if h or w:self.mouse(w=w if self.natural else -w,h=-h if self.natural else h)
     elif not self.multi:
      self.rx+=dx*self.gain;self.ry+=dy*self.gain;mx,my=int(self.rx),int(self.ry);self.rx-=mx;self.ry-=my
      if mx or my:self.mouse(mx,my)
  elif not n and self.count:
   if self.region in ('L Click','R Click'):
    bit=1 if self.region=='L Click' else 2
    def release_button(bit=bit):self.buttons&=~bit;self.mouse()
    self.schedule(max(t,self.started+.055),release_button)
   elif self.region and not self.multi and self.travel<15:
    k=self.region
    if k=='Wheel':self.click(4,t)
    elif k=='L Click':self.click(1,t)
    elif k=='R Click':self.click(2,t)
    elif k=='Double':self.click(1,t,True)
    elif k=='Drag':self.lockdrag=not self.lockdrag;self.buttons=1 if self.lockdrag else 0;self.mouse()
    else:self.keytap(k,t)
   elif self.mode=='pad' and not self.region:
    if self.drag:self.buttons&=~1;self.mouse();self.drag=False;self.lasttap=-1
    elif self.travel<12 and t-self.started<.38:self.click(2 if self.multi else 1,t);self.lasttap=t if not self.multi else -1
    else:self.lasttap=-1
  self.lastx=x;self.lasty=y;self.count=n
 def close(self):
  self.pending=[];self.buttons=0;self.mouse()
  for c in [29,42,56]:self.key(c,False)
