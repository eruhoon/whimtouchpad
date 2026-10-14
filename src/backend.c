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
#ifdef __linux__
#include <sys/prctl.h>
#endif

static volatile sig_atomic_t g_running = 1;
static int g_mouse_fd = -1;
static int g_keyboard_fd = -1;
static int g_touch_fd = -1;
static int g_sock_fd = -1;
static char g_sock_path[108] = {0};
static int g_current_buttons = 0;

static void cleanup_devices(void) {
    static int cleaned = 0;
    if (cleaned) return;
    cleaned = 1;

#ifdef __linux__
    if (g_touch_fd >= 0) {
        ioctl(g_touch_fd, EVIOCGRAB, 0);
        close(g_touch_fd);
        g_touch_fd = -1;
    }
    if (g_mouse_fd >= 0) {
        emit_event(g_mouse_fd, EV_KEY, BTN_LEFT, 0);
        emit_event(g_mouse_fd, EV_KEY, BTN_RIGHT, 0);
        sync_event(g_mouse_fd);
        ioctl(g_mouse_fd, UI_DEV_DESTROY);
        close(g_mouse_fd);
        g_mouse_fd = -1;
    }
    if (g_keyboard_fd >= 0) {
        ioctl(g_keyboard_fd, UI_DEV_DESTROY);
        close(g_keyboard_fd);
        g_keyboard_fd = -1;
    }
#endif
    if (g_sock_fd >= 0) {
        close(g_sock_fd);
        g_sock_fd = -1;
    }
    if (g_sock_path[0]) {
        unlink(g_sock_path);
        g_sock_path[0] = 0;
    }
    fprintf(stderr, "[whimtouchpad] Backend devices and touch grab released cleanly.\n");
}

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

static int score_touch_device(const char *path, const char *name, const char *real_dev_path, int has_slot, const char *manual) {
    if (manual && *manual) {
        if (!strcmp(manual, path)) return 10000;
        return -100;
    }
    int score = 10;
    if (has_slot) score += 50;
    if (real_dev_path && strstr(real_dev_path, "fe5e0000")) score += 500;
    if (name && (strcasestr(name, "bottom") || strcasestr(name, "lower"))) score += 200;
    if (real_dev_path && strcasestr(real_dev_path, "dsi-1")) score += 200;
    if (name && (strcasestr(name, "goodix") || strcasestr(name, "gt9") || strcasestr(name, "gt1"))) score += 100;
    if (real_dev_path && strcasestr(real_dev_path, "goodix")) score += 100;
    if (name && (strcasestr(name, "focaltech") || strcasestr(name, "ft5") || strcasestr(name, "edt-ft"))) score += 100;
    if (real_dev_path && strcasestr(real_dev_path, "focaltech")) score += 100;
    if (name && (strcasestr(name, "gsl") || strcasestr(name, "silead") || strcasestr(name, "chipone") || strcasestr(name, "ilitek"))) score += 100;
    if (name && strcasestr(name, "touchscreen")) score += 50;
    if (name && (strcasestr(name, "top") || strcasestr(name, "upper"))) score -= 200;
    return score;
}

/**
 * 하단 터치스크린 디바이스 다계층 자동 탐색 (우선순위 스코어링 & EVIOCGRAB)
 */
