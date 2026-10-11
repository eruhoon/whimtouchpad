"""Wayland virtual keyboard text input, using the same public protocol as wvkbd."""
import ctypes as C
import os
import time
class Interface(C.Structure):pass
class Message(C.Structure):
    _fields_=[('name',C.c_char_p),('signature',C.c_char_p),('types',C.POINTER(C.POINTER(Interface)))]
Interface._fields_=[('name',C.c_char_p),('version',C.c_int),('method_count',C.c_int),('methods',C.POINTER(Message)),('event_count',C.c_int),('events',C.POINTER(Message))]

def keymap(text):
    chars=list(dict.fromkeys(text))
    if len(chars)>12:raise ValueError('Text chunk exceeds reserved F13–F24 keys')
    codes=['<BKSP> = 22;','<LEFT> = 113;','<RGHT> = 114;']+[f'<K{i:03}> = {i+191};' for i in range(len(chars))]
    symbols=['key <BKSP> { [ BackSpace ] };','key <LEFT> { [ Left ] };','key <RGHT> { [ Right ] };']+[f'key <K{i:03}> {{ [ U{ord(c):04X} ] }};' for i,c in enumerate(chars)]
    data=('xkb_keymap { xkb_keycodes "whimpad" { minimum=8; maximum=255; '+''.join(codes)+' }; xkb_types "whimpad" { type "ONE_LEVEL" { modifiers=None; map[None]=Level1; }; }; xkb_compatibility "whimpad" {}; xkb_symbols "whimpad" { '+''.join(symbols)+' }; };\0').encode()
    return data,{c:i+183 for i,c in enumerate(chars)}

