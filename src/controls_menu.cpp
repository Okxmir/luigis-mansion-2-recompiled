#include "controls_menu.h"

#include <imgui.h>
#include <imgui_impl_sdl3.h>
#include <imgui_impl_sdlrenderer3.h>

#include <algorithm>
#include <filesystem>
#include <iterator>
#include <windows.h>

namespace frontend {
namespace {

struct Labels {
    const char *title, *action, *keyboard, *mouse, *gamepad;
    const char *waiting[3];
    const char *clear, *cancel, *save, *reset, *save_error, *swap_sticks;
    const char *buttons[6];
    const char *directions[4];
    const char *mouse_buttons[5];
};

constexpr Labels translations[] = {
    {"Controls", "Action", "Keyboard", "Mouse", "Gamepad",
     {"Press a key", "Press a mouse button", "Press a gamepad button or trigger"},
     "Clear", "Cancel", "Save", "Reset defaults", "Could not save the controls.", "Swap the gamepad sticks",
     {"Start", "Select", "Touch screen", "Swap screens", "D-pad", "Circle Pad"},
     {"Up", "Down", "Left", "Right"}, {"Left click", "Middle click", "Right click", "Button 4", "Button 5"}},
    {"Commandes", "Action", "Clavier", "Souris", "Manette",
     {"Appuyez sur une touche", "Appuyez sur un bouton de la souris", "Appuyez sur un bouton ou une gâchette"},
     "Effacer", "Annuler", "Enregistrer", "Rétablir les réglages", "Impossible d'enregistrer les commandes.",
     "Inverser les sticks de la manette",
     {"Start", "Select", "Écran tactile", "Permuter les écrans", "Croix", "Stick"},
     {"Haut", "Bas", "Gauche", "Droite"}, {"Clic gauche", "Clic milieu", "Clic droit", "Bouton 4", "Bouton 5"}},
    {"Steuerung", "Aktion", "Tastatur", "Maus", "Controller",
     {"Taste drücken", "Maustaste drücken", "Controller-Taste oder Trigger drücken"},
     "Löschen", "Abbrechen", "Speichern", "Standard wiederherstellen", "Speichern der Steuerung fehlgeschlagen.",
     "Controller-Sticks tauschen",
     {"Start", "Select", "Touchscreen", "Bildschirme tauschen", "Steuerkreuz", "Schiebepad"},
     {"Hoch", "Runter", "Links", "Rechts"}, {"Linksklick", "Mittelklick", "Rechtsklick", "Taste 4", "Taste 5"}},
    {"Comandi", "Azione", "Tastiera", "Mouse", "Controller",
     {"Premi un tasto", "Premi un pulsante del mouse", "Premi un pulsante o un grilletto"},
     "Rimuovi", "Annulla", "Salva", "Ripristina predefiniti", "Impossibile salvare i comandi.",
     "Scambia le levette del controller",
     {"Start", "Select", "Touch screen", "Scambia gli schermi", "Croce", "Stick"},
     {"Su", "Giù", "Sinistra", "Destra"}, {"Clic sinistro", "Clic centrale", "Clic destro", "Pulsante 4", "Pulsante 5"}},
    {"Controles", "Acción", "Teclado", "Ratón", "Mando",
     {"Pulsa una tecla", "Pulsa un botón del ratón", "Pulsa un botón o un gatillo del mando"},
     "Borrar", "Cancelar", "Guardar", "Restaurar valores", "No se pudieron guardar los controles.",
     "Intercambiar los sticks del mando",
     {"Start", "Select", "Pantalla táctil", "Intercambiar pantallas", "Cruceta", "Stick"},
     {"Arriba", "Abajo", "Izquierda", "Derecha"}, {"Clic izquierdo", "Clic central", "Clic derecho", "Botón 4", "Botón 5"}},
};

const Labels &labels(int language) {
    return translations[std::clamp(language, 1, 5) - 1];
}

void copy_bindings(const Settings &from, Settings &to) {
    std::copy_n(from.keys, CONTROL_COUNT, to.keys);
    std::copy_n(from.mouse, CONTROL_COUNT, to.mouse);
    std::copy_n(from.pad, CONTROL_COUNT, to.pad);
    to.swap_sticks = from.swap_sticks;
}

std::string action_name(const Labels &text, int action) {
    if (action < C_START) return CONTROLS[action].label;
    if (action < C_UP) return text.buttons[action - C_START];
    if (action < C_CIRCLE_UP) return std::string(text.buttons[4]) + " " + text.directions[action - C_UP];
    if (action < C_TOUCH) return std::string(text.buttons[5]) + " " + text.directions[action - C_CIRCLE_UP];
    return text.buttons[action == C_TOUCH ? 2 : 3];
}

std::string keyboard_label(const Labels &text, int code) {
    switch (code) {
    case SDL_SCANCODE_UP: return text.directions[0];
    case SDL_SCANCODE_DOWN: return text.directions[1];
    case SDL_SCANCODE_LEFT: return text.directions[2];
    case SDL_SCANCODE_RIGHT: return text.directions[3];
    }
    if (code == SDL_SCANCODE_UNKNOWN) return "-";
    // Settings store physical scancodes. Show the character on the player's keyboard layout.
    const auto scancode = SDL_Scancode(code);
    const SDL_Keycode key = SDL_GetKeyFromScancode(scancode, SDL_KMOD_NONE, false);
    const char *name = SDL_GetKeyName(key);
    return name && *name && key != SDLK_UNKNOWN ? name : key_name(code);
}

SDL_FRect last_item_bounds() {
    const ImVec2 min = ImGui::GetItemRectMin(), max = ImGui::GetItemRectMax();
    return {min.x, min.y, max.x - min.x, max.y - min.y};
}

std::string gamepad_label(const Labels &text, int code) {
    switch (code) {
    case PAD_LEFT_TRIGGER: return "LT / L2";
    case PAD_RIGHT_TRIGGER: return "RT / R2";
    case SDL_GAMEPAD_BUTTON_SOUTH: return "A / Cross";
    case SDL_GAMEPAD_BUTTON_EAST: return "B / Circle";
    case SDL_GAMEPAD_BUTTON_WEST: return "X / Square";
    case SDL_GAMEPAD_BUTTON_NORTH: return "Y / Triangle";
    case SDL_GAMEPAD_BUTTON_LEFT_SHOULDER: return "LB / L1";
    case SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER: return "RB / R1";
    case SDL_GAMEPAD_BUTTON_LEFT_STICK: return "L3";
    case SDL_GAMEPAD_BUTTON_RIGHT_STICK: return "R3";
    case SDL_GAMEPAD_BUTTON_START: return text.buttons[0];
    case SDL_GAMEPAD_BUTTON_BACK: return text.buttons[1];
    case SDL_GAMEPAD_BUTTON_DPAD_UP: return text.directions[0];
    case SDL_GAMEPAD_BUTTON_DPAD_DOWN: return text.directions[1];
    case SDL_GAMEPAD_BUTTON_DPAD_LEFT: return text.directions[2];
    case SDL_GAMEPAD_BUTTON_DPAD_RIGHT: return text.directions[3];
    default: return pad_name(code);
    }
}

} // namespace

bool key_pressed(const bool *keys, int code) {
    return code > SDL_SCANCODE_UNKNOWN && code < SDL_SCANCODE_COUNT && keys[code];
}

bool mouse_pressed(SDL_MouseButtonFlags buttons, int code) {
    return code >= SDL_BUTTON_LEFT && code <= SDL_BUTTON_X2 && (buttons & SDL_BUTTON_MASK(code));
}

bool pad_pressed(SDL_Gamepad *pad, int code) {
    if (code == PAD_LEFT_TRIGGER)
        return SDL_GetGamepadAxis(pad, SDL_GAMEPAD_AXIS_LEFT_TRIGGER) > TRIGGER_THRESHOLD;
    if (code == PAD_RIGHT_TRIGGER)
        return SDL_GetGamepadAxis(pad, SDL_GAMEPAD_AXIS_RIGHT_TRIGGER) > TRIGGER_THRESHOLD;
    return code >= 0 && code < SDL_GAMEPAD_BUTTON_COUNT && SDL_GetGamepadButton(pad, SDL_GamepadButton(code));
}

bool ControlsMenu::init(SDL_Window *window, SDL_Renderer *renderer) {
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO &io = ImGui::GetIO();
    io.IniFilename = nullptr;
    io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard;
    wchar_t windows[MAX_PATH];
    const UINT length = GetWindowsDirectoryW(windows, MAX_PATH);
    if (length && length < MAX_PATH) {
        const auto font = std::filesystem::path(windows) / "Fonts" / "segoeui.ttf";
        std::error_code error;
        if (std::filesystem::is_regular_file(font, error)) {
            const auto path = font.u8string();
            io.FontDefault = io.Fonts->AddFontFromFileTTF(reinterpret_cast<const char *>(path.c_str()), 16);
        }
    }
    ImGui::StyleColorsDark();
    ImGuiStyle &style = ImGui::GetStyle();
    style.FontSizeBase = 16;
    style.WindowRounding = 9;
    style.FrameRounding = 5;
    style.WindowPadding = {16, 14};
    style.CellPadding = {6, 4};
    style.Colors[ImGuiCol_WindowBg] = {0.06f, 0.09f, 0.09f, 0.98f};
    style.Colors[ImGuiCol_Button] = {0.13f, 0.27f, 0.21f, 1};
    style.Colors[ImGuiCol_ButtonHovered] = {0.18f, 0.37f, 0.28f, 1};
    style.Colors[ImGuiCol_ButtonActive] = {0.22f, 0.44f, 0.31f, 1};

    const bool platform_ready = ImGui_ImplSDL3_InitForSDLRenderer(window, renderer);
    enabled = platform_ready && ImGui_ImplSDLRenderer3_Init(renderer);
    if (!enabled) {
        if (platform_ready) ImGui_ImplSDL3_Shutdown();
        ImGui::DestroyContext();
    }
    return enabled;
}

void ControlsMenu::show(const Settings &settings) {
    copy_bindings(settings, draft);
    open = true;
    waiting = -1;
    save_failed = false;
}

void ControlsMenu::assign(int code) {
    int *bindings = device == Keyboard ? draft.keys : device == Mouse ? draft.mouse : draft.pad;
    const int empty = device == Gamepad ? PAD_NONE : 0;
    if (code != empty) {
        for (int i = 0; i < CONTROL_COUNT; ++i) {
            if (bindings[i] == code) bindings[i] = empty;
        }
    }
    bindings[waiting] = code;
    waiting = -1;
}

bool ControlsMenu::event(const SDL_Event &event, const Settings &settings) {
    if (!enabled) return false;
    if (event.type == SDL_EVENT_KEY_DOWN && !event.key.repeat) {
        if (event.key.scancode == SDL_SCANCODE_ESCAPE && open) {
            if (waiting >= 0) waiting = -1;
            else open = false;
            return true;
        }
        if (event.key.scancode == SDL_SCANCODE_F4) {
            if (open) open = false;
            else show(settings);
            return true;
        }
        if (open && waiting >= 0 && device == Keyboard && event.key.scancode != SDL_SCANCODE_UNKNOWN) {
            assign(event.key.scancode);
            return true;
        }
    }
    if (open && waiting >= 0 && device == Mouse && event.type == SDL_EVENT_MOUSE_BUTTON_DOWN &&
        event.button.button >= SDL_BUTTON_LEFT && event.button.button <= SDL_BUTTON_X2) {
        const SDL_FPoint point{event.button.x, event.button.y};
        const bool footer_click = event.button.button == SDL_BUTTON_LEFT &&
            std::any_of(std::begin(mouse_exceptions), std::end(mouse_exceptions),
                        [&](const SDL_FRect &rect) { return SDL_PointInRectFloat(&point, &rect); });
        if (!footer_click) {
            assign(event.button.button);
            return true;
        }
    }
    if (waiting >= 0 && device == Gamepad && open) {
        if (event.type == SDL_EVENT_GAMEPAD_BUTTON_DOWN) assign(event.gbutton.button);
        if (event.type == SDL_EVENT_GAMEPAD_AXIS_MOTION && event.gaxis.value > TRIGGER_THRESHOLD) {
            if (event.gaxis.axis == SDL_GAMEPAD_AXIS_LEFT_TRIGGER) assign(PAD_LEFT_TRIGGER);
            if (event.gaxis.axis == SDL_GAMEPAD_AXIS_RIGHT_TRIGGER) assign(PAD_RIGHT_TRIGGER);
        }
    }
    ImGui_ImplSDL3_ProcessEvent(&event);
    return open && (event.type == SDL_EVENT_KEY_DOWN || event.type == SDL_EVENT_GAMEPAD_BUTTON_DOWN);
}

bool ControlsMenu::captures_mouse(float x, float y) const {
    const SDL_FPoint point{x, y};
    return enabled && SDL_PointInRectFloat(&point, &toggle_button);
}

void ControlsMenu::draw(SDL_Renderer *renderer, Settings &settings) {
    if (!enabled) return;
    ImGui_ImplSDLRenderer3_NewFrame();
    ImGui_ImplSDL3_NewFrame();
    ImGui::NewFrame();
    const Labels &text = labels(settings.language);
    const ImVec2 size = ImGui::GetIO().DisplaySize;
    toggle_button = {};
    std::fill(std::begin(mouse_exceptions), std::end(mouse_exceptions), SDL_FRect{});
    if (!open) {
        ImGui::SetNextWindowPos({size.x - 8, 8}, ImGuiCond_Always, {1, 0});
        ImGui::Begin("##controls_button", nullptr, ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_NoBackground |
                     ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoSavedSettings | ImGuiWindowFlags_NoNavFocus);
        const std::string button = std::string(text.title) + "  (F4)";
        if (ImGui::Button(button.c_str())) show(settings);
        toggle_button = last_item_bounds();
        ImGui::End();
    }

    if (open && size.x > 16 && size.y > 16) {
        const auto footer_button = [&](int index, const char *label) {
            const bool clicked = ImGui::Button(label);
            mouse_exceptions[index] = last_item_bounds();
            return clicked;
        };
        ImGui::SetNextWindowPos({size.x / 2, size.y / 2}, ImGuiCond_Always, {0.5f, 0.5f});
        ImGui::SetNextWindowSize({std::min(680.0f, size.x - 16), std::min(740.0f, size.y - 16)}, ImGuiCond_Always);
        const std::string title = std::string(text.title) + "###controls";
        if (ImGui::Begin(title.c_str(), &open, ImGuiWindowFlags_NoCollapse | ImGuiWindowFlags_NoMove |
                        ImGuiWindowFlags_NoResize | ImGuiWindowFlags_NoSavedSettings)) {
            ImGui::Checkbox(text.swap_sticks, &draft.swap_sticks);
            if (ImGui::BeginTable("bindings", 4, ImGuiTableFlags_RowBg | ImGuiTableFlags_BordersInnerV |
                                  ImGuiTableFlags_ScrollY, {0, -ImGui::GetFrameHeightWithSpacing() * 3})) {
                ImGui::TableSetupColumn(text.action, ImGuiTableColumnFlags_WidthStretch, 1.3f);
                ImGui::TableSetupColumn(text.keyboard);
                ImGui::TableSetupColumn(text.mouse);
                ImGui::TableSetupColumn(text.gamepad, ImGuiTableColumnFlags_WidthStretch, 1.3f);
                ImGui::TableSetupScrollFreeze(0, 1);
                ImGui::TableHeadersRow();
                for (int i = 0; i < CONTROL_COUNT; ++i) {
                    ImGui::PushID(i);
                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    ImGui::AlignTextToFramePadding();
                    ImGui::TextUnformatted(action_name(text, i).c_str());
                    const int mouse = draft.mouse[i];
                    const std::string names[] = {
                        keyboard_label(text, draft.keys[i]),
                        mouse ? text.mouse_buttons[mouse - SDL_BUTTON_LEFT] : "-",
                        gamepad_label(text, draft.pad[i]),
                    };
                    for (int column = 0; column < 3; ++column) {
                        ImGui::PushID(column);
                        ImGui::TableSetColumnIndex(column + 1);
                        const bool selected = waiting == i && int(device) == column;
                        const std::string caption = (selected ? "..." : names[column]) + std::string("###binding");
                        if (ImGui::Button(caption.c_str(), {-FLT_MIN, 0})) {
                            device = Device(column);
                            waiting = i;
                        }
                        ImGui::PopID();
                    }
                    ImGui::PopID();
                }
                ImGui::EndTable();
            }
            if (waiting >= 0) {
                ImGui::TextUnformatted(text.waiting[device]);
                ImGui::SameLine();
                if (footer_button(0, text.clear)) assign(device == Gamepad ? PAD_NONE : 0);
            } else {
                ImGui::Dummy({0, ImGui::GetFrameHeight()});
            }
            if (footer_button(1, text.reset)) {
                draft.reset_controls();
                waiting = -1;
            }
            ImGui::SameLine();
            if (footer_button(2, text.cancel)) open = false;
            ImGui::SameLine();
            if (footer_button(3, text.save)) {
                Settings updated = settings;
                copy_bindings(draft, updated);
                save_failed = !updated.save();
                if (!save_failed) {
                    copy_bindings(updated, settings);
                    open = false;
                }
            }
            if (save_failed) ImGui::TextWrapped("%s", text.save_error);
        }
        ImGui::End();
    }
    ImGui::Render();

    int width, height;
    SDL_RendererLogicalPresentation mode;
    SDL_GetRenderLogicalPresentation(renderer, &width, &height, &mode);
    SDL_SetRenderLogicalPresentation(renderer, 0, 0, SDL_LOGICAL_PRESENTATION_DISABLED);
    ImGui_ImplSDLRenderer3_RenderDrawData(ImGui::GetDrawData(), renderer);
    SDL_SetRenderLogicalPresentation(renderer, width, height, mode);
}

} // namespace frontend
