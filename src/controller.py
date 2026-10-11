import math
import time

# Linux Key Codes
KEYS = {
    'Esc': 1, '1': 2, '2': 3, '3': 4, '4': 5, '5': 6, '6': 7, '7': 8, '8': 9, '9': 10, '0': 11,
    '-': 12, '=': 13, 'Back': 14, 'Tab': 15, 'q': 16, 'w': 17, 'e': 18, 'r': 19, 't': 20,
    'y': 21, 'u': 22, 'i': 23, 'o': 24, 'p': 25, '[': 26, ']': 27, 'Enter': 28, 'Ctrl': 29,
    'a': 30, 's': 31, 'd': 32, 'f': 33, 'g': 34, 'h': 35, 'j': 36, 'k': 37, 'l': 38, ';': 39,
    "'": 40, '`': 41, 'Shift': 42, '\\': 43, 'z': 44, 'x': 45, 'c': 46, 'v': 47, 'b': 48,
    'n': 49, 'm': 50, ',': 51, '.': 52, '/': 53, 'Alt': 56, 'Space': 57, 'Caps': 58,
    'F1': 59, 'F2': 60, 'F3': 61, 'F4': 62, 'F5': 63, 'F6': 64, 'F7': 65, 'F8': 66, 'F9': 67,
    'F10': 68, 'F11': 87, 'F12': 88, 'Home': 102, 'Up': 103, 'Left': 105, 'Right': 106,
    'End': 107, 'Down': 108, 'Del': 111
}

