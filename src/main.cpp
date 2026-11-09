#include "dump.h"
#include "frontend/frontend.h"
#include "game_code.h"
#include "kernel/kernel.h"
#include "lm2_services.h"
#include "loader.h"
#include "log.h"
#include "memory.h"
#include "platform.h"
#include "save_crc.h"
#include "save_storage.h"

#include <SDL3/SDL.h>
#include <windows.h>
#include <bcrypt.h>

#include <array>
#include <cstdio>
#include <filesystem>
#include <string_view>

namespace game_code {
const RecompEntry *functions() { return recomp_functions; }
size_t function_count() { return recomp_function_count; }
}

namespace {
constexpr uint64_t europe_title = 0x0004000000076500;

void check_original_code(const std::vector<uint8_t> &code) {
    constexpr std::array<uint8_t, 32> expected = {
        0xfe, 0xea, 0xa7, 0x13, 0x50, 0xc2, 0x71, 0x2c, 0x54, 0x02, 0xfb, 0xee, 0xfa, 0x9b, 0xe4, 0xaa,
        0xed, 0x0a, 0x77, 0x44, 0x2d, 0xf4, 0x3a, 0xf0, 0xc1, 0x43, 0x26, 0xb2, 0x52, 0x4c, 0xa2, 0xc8,
    };
    if (code.size() != 0x850000) fatal("Incompatible LM2 executable size");
    std::array<uint8_t, 32> hash{};
    auto status = BCryptHash(BCRYPT_SHA256_ALG_HANDLE, nullptr, 0, const_cast<PUCHAR>(code.data()),
                             static_cast<ULONG>(code.size()), hash.data(), static_cast<ULONG>(hash.size()));
    if (status < 0 || hash != expected) fatal("The supplied cartridge code does not match this build");
}

GameImage load_lm2(const char *path) {
    if (peek_program_id(path) != europe_title) fatal("Expected the decrypted LM2 European cartridge (CTR-P-AGGP)");
    open_dump(path);
    check_original_code(dump().code());
    mem::init();
    return load_game();
}

void play(const char *path) {
    auto image = load_lm2(path);
    lm2::lock_save_directory(platform::state_dir());
    register_lm2_services();
    kernel::init(image);
    kernel::run(image);
}
}

int main(int argc, char **argv) {
    const bool crc = argc == 3 && std::string_view(argv[1]) == "--verify-crc";
    if (argc > 2 && !crc) {
        std::fprintf(stderr, "Usage: LuigisMansion2 [LM2-EUR.cxi] or LuigisMansion2 --verify-crc LM2-EUR.cxi\n");
        return 2;
    }
    if (argc == 2 && std::string_view(argv[1]) == "--help") {
        std::puts("LuigisMansion2 [LM2-EUR.cxi]\nLuigisMansion2 --verify-crc LM2-EUR.cxi");
        return 0;
    }
    log_cfg::init();
    const char *base = SDL_GetBasePath();
    const auto executable_dir = std::filesystem::path(base ? base : ".");
    auto default_path = executable_dir / "LM2-EUR.cxi";
    if (argc == 1 && !std::filesystem::is_regular_file(default_path))
        default_path = executable_dir / ".." / "extracted" / "LM2-EUR.cxi";
    auto path = crc ? std::string(argv[2]) : argc == 2 ? std::string(argv[1]) : default_path.string();
    if (peek_program_id(path) != europe_title) fatal("Supply a decrypted LM2 European cartridge: %s", path.c_str());
    if (crc) {
        load_lm2(path.c_str());
        return verify_save_crc();
    }
    frontend::run(play, path.c_str());
}
