#define _GNU_SOURCE
#include <linux/input.h>
#include <linux/uinput.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <poll.h>
#include <fcntl.h>
#include <unistd.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <time.h>

static volatile sig_atomic_t g_running = 1;
static int g_mouse_fd = -1;
static int g_keyboard_fd = -1;
static int g_current_buttons = 0;

static void handle_signal(int s) {
    (void)s;
    g_running = 0;
}

static int emit_event(int fd, int type, int code, int value) {
#ifdef __linux__
    struct input_event ev = {0};
    ev.type = type;
    ev.code = code;
    ev.value = value;
    return write(fd, &ev, sizeof(ev)) == sizeof(ev) ? 0 : -1;
#else
    (void)fd; (void)type; (void)code; (void)value;
    return 0;
#endif
}

static int sync_event(int fd) {
    return emit_event(fd, EV_SYN, SYN_REPORT, 0);
}

/**
 * uinput 가상 마우스/키보드 장치 생성
 */
static int create_uinput_device(int is_keyboard) {
#ifdef __linux__
    int fd = open("/dev/uinput", O_WRONLY);
    if (fd < 0) return -1;

    if (ioctl(fd, UI_SET_EVBIT, EV_KEY)) goto fail;

    if (is_keyboard) {
        for (int i = 1; i < 256; i++) {
            if (ioctl(fd, UI_SET_KEYBIT, i)) goto fail;
        }
    } else {
        if (ioctl(fd, UI_SET_EVBIT, EV_REL)) goto fail;
        int mouse_keys[] = {BTN_LEFT, BTN_RIGHT, BTN_MIDDLE};
        int rel_axes[]   = {REL_X, REL_Y, REL_WHEEL, REL_HWHEEL};

        for (int i = 0; i < 3; i++) {
            if (ioctl(fd, UI_SET_KEYBIT, mouse_keys[i])) goto fail;
        }
        for (int i = 0; i < 4; i++) {
            if (ioctl(fd, UI_SET_RELBIT, rel_axes[i])) goto fail;
        }
    }

    struct uinput_user_dev dev;
    memset(&dev, 0, sizeof(dev));
    snprintf(dev.name, sizeof(dev.name), "WhimTouchpad %s", is_keyboard ? "Keyboard" : "Mouse");
    dev.id.bustype = BUS_USB;
    dev.id.vendor  = 0x1209;
    dev.id.product = is_keyboard ? 0xd002 : 0xd001;

    if (write(fd, &dev, sizeof(dev)) != sizeof(dev) || ioctl(fd, UI_DEV_CREATE)) {
        goto fail;
    }
    return fd;

fail:
    close(fd);
    return -1;
#else
    (void)is_keyboard;
    return 0;
#endif
}

static int get_abs_range(int fd, int code) {
#ifdef __linux__
    struct input_absinfo abs;
    if (ioctl(fd, EVIOCGABS(code), &abs)) return 0;
    return abs.maximum - abs.minimum;
#else
    (void)fd; (void)code;
    return 1;
#endif
}

static int is_multitouch_screen(int fd) {
    return get_abs_range(fd, ABS_MT_POSITION_X) > 0 &&
           get_abs_range(fd, ABS_MT_POSITION_Y) > 0 &&
           get_abs_range(fd, ABS_MT_SLOT) > 0;
}

/**
 * 하단 터치스크린 디바이스 전용 검색 및 개방 (fe5e0000 필터링 & EVIOCGRAB)
 */
static int open_bottom_touchscreen(const char *manual_device, int list_only) {
#ifdef __linux__
    int selected = -1;
    for (int i = 0; i < 64; i++) {
        char path[64], syspath[128], real_dev_path[1024] = {0}, name[128] = {0};
        snprintf(path, sizeof(path), "/dev/input/event%d", i);
        int fd = open(path, O_RDONLY | O_NONBLOCK);
        if (fd < 0) continue;

        snprintf(syspath, sizeof(syspath), "/sys/class/input/event%d/device", i);
        if (!realpath(syspath, real_dev_path)) real_dev_path[0] = 0;
        ioctl(fd, EVIOCGNAME(sizeof(name)), name);

        if (is_multitouch_screen(fd)) {
            if (list_only) {
                printf("%s | %s | %s\n", path, name, real_dev_path);
            } else if (selected < 0) {
                // 수동 지정 또는 RGDS 하단 터치 전용 I2C 컨트롤러(fe5e0000) 자동 매칭
                if ((manual_device && *manual_device && !strcmp(manual_device, path)) ||
                    ((!manual_device || !*manual_device) && strstr(real_dev_path, "fe5e0000"))) {
                    selected = fd;
                    fprintf(stderr, "[whimtouchpad] Attached to bottom touchscreen: %s (%s)\n", path, real_dev_path);
                    continue; // 닫지 않고 유지
                }
            }
        }
        close(fd);
    }
    return selected;
#else
    (void)manual_device; (void)list_only;
    return 0;
#endif
}

