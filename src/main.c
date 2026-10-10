#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include "uinput.h"

#ifdef USE_SDL2
#include <SDL2/SDL.h>
#endif

static volatile bool g_running = true;

static void handle_signal(int sig) {
    (void)sig;
    g_running = false;
}

int main(int argc, char* argv[]) {
    const char* mode = "touchpad"; // touchpad or keypad
    int screen_index = 1;          // 0: 메인, 1: 보조 스크린 (RGDS 등)

    for (int i = 1; i < argc; i++) {
        if (strncmp(argv[i], "--mode=", 7) == 0) {
            mode = argv[i] + 7;
        } else if (strncmp(argv[i], "--screen=", 9) == 0) {
            screen_index = atoi(argv[i] + 9);
        }
    }

    signal(SIGINT, handle_signal);
    signal(SIGTERM, handle_signal);

    printf("[whimtouchpad] Starting in '%s' mode on display #%d...\n", mode, screen_index);

    if (uinput_init() != 0) {
        fprintf(stderr, "[whimtouchpad] Warning: uinput not available (running in preview mode).\n");
    }

#ifdef USE_SDL2
    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS) != 0) {
        fprintf(stderr, "[whimtouchpad] SDL_Init failed: %s\n", SDL_GetError());
        uinput_close();
        return 1;
    }

    int num_displays = SDL_GetNumVideoDisplays();
    printf("[whimtouchpad] Total video displays detected: %d\n", num_displays);
    if (screen_index >= num_displays) {
        screen_index = num_displays - 1; // 사용 가능한 마지막 디스플레이 선택
    }

    SDL_Rect bounds;
    SDL_GetDisplayBounds(screen_index, &bounds);
    printf("[whimtouchpad] Target display #%d bounds: %dx%d at (%d, %d)\n",
           screen_index, bounds.w, bounds.h, bounds.x, bounds.y);

    SDL_Window* window = SDL_CreateWindow(
        "WhimTouchpad Overlay",
        bounds.x, bounds.y, bounds.w, bounds.h,
        SDL_WINDOW_BORDERLESS | SDL_WINDOW_FULLSCREEN_DESKTOP
    );

    if (!window) {
        fprintf(stderr, "[whimtouchpad] SDL_CreateWindow failed: %s\n", SDL_GetError());
        SDL_Quit();
        uinput_close();
        return 1;
    }

    SDL_Renderer* renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED);

    int last_touch_x = 0;
    int last_touch_y = 0;
    bool is_touch_active = false;

    while (g_running) {
        SDL_Event event;
        while (SDL_PollEvent(&event)) {
            if (event.type == SDL_QUIT) {
                g_running = false;
            } else if (event.type == SDL_FINGERDOWN) {
                is_touch_active = true;
                last_touch_x = (int)(event.tfinger.x * bounds.w);
                last_touch_y = (int)(event.tfinger.y * bounds.h);
            } else if (event.type == SDL_FINGERMOTION && is_touch_active) {
                int curr_x = (int)(event.tfinger.x * bounds.w);
                int curr_y = (int)(event.tfinger.y * bounds.h);
                int dx = (curr_x - last_touch_x);
                int dy = (curr_y - last_touch_y);
                uinput_move_mouse(dx * 2, dy * 2);
                last_touch_x = curr_x;
                last_touch_y = curr_y;
            } else if (event.type == SDL_FINGERUP) {
                is_touch_active = false;
            }
        }

        // 보조 스크린 배경 렌더링 (다크 테마)
        SDL_SetRenderDrawColor(renderer, 24, 24, 27, 255);
        SDL_RenderClear(renderer);

        // 터치패드 영역 테두리 표시
        SDL_SetRenderDrawColor(renderer, 63, 63, 70, 255);
        SDL_Rect pad_rect = { 20, 20, bounds.w - 40, bounds.h - 100 };
        SDL_RenderDrawRect(renderer, &pad_rect);

        // 하단 좌/우 클릭 버튼 영역
        SDL_Rect left_btn = { 20, bounds.h - 70, (bounds.w - 50) / 2, 50 };
        SDL_Rect right_btn = { bounds.w / 2 + 5, bounds.h - 70, (bounds.w - 50) / 2, 50 };
        SDL_SetRenderDrawColor(renderer, 39, 39, 42, 255);
        SDL_RenderFillRect(renderer, &left_btn);
        SDL_RenderFillRect(renderer, &right_btn);

        SDL_RenderPresent(renderer);
        SDL_Delay(16); // ~60fps
    }

    SDL_DestroyRenderer(renderer);
    SDL_DestroyWindow(window);
    SDL_Quit();
#else
    printf("[whimtouchpad] SDL2 disabled build. Running headless event loop.\n");
    while (g_running) {
        usleep(100000);
    }
#endif

    uinput_close();
    printf("[whimtouchpad] Cleanly terminated.\n");
    return 0;
}
