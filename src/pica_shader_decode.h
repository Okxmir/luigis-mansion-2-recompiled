#pragma once

#include <cstdint>

namespace pica {

struct ArithmeticInstruction {
    uint32_t word;
    uint8_t source[3], address[3];
    uint8_t destination, descriptor;
};

inline ArithmeticInstruction decode_arithmetic(uint32_t word) {
    ArithmeticInstruction d{};
    d.word = word;
    const uint32_t op = word >> 26;
    if (op >= 0x30) {
        d.descriptor = word & 0x1f;
        d.destination = (word >> 24) & 31;
        d.source[0] = (word >> 17) & 31;
        d.source[2] = (word >> 5) & 31;
        const uint8_t relative = (word >> 22) & 3;
        if (op >= 0x38) {
            d.source[1] = (word >> 10) & 127;
            d.address[1] = relative;
        } else {
            d.source[1] = (word >> 12) & 31;
            d.source[2] = (word >> 5) & 127;
            d.address[2] = relative;
        }
    } else {
        d.descriptor = word & 127;
        d.destination = (word >> 21) & 31;
        d.source[1] = (word >> 7) & 31;
        const uint8_t relative = (word >> 19) & 3;
        if (op >= 0x18 && op <= 0x1b) {
            d.source[0] = (word >> 14) & 31;
            d.source[1] = (word >> 7) & 127;
            d.address[1] = relative;
        } else {
            d.source[0] = (word >> 12) & 127;
            d.address[0] = relative;
        }
    }
    return d;
}

} // namespace pica
