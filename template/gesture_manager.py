import os
import sys
import time
import socket
import select
import signal
from controller import WhimController

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else "/tmp/whimtouchpad"
os.makedirs(DATA_DIR, exist_ok=True)

UI_SOCK_PATH = os.path.join(DATA_DIR, "ui.sock")
IN_SOCK_PATH = os.path.join(DATA_DIR, "input.sock")

if os.path.exists(UI_SOCK_PATH):
    try: os.unlink(UI_SOCK_PATH)
    except: pass

ui_sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
ui_sock.bind(UI_SOCK_PATH)
ui_sock.setblocking(False)

def send_to_backend(msg):
    try:
        ui_sock.sendto(msg.encode(), IN_SOCK_PATH)
    except Exception as e:
        # Backend not ready or dropped
        pass

controller = WhimController(send_func=send_to_backend, gain=1.6)

running = True
def handle_sig(sig, frame):
    global running
    running = False

signal.signal(signal.SIGINT, handle_sig)
signal.signal(signal.SIGTERM, handle_sig)

print(f"[whimtouchpad] Gesture manager online (listening on {UI_SOCK_PATH})")

try:
    while running and not controller.finished:
        r, _, _ = select.select([ui_sock], [], [], 0.05)
        now = time.time()
        controller.tick(now)

        if r:
            while True:
                try:
                    data, _ = ui_sock.recvfrom(256)
                    if not data:
                        break
                    msg = data.decode().strip()
                    # Message format: "t <count> <x> <y> <timestamp>"
                    parts = msg.split()
                    if parts and parts[0] == 't' and len(parts) >= 5:
                        count = int(parts[1])
                        x = float(parts[2])
                        y = float(parts[3])
                        ts = float(parts[4])
                        controller.on_touch_frame(count, x, y, ts)
                except BlockingIOError:
                    break
                except Exception as e:
                    break
finally:
    controller.close()
    try:
        ui_sock.close()
        if os.path.exists(UI_SOCK_PATH):
            os.unlink(UI_SOCK_PATH)
    except: pass
    print("[whimtouchpad] Gesture manager stopped.")