class UnicodeInput:
    def __init__(self):
        try:self._open()
        except Exception:
            self.close()
            raise
    def _open(self):
        self.vk=None;self.display=None;self.ready=False;self.removed=False
        self.seat_globals={};self.selected_global=None
        self.lib=C.CDLL('libwayland-client.so.0');self.keep=[];self.seats={};self.manager=None
        def bind(n,r,*a):
            f=getattr(self.lib,n);f.restype=r;f.argtypes=list(a);return f
        self.connect=bind('wl_display_connect',C.c_void_p,C.c_char_p)
        self.disconnect=bind('wl_display_disconnect',None,C.c_void_p)
        self.roundtrip=bind('wl_display_roundtrip',C.c_int,C.c_void_p)
        self.flush=bind('wl_display_flush',C.c_int,C.c_void_p)
        self.marshal=bind('wl_proxy_marshal_flags',C.c_void_p,C.c_void_p,C.c_uint,C.POINTER(Interface),C.c_uint,C.c_uint)
        self.listener=bind('wl_proxy_add_listener',C.c_int,C.c_void_p,C.POINTER(C.c_void_p),C.c_void_p)
        self.destroy=bind('wl_proxy_destroy',None,C.c_void_p)
        self.registry_interface=Interface.in_dll(self.lib,'wl_registry_interface')
        self.seat_interface=Interface.in_dll(self.lib,'wl_seat_interface')
        self.vk_interface=Interface(b'zwp_virtual_keyboard_v1',1,4,None,0,None)
        methods=(Message*4)(Message(b'keymap',b'uhu',None),Message(b'key',b'uuu',None),Message(b'modifiers',b'uuuu',None),Message(b'destroy',b'',None))
        self.vk_interface.methods=methods;self.keep.append(methods)
        types=(C.POINTER(Interface)*2)(C.pointer(self.seat_interface),C.pointer(self.vk_interface));self.keep.append(types)
        mgrmethods=(Message*1)(Message(b'create_virtual_keyboard',b'on',types));self.keep.append(mgrmethods)
        self.mgr_interface=Interface(b'zwp_virtual_keyboard_manager_v1',1,1,mgrmethods,0,None)
        self.display=self.connect(None)
        if not self.display:raise RuntimeError('Cannot connect to Wayland for text input')
        self.registry=self.marshal(self.display,1,C.byref(self.registry_interface),1,0,C.c_void_p(None))
        GLOBAL=C.CFUNCTYPE(None,C.c_void_p,C.c_void_p,C.c_uint,C.c_char_p,C.c_uint)
        REMOVE=C.CFUNCTYPE(None,C.c_void_p,C.c_void_p,C.c_uint)
        CAPS=C.CFUNCTYPE(None,C.c_void_p,C.c_void_p,C.c_uint)
        NAME=C.CFUNCTYPE(None,C.c_void_p,C.c_void_p,C.c_char_p)
        def add_callbacks(obj,callbacks):
            array=(C.c_void_p*len(callbacks))(*[C.cast(c,C.c_void_p).value for c in callbacks]);self.keep.extend([array,*callbacks]);self.listener(obj,array,None)
        def bind_global(reg,num,iface,version):
            return self.marshal(reg,0,C.byref(iface),version,0,C.c_uint(num),C.c_char_p(iface.name),C.c_uint(version),C.c_void_p(None))
        def global_(data,reg,num,name,version):
            if name==b'wl_seat' and not self.ready:
                seat=bind_global(reg,num,self.seat_interface,min(version,2));self.seats[seat]='';self.seat_globals[num]=seat
                add_callbacks(seat,[CAPS(lambda *a:None),NAME(lambda data,obj,n:self.seats.__setitem__(obj,n.decode()))])
            elif name==self.mgr_interface.name and not self.ready:self.manager=bind_global(reg,num,self.mgr_interface,1)
        add_callbacks(self.registry,[GLOBAL(global_),REMOVE(lambda data,reg,num:self.remove_global(num))])
        if self.roundtrip(self.display)<0 or self.roundtrip(self.display)<0:raise RuntimeError('Wayland registry error')
        seat=next((p for p,n in self.seats.items() if n=='seat0'),None)
        if not seat or not self.manager:raise RuntimeError('seat0 / virtual keyboard protocol unavailable')
        self.selected_global=next(n for n,p in self.seat_globals.items() if p==seat)
        self.ready=True
        self.vk=self.marshal(self.manager,0,C.byref(self.vk_interface),1,0,C.c_void_p(seat),C.c_void_p(None))
        self.setmap(' ')
    def remove_global(self,num):
        seat=self.seat_globals.pop(num,None)
        if seat is not None:self.seats.pop(seat,None)
        if num==self.selected_global:self.removed=True
    def prepare(self):
        # Process registry removals before any Backspace or insertion. Never
        # bind newly announced transient seats after selecting our initial seat.
        if not self.display:
            self.__init__();return
        failed=self.roundtrip(self.display)<0
        if failed or self.removed:
            self.close()
            self.__init__()
            print('Wayland text connection recreated after seat change',flush=True)
    def setmap(self,text):
        data,self.codes=keymap(text);fd=os.memfd_create('whimpad-keymap',os.MFD_CLOEXEC)
        try:
            os.write(fd,data);self.marshal(self.vk,0,None,1,0,C.c_uint(1),C.c_int(fd),C.c_uint(len(data)));self.flush(self.display)
            if self.roundtrip(self.display)<0:raise RuntimeError('Keymap synchronization failed')
        finally:os.close(fd)
    def event(self,code,down):
        self.marshal(self.vk,1,None,1,0,C.c_uint(int(time.monotonic()*1000)&0xffffffff),C.c_uint(code),C.c_uint(down));
        if self.flush(self.display)<0:raise RuntimeError('Wayland text event flush failed')
    def replace(self,previous,new):
        # Always preserve the unchanged prefix. Focus can move between seats;
        # it must not switch composition to whole-word deletion.
        common=0
        while common<min(len(previous),len(new)) and previous[common]==new[common]:common+=1
        self.text(new[common:],len(previous)-common,delay=.012)
    def text(self,text,erase=0,delay=.012):
        if hasattr(self,'display'):self.prepare()
        # Linux codes 32 onward are real letter keys. SDL exposes their physical
        # scancodes even with a Unicode keymap, so ES-DE's configured navigation
        # can stop editing. Use only the otherwise unused F13–F24 range.
        def tap(code):
            self.event(code,1);time.sleep(delay);self.event(code,0);time.sleep(delay)
        try:literal=bool(getattr(self,'es_context',lambda:False)())
        except Exception as error:
            print('ES literal context lookup:',error,flush=True);literal=False
        if erase:
            self.setmap(' ')
            for _ in range(erase):tap(14)
        # Reuse one physical key for every Unicode character. This avoids
        # depending on SDL handling a changing set of F13–F24 scancodes.
        for c in text:
            korean=0x3131<=ord(c)<=0x318e or 0xac00<=ord(c)<=0xd7a3
            if literal and korean:
                # ROCKNIX's native composer intercepts adjacent Korean characters,
                # including already composed syllables. A temporary ASCII space
                # selects its plain-insert branch; remove it without changing text.
                self.setmap(' ');tap(self.codes[' '])
            self.setmap(c);tap(self.codes[c])
            if literal and korean:
                tap(105);tap(14);tap(106)
    def close(self):
        # Do not marshal destructor requests on a display with a fatal error.
        if getattr(self,'display',None):
            self.disconnect(self.display);self.display=None;self.vk=None