static int open_bottom_touchscreen(const char *manual_device, int list_only) {
#ifdef __linux__
    struct {
        int fd;
        char path[64];
        char name[128];
        char real_dev_path[1024];
        int score;
    } candidates[32];
    int candidate_count = 0;

    for (int i = 0; i < 64; i++) {
        char path[64], syspath[128], real_dev_path[1024] = {0}, name[128] = {0};
        snprintf(path, sizeof(path), "/dev/input/event%d", i);
        int fd = open(path, O_RDONLY | O_NONBLOCK);
        if (fd < 0) continue;

        snprintf(syspath, sizeof(syspath), "/sys/class/input/event%d/device", i);
        if (!realpath(syspath, real_dev_path)) real_dev_path[0] = 0;
        ioctl(fd, EVIOCGNAME(sizeof(name)), name);

        int has_mt = (get_abs_range(fd, ABS_MT_POSITION_X) > 0 && get_abs_range(fd, ABS_MT_POSITION_Y) > 0);
        int has_slot = (get_abs_range(fd, ABS_MT_SLOT) > 0);
        int has_single = (get_abs_range(fd, ABS_X) > 0 && get_abs_range(fd, ABS_Y) > 0);

        if (has_mt || has_single) {
            int score = score_touch_device(path, name, real_dev_path, has_slot, manual_device);
            if (list_only) {
                printf("%s | %s | %s | score=%d%s\n", path, name, real_dev_path, score, has_mt ? " (multitouch)" : "");
                close(fd);
            } else if (score >= 0 && candidate_count < 32) {
                candidates[candidate_count].fd = fd;
                strncpy(candidates[candidate_count].path, path, sizeof(candidates[candidate_count].path) - 1);
                strncpy(candidates[candidate_count].name, name, sizeof(candidates[candidate_count].name) - 1);
                strncpy(candidates[candidate_count].real_dev_path, real_dev_path, sizeof(candidates[candidate_count].real_dev_path) - 1);
                candidates[candidate_count].score = score;
                candidate_count++;
            } else {
                close(fd);
            }
        } else {
            close(fd);
        }
    }

    if (list_only) return 0;
    if (candidate_count == 0) return -1;

    int best_idx = 0;
    for (int i = 1; i < candidate_count; i++) {
        if (candidates[i].score > candidates[best_idx].score) {
            best_idx = i;
        }
    }

    int selected_fd = candidates[best_idx].fd;
    fprintf(stderr, "[whimtouchpad] Attached to bottom touchscreen: %s (%s, score=%d)\n",
            candidates[best_idx].path, candidates[best_idx].name, candidates[best_idx].score);

    for (int i = 0; i < candidate_count; i++) {
        if (i != best_idx) close(candidates[i].fd);
    }
    return selected_fd;
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
        fprintf(stderr, "Usage: whimpad_backend <DATA_DIR> [TOUCH_DEVICE]\n");
        return 2;
    }

    const char *data_dir = argv[1];
    const char *manual_touch = argc > 2 ? argv[2] : getenv("WHIMPAD_TOUCH_DEV");
    if (manual_touch && !*manual_touch) manual_touch = NULL;

    int touch_fd = open_bottom_touchscreen(manual_touch, 0);
    if (touch_fd < 0) {
        fprintf(stderr, "[whimtouchpad] Bottom touchscreen device not found.\n");
        return 1;
    }
    g_touch_fd = touch_fd;

    g_mouse_fd = create_uinput_device(0);
    g_keyboard_fd = create_uinput_device(1);
    if (g_mouse_fd < 0 || g_keyboard_fd < 0) {
        perror("[whimtouchpad] Failed to create uinput virtual device");
        cleanup_devices();
        return 1;
    }

#ifdef __linux__
    // 부모 프로세스(게임 스크립트) 비정상 종료 시 즉시 SIGTERM 수신하여 터치락 누수 방지
    prctl(PR_SET_PDEATHSIG, SIGTERM);

    // 하단 터치스크린 이벤트를 독점(EVIOCGRAB)하여 데스크톱이나 메인 게임으로 직접 새지 않도록 캡처
    if (ioctl(touch_fd, EVIOCGRAB, 1)) {
        perror("[whimtouchpad] Failed to grab bottom touch device");
        cleanup_devices();
        return 1;
    }
#endif

    // 비정상/정상 종료 시 무조건 터치스크린 장치를 반환하도록 atexit 등록
    atexit(cleanup_devices);

    // UNIX Domain Socket 설정 (UI 프로세스와의 IPC 통신)
    struct sockaddr_un in_addr = {.sun_family = AF_UNIX};
    struct sockaddr_un ui_addr = {.sun_family = AF_UNIX};
    char in_sock_path[108] = {0};

    snprintf(in_addr.sun_path, sizeof(in_addr.sun_path), "%s/input.sock", data_dir);
    snprintf(ui_addr.sun_path, sizeof(ui_addr.sun_path), "%s/ui.sock", data_dir);
    strncpy(in_sock_path, in_addr.sun_path, sizeof(in_sock_path) - 1);
    strncpy(g_sock_path, in_sock_path, sizeof(g_sock_path) - 1);

    unlink(in_sock_path);
    int sock_fd = socket(AF_UNIX, SOCK_DGRAM | SOCK_NONBLOCK, 0);
    if (sock_fd < 0 || bind(sock_fd, (void*)&in_addr, sizeof(in_addr)) != 0) {
        perror("[whimtouchpad] Failed to bind IPC socket");
        cleanup_devices();
        return 1;
    }
    g_sock_fd = sock_fd;

    struct sigaction sa = {0};
    sa.sa_handler = handle_signal;
    sigemptyset(&sa.sa_mask);
    sigaction(SIGTERM, &sa, NULL);
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGHUP, &sa, NULL);

    int game_pid = 0;
    const char *game_pid_env = getenv("GAME_PID");
    if (game_pid_env && *game_pid_env) {
        game_pid = atoi(game_pid_env);
    }

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

        // 0. Watchdog: 부모 및 대상 게임 프로세스 생존 확인
        if (getppid() == 1) {
            fprintf(stderr, "[whimtouchpad] Parent process died (re-parented to init). Exiting.\n");
            g_running = 0;
            break;
        }
        if (game_pid > 0 && kill(game_pid, 0) == -1 && errno == ESRCH) {
            fprintf(stderr, "[whimtouchpad] Monitored game process (%d) terminated. Exiting.\n", game_pid);
            g_running = 0;
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

    cleanup_devices();
    return 0;
}
