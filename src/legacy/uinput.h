#ifndef UINPUT_H
#define UINPUT_H

#ifdef __cplusplus
extern "C" {
#endif

int  uinput_init(void);
void uinput_move_mouse(int dx, int dy);
void uinput_mouse_button(int button_code, int is_pressed);
void uinput_send_key(int key_code, int is_pressed);
void uinput_close(void);

#ifdef __cplusplus
}
#endif

#endif // UINPUT_H
