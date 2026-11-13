#pragma once

#include <SDL3/SDL.h>
#include "frontend/settings.h"

namespace frontend {

constexpr int TRIGGER_THRESHOLD = 16000;

bool key_pressed(const bool *keys, int code);
bool mouse_pressed(SDL_MouseButtonFlags buttons, int code);
bool pad_pressed(SDL_Gamepad *pad, int code);

class ControlsMenu {
public:
    bool init(SDL_Window *window, SDL_Renderer *renderer);
    bool event(const SDL_Event &event, const Settings &settings);
    bool blocks_gameplay() const { return open; }
    bool captures_mouse(float x, float y) const;
    void draw(SDL_Renderer *renderer, Settings &settings);

private:
    enum Device { Keyboard, Mouse, Gamepad };

    void show(const Settings &settings);
    void assign(int code);

    bool enabled = false, open = false, save_failed = false;
    int waiting = -1;
    Device device = Keyboard;
    Settings draft;
    SDL_FRect toggle_button{};
    SDL_FRect mouse_exceptions[4]{};
};

} // namespace frontend