int main(int argc, char **argv) {
    if (argc > 1 && !strcmp(argv[1], "--list")) {
        open_bottom_touchscreen(NULL, 1);
        return 0;
    }

    if (argc < 2) {
        fprintf(stderr, "Usage: whimtouchpad_backend <DATA_DIR> [TOUCH_DEVICE]\n");
        return 2;
    }

    const char *data_dir = argv[1];
    const char *manual_touch = argc > 2 ? argv[2] : NULL;

    int touch_fd = open_bottom_touchscreen(manual_touch, 0);
    if (touch_fd < 0) {
        fprintf(stderr, "[whimtouchpad] Bottom touchscreen device not found.\n");
        return 1;
    }

    g_mouse_fd = create_uinput_device(0);
    g_keyboard_fd = create_uinput_device(1);
    if (g_mouse_fd < 0 || g_keyboard_fd < 0) {
        perror("[whimtouchpad] Failed to create uinput virtual device");
        close(touch_fd);
        return 1;
    }

#ifdef __linux__
    // 하단 터치스크린 이벤트를 독점(EVIOCGRAB)하여 데스크톱이나 메인 게임으로 직접 새지 않도록 캡처
    if (ioctl(touch_fd, EVIOCGRAB, 1)) {
        perror("[whimtouchpad] Failed to grab bottom touch device");
        close(touch_fd);
        return 1;
    }
#endif

    // UNIX Domain Socket 설정 (UI 프로세스와의 IPC 통신)
    struct sockaddr_un in_addr = {.sun_family = AF_UNIX};
    struct sockaddr_un ui_addr = {.sun_family = AF_UNIX};
    char in_sock_path[108] = {0};

    snprintf(in_addr.sun_path, sizeof(in_addr.sun_path), "%s/input.sock", data_dir);
    snprintf(ui_addr.sun_path, sizeof(ui_addr.sun_path), "%s/ui.sock", data_dir);
    strncpy(in_sock_path, in_addr.sun_path, sizeof(in_sock_path) - 1);

    unlink(in_sock_path);
    int sock_fd = socket(AF_UNIX, SOCK_DGRAM | SOCK_NONBLOCK, 0);
    if (sock_fd < 0 || bind(sock_fd, (void*)&in_addr, sizeof(in_addr)) != 0) {
        perror("[whimtouchpad] Failed to bind IPC socket");
        return 1;
    }

    struct sigaction sa = {0};
    sa.sa_handler = handle_signal;
    sigemptyset(&sa.sa_mask);
    sigaction(SIGTERM, &sa, NULL);
    sigaction(SIGINT, &sa, NULL);

    int max_x = get_abs_range(touch_fd, ABS_MT_POSITION_X);
    int max_y = get_abs_range(touch_fd, ABS_MT_POSITION_Y);
    double scale_x = max_x > 0 ? (640.0 / max_x) : 1.0;
    double scale_y = max_y > 0 ? (480.0 / max_y) : 1.0;

    int slot = 0;
    int active[32] = {0}, touch_x[32] = {0}, touch_y[32] = {0};

    struct pollfd pfd[2] = {
        {.fd = touch_fd, .events = POLLIN},
        {.fd = sock_fd,  .events = POLLIN}
    };

    fprintf(stderr, "[whimtouchpad] Backend service ready (listening on %s)\n", in_sock_path);

    while (g_running) {
        int pr = poll(pfd, 2, 250);
        if (pr < 0) {
            if (errno == EINTR) continue;
            break;
        }

        // 1. UI 프로세스로부터 수신된 마우스/키보드 방출 명령 처리
        if (pfd[1].revents & POLLIN) {
            char msg[512];
            ssize_t n;
            while ((n = recv(sock_fd, msg, sizeof(msg) - 1, 0)) > 0) {
                msg[n] = 0;
                int dx, dy, bs, v, h, key_code, key_down;

                if (sscanf(msg, "m %d %d %d %d %d", &dx, &dy, &bs, &v, &h) == 5) {
                    int keys[] = {BTN_LEFT, BTN_RIGHT, BTN_MIDDLE};
                    for (int i = 0; i < 3; i++) {
                        if ((g_current_buttons ^ bs) & (1 << i)) {
                            emit_event(g_mouse_fd, EV_KEY, keys[i], (bs >> i) & 1);
                        }
                    }
                    g_current_buttons = bs;
                    if (dx) emit_event(g_mouse_fd, EV_REL, REL_X, dx);
                    if (dy) emit_event(g_mouse_fd, EV_REL, REL_Y, dy);
                    if (v)  emit_event(g_mouse_fd, EV_REL, REL_WHEEL, v);
                    if (h)  emit_event(g_mouse_fd, EV_REL, REL_HWHEEL, h);
                    sync_event(g_mouse_fd);
                } else if (sscanf(msg, "k %d %d", &key_code, &key_down) == 2 && key_code > 0 && key_code < 256) {
                    emit_event(g_keyboard_fd, EV_KEY, key_code, !!key_down);
                    sync_event(g_keyboard_fd);
                } else if (!strcmp(msg, "quit")) {
                    g_running = 0;
                }
            }
        }

        // 2. 하단 터치스크린 raw 입력 읽기 및 UI로 정규화 좌표 전송
        if (pfd[0].revents & POLLIN) {
#ifdef __linux__
            struct input_event ev;
            ssize_t n;
            while ((n = read(touch_fd, &ev, sizeof(ev))) == sizeof(ev)) {
                if (ev.type == EV_SYN && ev.code == SYN_DROPPED) {
                    fprintf(stderr, "[whimtouchpad] Touch frame stream dropped.\n");
                    break;
                }
                if (ev.type == EV_ABS) {
                    if (ev.code == ABS_MT_SLOT) {
                        slot = ev.value;
                    } else if (slot >= 0 && slot < 32) {
                        if (ev.code == ABS_MT_TRACKING_ID) {
                            active[slot] = ev.value >= 0;
                        } else if (ev.code == ABS_MT_POSITION_X) {
                            touch_x[slot] = ev.value;
                        } else if (ev.code == ABS_MT_POSITION_Y) {
                            touch_y[slot] = ev.value;
                        }
                    }
                }
                if (ev.type == EV_SYN && ev.code == SYN_REPORT) {
                    int count = 0;
                    double cx = 0, cy = 0;
                    for (int i = 0; i < 32; i++) {
                        if (active[i]) {
                            count++;
                            cx += touch_x[i] * scale_x;
                            cy += touch_y[i] * scale_y;
                        }
                    }
                    if (count > 0) {
                        cx /= count;
                        cy /= count;
                    }

                    char out_msg[128];
                    struct timespec tm;
                    clock_gettime(CLOCK_MONOTONIC, &tm);
                    double timestamp = tm.tv_sec + tm.tv_nsec / 1e9;
                    int len = snprintf(out_msg, sizeof(out_msg), "t %d %.3f %.3f %.6f", count, cx, cy, timestamp);
                    sendto(sock_fd, out_msg, len, 0, (void*)&ui_addr, sizeof(ui_addr));
                }
            }
#endif
        }
    }

    // 정리 및 해제
#ifdef __linux__
    if (g_mouse_fd >= 0) {
        emit_event(g_mouse_fd, EV_KEY, BTN_LEFT, 0);
        emit_event(g_mouse_fd, EV_KEY, BTN_RIGHT, 0);
        sync_event(g_mouse_fd);
        ioctl(g_mouse_fd, UI_DEV_DESTROY);
        close(g_mouse_fd);
    }
    if (g_keyboard_fd >= 0) {
        ioctl(g_keyboard_fd, UI_DEV_DESTROY);
        close(g_keyboard_fd);
    }
    if (touch_fd >= 0) {
        ioctl(touch_fd, EVIOCGRAB, 0);
        close(touch_fd);
    }
#endif
    if (sock_fd >= 0) close(sock_fd);
    if (*in_sock_path) unlink(in_sock_path);

    fprintf(stderr, "[whimtouchpad] Backend terminated cleanly.\n");
    return 0;
}