class WhimController:
    def __init__(self, send_func, gain=1.5):
        self.send = send_func
        self.gain = gain
        self.mode = 'pad'       # 'pad' or 'keys'
        self.buttons = 0        # bit 0: L, bit 1: R, bit 2: M
        self.natural_scroll = False

        self.last_x = 0
        self.last_y = 0
        self.current_x = 0
        self.current_y = 0
        self.touch_count = 0

        self.started_time = 0
        self.travel_distance = 0
        self.last_tap_time = -1
        self.is_dragging = False
        self.multi_touch = False

        self.scroll_acc_x = 0
        self.scroll_acc_y = 0
        self.rx = 0
        self.ry = 0

        self.pending_tasks = []
        self.seq = 0
        self.active_region = None
        self.finished = False

    def emit_mouse(self, dx=0, dy=0, w=0, h=0):
        self.send(f"m {int(dx)} {int(dy)} {self.buttons} {int(w)} {int(h)}")

    def emit_key(self, code, is_down):
        self.send(f"k {code} {1 if is_down else 0}")

    def schedule(self, trigger_time, func):
        self.seq += 1
        self.pending_tasks.append((trigger_time, self.seq, func))

    def tick(self, now):
        due = sorted(x for x in self.pending_tasks if x[0] <= now)
        self.pending_tasks = [x for x in self.pending_tasks if x[0] > now]
        for _, _, func in due:
            func()

    def click(self, button_mask, now, double=False):
        def down():
            self.buttons |= button_mask
            self.emit_mouse()

        def up():
            self.buttons &= ~button_mask
            self.emit_mouse()

        down()
        self.schedule(now + 0.055, up)
        if double:
            self.schedule(now + 0.120, down)
            self.schedule(now + 0.175, up)

    def cells(self):
        # 상단 네비게이션 버튼: [키보드/패드 전환] [종료]
        nav = [
            (10, 8, 480, 50, 'Mode'),
            (500, 8, 130, 50, 'Exit')
        ]
        if self.mode == 'pad':
            # 트랙패드 모드: 하단 좌클릭, 휠, 우클릭 바
            return nav + [
                (10, 400, 260, 72, 'L Click'),
                (280, 400, 80, 72, 'Wheel'),
                (370, 400, 260, 72, 'R Click')
            ]
        else:
            # 키패드 모드 레이아웃
            rows = [
                ['Esc', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12'],
                ['`', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '-', '=', 'Back'],
                ['Tab', 'q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p', '[', ']', '\\'],
                ['Caps', 'a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', ';', "'", 'Enter'],
                ['Shift', 'z', 'x', 'c', 'v', 'b', 'n', 'm', ',', '.', '/', 'Shift'],
                ['Ctrl', 'Alt', 'Space', 'Left', 'Down', 'Up', 'Right']
            ]
            y = 66
            heights = [45, 68, 68, 68, 68, 70]
            cells = list(nav)
            for row, h in zip(rows, heights):
                weights = [3.0 if k == 'Space' else 1.5 if k in ['Enter', 'Back', 'Shift'] else 1.0 for k in row]
                total_w = sum(weights)
                unit = 620.0 / total_w
                cur_x = 10
                for k, weight in zip(row, weights):
                    bw = unit * weight
                    cells.append((int(cur_x + 2), int(y + 2), int(bw - 4), int(h - 4), k))
                    cur_x += bw
                y += h
            return cells

    def hit_test(self, x, y):
        for bx, by, bw, bh, key in self.cells():
            if bx <= x < bx + bw and by <= y < by + bh:
                return key
        return None

    def key_tap(self, key_label, now):
        if key_label == 'Mode':
            self.mode = 'keys' if self.mode == 'pad' else 'pad'
            self.buttons = 0
            self.emit_mouse()
            return
        if key_label == 'Exit':
            self.finished = True
            return

        if key_label in KEYS:
            code = KEYS[key_label]
            self.emit_key(code, True)
            self.schedule(now + 0.055, lambda: self.emit_key(code, False))

    def on_touch_frame(self, count, x, y, timestamp):
        self.tick(timestamp)
        self.current_x = x
        self.current_y = y

        # 1. 새 터치 시작
        if count > 0 and self.touch_count == 0:
            self.started_time = timestamp
            self.travel_distance = 0
            self.multi_touch = (count > 1)
            self.active_region = self.hit_test(x, y)
            self.scroll_acc_x = 0
            self.scroll_acc_y = 0
            self.rx = 0
            self.ry = 0

            # 하단 고정 버튼 영역을 터치한 경우
            if self.active_region in ('L Click', 'R Click'):
                self.buttons |= (1 if self.active_region == 'L Click' else 2)
                self.emit_mouse()

            # 트랙패드 영역에서 더블 탭 판정 (< 0.32초)
            if self.mode == 'pad' and not self.active_region:
                self.is_dragging = (timestamp - self.last_tap_time < 0.32) and (self.last_tap_time >= 0)
                if self.is_dragging:
                    self.pending_tasks = []
                    self.buttons |= 1
                    self.emit_mouse()

        # 2. 터치 이동 중
        elif count > 0 and self.touch_count > 0:
            if count != self.touch_count:
                self.multi_touch |= (count > 1)
                self.scroll_acc_x = 0
                self.scroll_acc_y = 0
                if count > 1 and self.is_dragging:
                    self.buttons &= ~1
                    self.emit_mouse()
                    self.is_dragging = False
            else:
                dx = x - self.last_x
                dy = y - self.last_y
                self.travel_distance += math.hypot(dx, dy)

                if self.active_region == 'Wheel':
                    self.scroll_acc_y += dy
                    w = int(self.scroll_acc_y / 14)
                    self.scroll_acc_y -= w * 14
                    if w:
                        self.emit_mouse(w=w if self.natural_scroll else -w)

                elif self.mode == 'pad' and not self.active_region:
                    # 두 손가락 스크롤
                    if count >= 2:
                        self.scroll_acc_x += dx
                        self.scroll_acc_y += dy
                        h = int(self.scroll_acc_x / 22)
                        w = int(self.scroll_acc_y / 22)
                        self.scroll_acc_x -= h * 22
                        self.scroll_acc_y -= w * 22
                        if h or w:
                            self.emit_mouse(w=w if self.natural_scroll else -w, h=-h if self.natural_scroll else h)
                    elif not self.multi_touch:
                        # 한 손가락 마우스 커서 이동
                        self.rx += dx * self.gain
                        self.ry += dy * self.gain
                        mx = int(self.rx)
                        my = int(self.ry)
                        self.rx -= mx
                        self.ry -= my
                        if mx or my:
                            self.emit_mouse(mx, my)

        # 3. 터치 종료 (손가락 뗌)
        elif count == 0 and self.touch_count > 0:
            if self.active_region in ('L Click', 'R Click'):
                bit = 1 if self.active_region == 'L Click' else 2
                self.schedule(max(timestamp, self.started_time + 0.055), lambda b=bit: (setattr(self, 'buttons', self.buttons & ~b), self.emit_mouse()))
            elif self.active_region and not self.multi_touch and self.travel_distance < 15:
                self.key_tap(self.active_region, timestamp)
            elif self.mode == 'pad' and not self.active_region:
                if self.is_dragging:
                    self.buttons &= ~1
                    self.emit_mouse()
                    self.is_dragging = False
                    self.last_tap_time = -1
                # 탭 판정: 이동 거리 12px 미만, 시간 0.38초 미만
                elif self.travel_distance < 12 and (timestamp - self.started_time < 0.38):
                    # 1손가락: 좌클릭, 2손가락: 우클릭
                    self.click(2 if self.multi_touch else 1, timestamp)
                    self.last_tap_time = timestamp if not self.multi_touch else -1
                else:
                    self.last_tap_time = -1

        self.last_x = x
        self.last_y = y
        self.touch_count = count

    def close(self):
        self.pending_tasks = []
        self.buttons = 0
        self.emit_mouse()
        for c in [29, 42, 56]:
            self.emit_key(c, False)
