#include "save_crc.h"

#include "memory.h"
#include "recomp.h"

#include <array>
#include <cstdio>
#include <cstring>
#include <span>

namespace {
// CRC-32/ISO-HDLC's reflected polynomial, with LM2's caller-supplied initial
// state and without the usual final XOR. This oracle uses no ROM lookup table.
uint32_t reference_crc(uint32_t crc, std::span<const uint8_t> data) {
    for (uint8_t byte : data) {
        crc ^= byte;
        for (int bit = 0; bit != 8; ++bit)
            crc = (crc >> 1) ^ (crc & 1 ? 0xedb88320u : 0u);
    }
    return crc;
}
}

int verify_save_crc() {
    constexpr uint32_t address = 0x003b4b98;
    constexpr uint32_t scratch = 0x09000000;
    constexpr uint32_t destination = scratch + 0x2000;
    mem::commit(scratch, 0x4000);
    mem::commit(mem::STACK_TOP - mem::PAGE, mem::PAGE);
    std::array<uint8_t, 0xf1d> sample{};
    for (size_t i = 0; i < sample.size(); ++i)
        sample[i] = static_cast<uint8_t>((i * 113) ^ (i >> 3));
    size_t tests = 0;
    for (uint32_t alignment = 0; alignment < 4; ++alignment) {
        const uint32_t source = scratch + alignment;
        std::memcpy(mem::ptr(source), sample.data(), sample.size());
        for (size_t size : {size_t{0}, size_t{1}, size_t{3}, size_t{4}, size_t{9}, size_t{26}, sample.size()}) {
            for (uint32_t seed : {0u, 0xffffffffu, 0x10203040u}) {
                Ctx ctx{};
                ctx.r[0] = destination;
                ctx.r[1] = source;
                ctx.r[2] = static_cast<uint32_t>(size);
                ctx.r[13] = mem::STACK_TOP;
                mem::write32(destination, seed);
                recomp_call_indirect(&ctx, address);
                uint32_t expected = reference_crc(seed, std::span(sample).first(size));
                uint32_t actual = mem::read32(destination);
                if (actual != expected || ctx.r[13] != mem::STACK_TOP) {
                    std::fprintf(stderr, "Save CRC failed: alignment=%u size=%zu seed=%08x expected=%08x got=%08x\n",
                                 alignment, size, seed, expected, actual);
                    return 1;
                }
                ++tests;
            }
        }
    }
    std::printf("LM2 original Save CRC ARM %08x -> Windows x64: %zu tests passed\n", address, tests);
    return 0;
}
