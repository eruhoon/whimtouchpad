"""Send pointer events to seat0 via a persistent Sway IPC connection."""
import json, os, socket, struct

class IPC:
 def __init__(self):
  self.sock=None
  self.connect()
 def connect(self):
  sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
  try:
   sock.settimeout(1);sock.connect(os.environ['SWAYSOCK'])
  except OSError:
   sock.close();raise
  self.sock=sock
 def read(self,n):
  result=b''
  while len(result)<n:
   part=self.sock.recv(n-len(result))
   if not part:raise OSError('Sway IPC closed')
   result+=part
  return result
 def request(self,kind,payload=''):
  try:
   if self.sock is None:self.connect()
   data=payload.encode()
   self.sock.sendall(b'i3-ipc'+struct.pack('=II',len(data),kind)+data)
   header=self.read(14)
   if header[:6]!=b'i3-ipc':raise OSError('Invalid Sway IPC response')
   size,response=struct.unpack('=II',header[6:])
   if response!=kind or size>4*1024*1024:raise OSError('Invalid Sway IPC header')
   result=json.loads(self.read(size))
   if kind==0 and any(not item.get('success') for item in result):raise OSError(str(result))
   return result
  except (OSError,ValueError) as error:
   # A timeout can leave half a frame in the stream. Never reuse it or
   # replay an uncertain command; reconnect on the next explicit request.
   self.close()
   raise OSError('Sway IPC connection discarded: '+str(error)) from error
 def close(self):
  if self.sock is not None:
   try:self.sock.close()
   finally:self.sock=None

class Pointer:
 def __init__(self,ipc,top,seat="seat0",limited=True):
  self.ipc=ipc;self.top=top;self.seat=seat;
  if seat not in ("seat0","seat1"):raise ValueError("Unsupported mouse seat")
  self.buttons=0;self.events=0;self.limited=limited
  self.native_mouse=None;self.active_seats={"seat0","seat1"}
  self.touch=None;self.touches={};self.touch_gesture=False
  self.refresh()
  self.x=self.rect['x']+self.rect['width']//2
  self.y=self.rect['y']+self.rect['height']//2
 def refresh(self):
  outputs=self.ipc.request(3)
  output=next((o for o in outputs if o['name']==self.top and o.get('active')),None)
  if not output:
   active_outs=sorted([o for o in outputs if o.get('active')], key=lambda o: (o.get('rect',{}).get('y',0), o.get('rect',{}).get('x',0)))
   if active_outs:
    output=active_outs[0]
    self.top=output['name']
  if not output:raise OSError('Upper output unavailable: '+str(self.top))
  self.rect=output['rect']
  self.active_seats={s['name'] for s in self.ipc.request(101)}
 def es_context(self):
  seats=self.ipc.request(101)
  if not isinstance(seats,list):raise OSError("Invalid GET_SEATS response")
  tree=self.ipc.request(4)
  def app(node,focus):
   if node.get('id')==focus:return node.get('app_id') or node.get('window_properties',{}).get('class')
   for key in ('nodes','floating_nodes'):
    for child in node.get(key,[]):
     found=app(child,focus)
     if found:return found
   return None
  for name in ('seat1','seat0'):
   focus=next((s.get('focus') for s in seats if s['name']==name),None)
   target=app(tree,focus) if focus is not None else None
   if target and target not in ('whimpad','duopad'):return target.lower()=='emulationstation'
  return False
 def mouse(self,dx,dy,buttons,w,h):
  if self.native_mouse and not (dx or dy or w or h or buttons!=self.buttons):return
  r=self.rect
  # Sway cursor set treats zero as "leave this coordinate unchanged".
  if self.limited:
   self.x=max(r['x']+1,min(r['x']+r['width']-1,self.x+dx))
   self.y=max(r['y']+1,min(r['y']+r['height']-1,self.y+dy))
  else:
   self.x+=dx;self.y+=dy
   if self.x==0:self.x=1
   if self.y==0:self.y=1
  if self.native_mouse:
   # Do not synthesize compositor buttons or convert mouse clicks to touch.
   # Position both client cursors first, then emit one real uinput frame.
   motion=[f'seat {seat} cursor set {self.x} {self.y}' for seat in ('seat0','seat1') if seat in self.active_seats]
   try:self.ipc.request(0,'; '.join(motion))
   except OSError:
    seats=self.ipc.request(101)
    self.active_seats={s['name'] for s in seats}
    motion=[f'seat {seat} cursor set {self.x} {self.y}' for seat in ('seat0','seat1') if seat in self.active_seats]
    if not motion:raise OSError('No pointer seat available')
    self.ipc.request(0,'; '.join(motion))
   if self.buttons!=buttons or w or h:self.native_mouse(buttons,w,h)
   self.buttons=buttons;self.events+=1
   return
  commands=[f'seat seat0 cursor set {self.x} {self.y}']
  if self.seat!='seat0':commands.append(f'seat {self.seat} cursor set {self.x} {self.y}')
  left_changed=bool((self.buttons^buttons)&1)
  if left_changed and buttons&1 and not self.native_mouse:
   if self.touches:
    try:target='seat0' if self.es_context() else 'seat1'
    except OSError as error:
     print('Click context warning:',error,flush=True);target='seat1'
    self.touch=self.touches.get(target,self.touch);self.touch_seat=target
   self.touch_gesture=bool(self.touch and r['x']<=self.x<r['x']+r['width'] and r['y']<=self.y<r['y']+r['height'])
  if left_changed:
   print('Left button:', 'down' if buttons&1 else 'up', 'x=',self.x,'y=',self.y,'path=','uinput-mouse' if self.native_mouse else ('touch-'+getattr(self,'touch_seat','seat1') if self.touch_gesture else self.seat),flush=True)
  if self.touch_gesture:
   self.touch.update((self.x-r['x'])*65535/max(1,r['width']-1),(self.y-r['y'])*65535/max(1,r['height']-1),bool(buttons&1))
  for bit,button in [(1,1),(2,3),(4,2)]:
   if bit==1 and self.touch_gesture:continue
   if (self.buttons^buttons)&bit:
    commands.append(f'seat {self.seat} cursor {"press" if buttons&bit else "release"} button{button}')
  for amount,positive,negative in [(w,4,5),(h,7,6)]:
   for _ in range(min(abs(amount),32)):
    commands.append(f'seat {self.seat} cursor press button{positive if amount>0 else negative}')
  self.ipc.request(0,'; '.join(commands))
  if left_changed and not buttons&1:self.touch_gesture=False
  self.buttons=buttons;self.events+=1
 def close(self):
  try:self.mouse(0,0,0,0,0)
  finally:
   try:
    devices=list(self.touches.values()) if self.touches else ([self.touch] if self.touch else [])
    for device in devices:device.close()
   finally:self.ipc.close()
