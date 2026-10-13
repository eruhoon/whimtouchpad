#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>

#ifdef __linux__
#include <linux/uinput.h>
#include <linux/input.h>
// 가상 입력 디바이스 파일 디스크립터
static int uinput_fd = -1;
#endif

/**
 * uinput 가상 마우스 및 키보드 장치 초기화
 */
int uinput_init(void) {
#ifdef __linux__
    uinput_fd = open("/dev/uinput", O_WRONLY | O_NONBLOCK);
    if (uinput_fd < 0) {
        perror("[whimtouchpad] Failed to open /dev/uinput");
        return -1;
    }

    // 마우스 이벤트 활성화 (상대 좌표 이동 + 좌/우/중간 버튼 + 휠)
    ioctl(uinput_fd, UI_SET_EVBIT, EV_REL);
    ioctl(uinput_fd, UI_SET_RELBIT, REL_X);
    ioctl(uinput_fd, UI_SET_RELBIT, REL_Y);
    ioctl(uinput_fd, UI_SET_RELBIT, REL_WHEEL);

    ioctl(uinput_fd, UI_SET_EVBIT, EV_KEY);
    ioctl(uinput_fd, UI_SET_KEYBIT, BTN_LEFT);
    ioctl(uinput_fd, UI_SET_KEYBIT, BTN_RIGHT);
    ioctl(uinput_fd, UI_SET_KEYBIT, BTN_MIDDLE);

    // 보조 키패드용 주요 키 활성화 (ESC, ENTER, SPACE, TAB, F1~F12, 숫자패드 등)
    int keys_to_enable[] = {
        KEY_ESC, KEY_ENTER, KEY_SPACE, KEY_TAB, KEY_BACKSPACE,
        KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT,
        KEY_F1, KEY_F2, KEY_F3, KEY_F4, KEY_F5, KEY_F6,
        KEY_F7, KEY_F8, KEY_F9, KEY_F10, KEY_F11, KEY_F12,
        KEY_LEFTSHIFT, KEY_LEFTCTRL, KEY_LEFTALT
    };
    size_t num_keys = sizeof(keys_to_enable) / sizeof(keys_to_enable[0]);
    for (size_t i = 0; i < num_keys; i++) {
        ioctl(uinput_fd, UI_SET_KEYBIT, keys_to_enable[i]);
    }

    struct uinput_setup usetup;
    memset(&usetup, 0, sizeof(usetup));
    usetup.id.bustype = BUS_USB;
    usetup.id.vendor  = 0x1234; /* WhimTouchpad 가상 디바이스 */
    usetup.id.product = 0x5678;
    strcpy(usetup.name, "WhimTouchpad Virtual Input");

    ioctl(uinput_fd, UI_DEV_SETUP, &usetup);
    ioctl(uinput_fd, UI_DEV_CREATE);

    printf("[whimtouchpad] Virtual input device registered successfully.\n");
    return 0;
#else
    printf("[whimtouchpad] Emulated uinput init (non-linux platform).\n");
    return 0;
#endif
}

/**
 * 상대 좌표 마우스 이동
 */
void uinput_move_mouse(int dx, int dy) {
#ifdef __linux__
    if (uinput_fd < 0) return;
    struct input_event ev[3];
    memset(ev, 0, sizeof(ev));

    ev[0].type = EV_REL;
    ev[0].code = REL_X;
    ev[0].value = dx;

    ev[1].type = EV_REL;
    ev[1].code = REL_Y;
    ev[1].value = dy;

    ev[2].type = EV_SYN;
    ev[2].code = SYN_REPORT;
    ev[2].value = 0;

    write(uinput_fd, ev, sizeof(ev));
#else
    (void)dx; (void)dy;
#endif
}

/**
 * 마우스 버튼 클릭/릴리즈 (BTN_LEFT, BTN_RIGHT)
 */
void uinput_mouse_button(int button_code, int is_pressed) {
#ifdef __linux__
    if (uinput_fd < 0) return;
    struct input_event ev[2];
    memset(ev, 0, sizeof(ev));

    ev[0].type = EV_KEY;
    ev[0].code = button_code;
    ev[0].value = is_pressed ? 1 : 0;

    ev[1].type = EV_SYN;
    ev[1].code = SYN_REPORT;
    ev[1].value = 0;

    write(uinput_fd, ev, sizeof(ev));
#else
    (void)button_code; (void)is_pressed;
#endif
}

/**
 * 가상 키보드 키 누름/뗌
 */
void uinput_send_key(int key_code, int is_pressed) {
#ifdef __linux__
    if (uinput_fd < 0) return;
    struct input_event ev[2];
    memset(ev, 0, sizeof(ev));

    ev[0].type = EV_KEY;
    ev[0].code = key_code;
    ev[0].value = is_pressed ? 1 : 0;

    ev[1].type = EV_SYN;
    ev[1].code = SYN_REPORT;
    ev[1].value = 0;

    write(uinput_fd, ev, sizeof(ev));
#else
    (void)key_code; (void)is_pressed;
#endif
}

/**
 * 종료 시 디바이스 해제
 */
void uinput_close(void) {
#ifdef __linux__
    if (uinput_fd >= 0) {
        ioctl(uinput_fd, UI_DEV_DESTROY);
        close(uinput_fd);
        uinput_fd = -1;
    }
#endif
}
