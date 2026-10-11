#!/usr/bin/env python3
"""WhimPad lower-screen view, SDL2 ctypes; no third-party Python modules."""
import ctypes as C
import ctypes.util
import os
import sys
import time
import signal
import socket
import math
from render_cache import TextureCache,corner_insets
from controller import Controller
from unicode_input import UnicodeInput
from pathlib import Path
import json
from screen_idle import ScreenIdle,TIMES

class Rect(C.Structure):
    _fields_=[('x',C.c_int),('y',C.c_int),('w',C.c_int),('h',C.c_int)]

def load(name,fallback):
    return C.CDLL(C.util.find_library(name) or fallback)

def bind(lib,name,result,*args):
    f=getattr(lib,name);f.restype=result;f.argtypes=list(args);return f

def refresh_pointer(pointer):
    try:pointer.refresh();return True
    except (OSError,ValueError) as error:
        print('Pointer refresh deferred; panel kept running:',error,flush=True)
        return False

def main():
    os.environ['SDL_VIDEODRIVER']='wayland'
    os.environ['SDL_VIDEO_WAYLAND_WMCLASS']='whimpad'
    os.environ['SDL_APP_ID']='whimpad'
    s=load('SDL2','libSDL2-2.0.so.0')
    init=bind(s,'SDL_Init',C.c_int,C.c_uint)
    hint=bind(s,'SDL_SetHint',C.c_int,C.c_char_p,C.c_char_p)
    create=bind(s,'SDL_CreateWindow',C.c_void_p,C.c_char_p,C.c_int,C.c_int,C.c_int,C.c_int,C.c_uint)
    renderer=bind(s,'SDL_CreateRenderer',C.c_void_p,C.c_void_p,C.c_int,C.c_uint)
    color=bind(s,'SDL_SetRenderDrawColor',C.c_int,C.c_void_p,C.c_ubyte,C.c_ubyte,C.c_ubyte,C.c_ubyte)
    clear=bind(s,'SDL_RenderClear',C.c_int,C.c_void_p)
    fill=bind(s,'SDL_RenderFillRect',C.c_int,C.c_void_p,C.POINTER(Rect))
    line=bind(s,'SDL_RenderDrawLine',C.c_int,C.c_void_p,C.c_int,C.c_int,C.c_int,C.c_int)
    logical=bind(s,'SDL_RenderSetLogicalSize',C.c_int,C.c_void_p,C.c_int,C.c_int)
    present=bind(s,'SDL_RenderPresent',None,C.c_void_p)
    poll=bind(s,'SDL_PollEvent',C.c_int,C.c_void_p)
    error=bind(s,'SDL_GetError',C.c_char_p)
    quit_sdl=bind(s,'SDL_Quit',None)
    hint(b'SDL_VIDEO_WAYLAND_WMCLASS',b'whimpad')
    hint(b'SDL_TOUCH_MOUSE_EVENTS',b'0')
    if init(0x20|0x4000):raise RuntimeError(error().decode())
    w=create(b'WhimPad Bottom',0x1fff0000,0x1fff0000,640,480,0x20)
    if not w:raise RuntimeError(error().decode())
    r=renderer(w,-1,2|4) # match lowerdeck's GPU/vsync path
    if not r:
        print('GPU renderer unavailable; using software:',error().decode(),flush=True)
        r=renderer(w,-1,1)
    if not r:raise RuntimeError(error().decode())
    logical(r,640,480)
    bind(s,"SDL_ShowCursor",C.c_int,C.c_int)(0)
    # Text is optional: the panel still renders if SDL_ttf/font is unavailable.
    text=None;texture_cache=None
    try:
        t=load('SDL2_ttf','libSDL2_ttf-2.0.so.0')
        bind(t,'TTF_Init',C.c_int)()
        bundled=Path(__file__).parent/'assets/NanumGothic-Regular.ttf'
        fontpath=str(bundled) if bundled.exists() else next((str(p) for root in ['/usr/share/fonts','/usr/share/emulationstation','/usr/config/emulationstation'] for p in Path(root).rglob('*.ttf')),None)
        if fontpath:
            font=bind(t,'TTF_OpenFont',C.c_void_p,C.c_char_p,C.c_int)(fontpath.encode(),19)
            if not font:raise RuntimeError('Font open failed')
            class Color(C.Structure):_fields_=[('r',C.c_ubyte),('g',C.c_ubyte),('b',C.c_ubyte),('a',C.c_ubyte)]
            rendertext=bind(t,'TTF_RenderUTF8_Blended',C.c_void_p,C.c_void_p,C.c_char_p,Color)
            tex=bind(s,'SDL_CreateTextureFromSurface',C.c_void_p,C.c_void_p,C.c_void_p)
            query=bind(s,'SDL_QueryTexture',C.c_int,C.c_void_p,C.c_void_p,C.c_void_p,C.POINTER(C.c_int),C.POINTER(C.c_int))
            copy=bind(s,'SDL_RenderCopy',C.c_int,C.c_void_p,C.c_void_p,C.c_void_p,C.POINTER(Rect))
            free=bind(s,'SDL_FreeSurface',None,C.c_void_p)
            destroy=bind(s,'SDL_DestroyTexture',None,C.c_void_p)
            def make_texture(key):
                value,rgb=key
                surface=rendertext(font,value.encode(),Color(*rgb,255))
                if not surface:return None
                try:texture=tex(r,surface)
                finally:free(surface)
                if not texture:return None
                tw,th=C.c_int(),C.c_int()
                if query(texture,None,None,C.byref(tw),C.byref(th)):
                    destroy(texture);return None
                return texture,tw.value,th.value
            texture_cache=TextureCache(make_texture,lambda item:destroy(item[0]))
            def text(value,x,y,w=None,h=None,rgb=(226,231,237)):
                item=texture_cache.get((value,rgb))
                if item is None:return
                texture,tw,th=item
                scale=min(1,(w-8)/max(1,tw),(h-6)/max(1,th)) if w and h else 1
                width,height=int(tw*scale),int(th*scale)
                rect=Rect(int(x+(w-width)/2) if w else int(x),int(y+(h-height)/2) if h else int(y),width,height)
                copy(r,texture,None,C.byref(rect))
    except Exception as e:print('Text unavailable:',e,flush=True)
    running=True
    def stop(*args):
        nonlocal running
        running=False
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    event=C.create_string_buffer(64)
    base=Path(__file__).parent
    runtime=Path(os.environ.get('WHIMPAD_RUNTIME_DIR',os.environ.get('DUOPAD_RUNTIME_DIR','/run/whimpad')))
    local=str(runtime/'ui.sock');target=str(runtime/'input.sock')
    Path(local).unlink(missing_ok=True)
    channel=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM);channel.bind(local);channel.setblocking(False)
    pointer=None
    if os.environ.get('WHIMPAD_POINTER_BACKEND',os.environ.get('DUOPAD_POINTER_BACKEND','sway'))=='sway':
        from pointer import IPC,Pointer
        pointer=Pointer(IPC(),os.environ.get('WHIMPAD_TOP_OUTPUT','DSI-2'),os.environ.get('WHIMPAD_MOUSE_SEAT','seat1'),os.environ.get('WHIMPAD_LIMIT_TOP','1')=='1')
        if os.environ.get('WHIMPAD_LEFT_TOUCH','0')=='1' and os.environ.get('WHIMPAD_CLICK_BACKEND','uinput')!='uinput':
            try:
                from virtual_touch import VirtualTouch
                pointer.touch=VirtualTouch()
                pointer.touches['seat1']=pointer.touch
                pointer.touches['seat0']=VirtualTouch('WhimPad ROCKNIX ES Touch',0xd004)
                print('Upper direct-touch left click ready',flush=True)
            except Exception as error:print('Virtual touch unavailable; mouse fallback:',error,flush=True)
        if os.environ.get('WHIMPAD_CLICK_BACKEND','uinput')=='uinput':
            pointer.native_mouse=lambda buttons,w,h:channel.sendto(f'm 0 0 {buttons} {w} {h}'.encode(),target)
            print('Native uinput mouse buttons and wheel ready',flush=True)
        print('Pointer IPC ready: '+pointer.seat+' / '+pointer.top+' / limited='+str(pointer.limited),flush=True)
    def send(message):
        try:
            if pointer and message.startswith('m '):pointer.mouse(*map(int,message.split()[1:]))
            else:channel.sendto(message.encode(),target)
        except (OSError,RuntimeError) as error:
            print('Input delivery failed; panel kept running:',error,flush=True)
            if pointer and pointer.native_mouse and message.startswith('m '):
                # Release pressed buttons even if cursor IPC is unavailable.
                if int(message.split()[3])==0:
                    try:pointer.native_mouse(0,0,0);pointer.buttons=0
                    except OSError as release_error:print('Release deferred:',release_error,flush=True)
    touch_frames=0;touch_contacts=0;last_stats=time.monotonic()
    unicode=None
    try:
        unicode=UnicodeInput()
        if pointer:unicode.es_context=pointer.es_context
        print('Wayland Korean text input ready',flush=True)
    except Exception as e:print('Korean input unavailable:',e,flush=True)
    gain=float(os.environ.get('WHIMPAD_GAIN',os.environ.get('DUOPAD_GAIN','1.5')))
    ctl=Controller(send,unicode=unicode,clock=time.monotonic,gain=gain)
    options=base/'panel-options.json'
    try:timeout=json.loads(options.read_text()).get('screen_timeout',30)
    except (OSError,ValueError):timeout=30
    idle=ScreenIdle(time.monotonic(),timeout)
    ready=base/'ui.ready';first_frame=True
    print('WhimPad SDL view ready',flush=True)
    def box(x,y,w,h,rgb):
        color(r,*rgb,255);rect=Rect(int(x),int(y),int(w),int(h));fill(r,C.byref(rect))
    def rounded(x,y,w,h,rgb,radius=7):
        box(x+radius,y,w-2*radius,h,rgb)
        box(x,y+radius,w,h-2*radius,rgb)
        for dy,inset in enumerate(corner_insets(radius)):
            box(x+inset,y+dy,w-2*inset,1,rgb)
            box(x+inset,y+h-dy-1,w-2*inset,1,rgb)
    try:
        while running and not ctl.finished:
            while poll(event):
                if int.from_bytes(event.raw[:4],sys.byteorder)==0x100:running=False
            while True:
                try:data=channel.recv(256).decode().split()
                except BlockingIOError:break
                if data==['reset']:
                    idle.reset(time.monotonic())
                    ctl.close();ctl.count=0;ctl.commit();ctl.shift=ctl.ctrl=ctl.alt=False
                    if pointer:
                        pointer.buttons=0
                        refresh_pointer(pointer)
                    if unicode:
                        try:unicode.prepare()
                        except Exception as error:print('Text reconnect after game:',error,flush=True)
                    print('Touch controller reset after game return',flush=True)
                if len(data)==5 and data[0]=='t':
                    touch_frames+=1;touch_contacts+=int(data[1])>0
                    n,x,y=int(data[1]),float(data[2]),float(data[3])
                    if idle.consume(n,time.monotonic()):continue
                    if n and not ctl.count and ctl.hit(x,y)=='ScreenTimeout':
                        idle.cycle(time.monotonic())
                        try:
                            temporary=options.with_suffix('.tmp')
                            temporary.write_text(json.dumps({'screen_timeout':idle.timeout}))
                            temporary.replace(options)
                        except OSError as error:print('Screen timeout save failed:',error,flush=True)
                    ctl.frame(n,x,y,float(data[4]))
                    if getattr(ctl,'screen_sleep',False):
                        ctl.screen_sleep=False
                        idle.blank=True
            if getattr(ctl,'screen_sleep',False):
                ctl.screen_sleep=False
                idle.blank=True
            ctl.tick(time.monotonic())
            if time.monotonic()-last_stats>=10:
                last_stats=time.monotonic()
                if pointer:refresh_pointer(pointer)
                print(f'Input stats: frames={touch_frames} contacts={touch_contacts} pointer={pointer.events if pointer else "uinput"}',flush=True)
            color(r,0,0,0,255);clear(r)
            if idle.tick(time.monotonic(),bool(ctl.count or ctl.buttons or ctl.pending)):
                present(r);time.sleep(1/60);continue
            if ctl.mode=='pad':
                rounded(12,68,616,322,(41,54,64),12)
                rounded(13,69,614,320,(16,22,29),11)
                box(297,375,46,3,(67,86,93))
            for x,y,w,h,k in ctl.cells():
                selected=ctl.active(k)
                pressed=ctl.count and ctl.region==k
                rgb=(35,83,67) if pressed else (23,56,46) if selected else (32,42,52) if k=='Wheel' else (27,34,44)
                rounded(x,y,w,h,rgb,7)
                if k=='Wheel':
                    for offset in [-18,-9,0,9,18]:box(x+w/2-12,y+h/2+offset,24,2,(140,175,170))
                elif k=='Settings':
                    cx,cy=int(x+w/2),int(y+h/2)
                    # 정교한 기계식 톱니바퀴 (Gear / Cogwheel) 그리기
                    for a in range(-12,13):
                        for b in range(-12,13):
                            dist2 = a*a + b*b
                            if dist2 > 144: continue
                            # 중심 구멍 (반경 3.5 이하 투명)
                            if dist2 <= 12: continue
                            angle = math.atan2(b, a)
                            # 6개 톱니 요철 계산 (sin(6*angle))
                            gear_r = 7.5 + 3.0 * math.sin(6 * angle)
                            if math.sqrt(dist2) <= gear_r:
                                box(cx+a, cy+b, 1, 1, (226,231,237))
                elif k=='Sleep':
                    color(r,226,231,237,255)
                    cx,cy=int(x+w/2),int(y+h/2)
                    # 초승달(Moon / Sleep) 아이콘 그리기
                    for a in range(-9,10):
                        for b in range(-9,10):
                            d1 = a*a + b*b
                            # 바깥 원 반경 9 이내, 안쪽 그림자 원 반경 8 제외
                            d2 = (a-4)*(a-4) + (b+2)*(b+2)
                            if d1 <= 81 and d2 >= 40:
                                box(cx+a, cy+b, 1, 1, (226,231,237))
                elif k=='Back':
                    color(r,226,231,237,255)
                    cx,cy=int(x+w/2),int(y+h/2)
                    for a,b,c,d in [(cx-13,cy,cx-6,cy-7),(cx-13,cy,cx-6,cy+7),(cx-6,cy-7,cx+12,cy-7),(cx-6,cy+7,cx+12,cy+7),(cx+12,cy-7,cx+12,cy+7),(cx-2,cy-4,cx+6,cy+4),(cx-2,cy+4,cx+6,cy-4)]:line(r,a,b,c,d)
                elif k not in ['L Click','R Click']:
                    if text:text(idle.label() if k=='ScreenTimeout' else ctl.label(k),x,y,w,h,(184,243,223) if selected else (226,231,237))
                    else:box(x+8,y+12,8,8,(185,215,210))
            if ctl.mode=='settings' and text:
                text('커서 감도',22,91)
                text(f'{ctl.gain:.1f} ×',115,132,410,58)
                text('휠 또는 두 손가락으로 스크롤',22,340)
            present(r)
            if first_frame:ready.write_text('0.5.9');first_frame=False
            time.sleep(1/60)
    finally:
        try:ctl.close()
        except OSError:pass
        if pointer:
            try:pointer.close()
            except OSError as error:print("Pointer cleanup:",error,flush=True)
        if unicode:unicode.close()
        channel.close();Path(local).unlink(missing_ok=True);ready.unlink(missing_ok=True)
        if texture_cache:texture_cache.close()
        quit_sdl()

if __name__=='__main__':
    try:main()
    except Exception as e:print('UI ERROR:',e,file=sys.stderr,flush=True);sys.exit(1)
