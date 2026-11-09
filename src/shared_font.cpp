#include "hle/service.h"
#include "log.h"
#include "memory.h"

#include <SDL3/SDL.h>

#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <vector>

namespace hle {
namespace {
constexpr uint32_t address = mem::LINEAR_BASE + 0x05000000;
constexpr uint32_t prefix_size = 0x80;
constexpr uint32_t size_limit = 0x00400000;

uint32_t read32(const std::vector<uint8_t> &data, size_t at) {
    uint32_t value;
    std::memcpy(&value, data.data() + at, sizeof value);
    return value;
}

void relocate(std::vector<uint8_t> &data, size_t at) {
    uint32_t offset = read32(data, at);
    if (!offset) return;
    if (offset >= data.size()) fatal("Shared font pointer at %#zx is out of range", at);
    uint32_t absolute = address + prefix_size + offset;
    std::memcpy(data.data() + at, &absolute, sizeof absolute);
}

void relocate_sections(std::vector<uint8_t> &data) {
    if (data.size() < 20 || std::memcmp(data.data(), "CFNT", 4) ||
        data[4] != 0xff || data[5] != 0xfe || read32(data, 12) != data.size())
        fatal("Invalid shared font header");
    size_t offset = size_t(data[6]) | size_t(data[7]) << 8;
    if (offset < 20 || offset > data.size()) fatal("Invalid shared font header length");
    uint32_t sections = read32(data, 16);
    bool font_info = false;
    bool sheets = false;
    for (uint32_t i = 0; i < sections; ++i) {
        if (data.size() - offset < 8) fatal("Truncated shared font section");
        const char *tag = reinterpret_cast<const char *>(data.data() + offset);
        uint32_t size = read32(data, offset + 4);
        if (size < 8 || size > data.size() - offset) fatal("Invalid shared font section length");
        if (!std::memcmp(tag, "FINF", 4) && size >= 32) {
            for (size_t field : {16, 20, 24}) relocate(data, offset + field);
            font_info = true;
        } else if (!std::memcmp(tag, "TGLP", 4) && size >= 32) {
            relocate(data, offset + 28);
            sheets = true;
        } else if (!std::memcmp(tag, "CWDH", 4) && size >= 16) {
            relocate(data, offset + 12);
        } else if (!std::memcmp(tag, "CMAP", 4) && size >= 20) {
            relocate(data, offset + 16);
        }
        offset += size;
    }
    if (!font_info || !sheets || offset != data.size()) fatal("Invalid shared font sections");
    data[3] = 'U';
}

std::shared_ptr<kernel::SharedMemory> load_font() {
    const char *configured = std::getenv("LGM2_SHARED_FONT");
    const char *base = SDL_GetBasePath();
    auto path = configured && *configured ? std::filesystem::path(configured)
                                          : std::filesystem::path(base ? base : ".") / "shared-font.bcfnt";
    std::ifstream stream(path, std::ios::binary | std::ios::ate);
    const auto length = stream.tellg();
    if (length <= 0 || length > size_limit - prefix_size)
        fatal("Missing or invalid 3DS-compatible shared font: %s", path.string().c_str());
    std::vector<uint8_t> data(static_cast<size_t>(length));
    stream.seekg(0);
    if (!stream.read(reinterpret_cast<char *>(data.data()), length)) fatal("Could not read shared font");
    relocate_sections(data);

    auto font = std::make_shared<kernel::SharedMemory>();
    font->name = "APT shared font";
    font->address = address;
    font->size = static_cast<uint32_t>(mem::page_up(prefix_size + data.size()));
    font->mapped = true;
    mem::commit(address, font->size);
    kernel::k().regions[address] = {font->size, 1, 6};
    mem::write32(address, 2); // shared-font load completed
    mem::write32(address + 4, 1); // standard Western/Japanese region font
    mem::write32(address + 8, static_cast<uint32_t>(data.size()));
    std::memcpy(mem::ptr(address + prefix_size), data.data(), data.size());
    LOG("APT shared font: %s (%zu bytes)", path.string().c_str(), data.size());
    return font;
}
}

void reply_lm2_shared_font(Request &req) {
    static const auto font = load_font();
    auto response = req.reply(2, 2);
    response.push(font->address);
    response.push_handles({kernel::add_handle(font)});
}
}
