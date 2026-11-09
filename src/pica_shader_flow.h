#pragma once

#include "video/internal.h"

#include <array>

namespace pica {

// Expand uniform-controlled paths. Backends can handle small vertex-dependent
// conditionals and use the interpreter for other control flow.
template<class Arithmetic, class Conditional>
bool specialize_vertex_program(const ShaderSetup &shader, uint32_t pc, Arithmetic arithmetic, Conditional conditional) {
    struct Frame {
        uint32_t end, resume, loop_start, remaining, increment;
    };
    std::array<Frame, 16> frames;
    size_t depth = 0;
    int32_t loop_address = 0;
    for (unsigned step = 0; step < 1024; ++step) {
        while (depth && pc == frames[depth - 1].end) {
            auto &frame = frames[depth - 1];
            if (frame.loop_start) {
                loop_address += frame.increment;
                if (frame.remaining) {
                    --frame.remaining;
                    pc = frame.loop_start;
                    break;
                }
            }
            pc = frame.resume;
            --depth;
        }
        const uint32_t word = shader.code[pc & 4095];
        const uint32_t op = word >> 26;
        const uint32_t count = word & 255;
        const uint32_t dest = (word >> 10) & 4095;
        const bool uniform = (shader.b >> ((word >> 22) & 15)) & 1;
        ++pc;

        if (op < 0x20 || op >= 0x2e) {
            if (!arithmetic(word, loop_address)) return false;
            continue;
        }
        switch (op) {
        case 0x22: return true; // END
        case 0x24: // CALL
        case 0x26: // CALLU
            if (op == 0x26 && !uniform) break;
            if (depth == frames.size()) return false;
            frames[depth++] = {dest + count, pc, 0, 0, 0};
            pc = dest;
            break;
        case 0x27: // IFU
            if (depth == frames.size()) return false;
            frames[depth++] = {uniform ? dest : dest + count, dest + count, 0, 0, 0};
            if (!uniform) pc = dest;
            break;
        case 0x28: // IFC
            if (dest < pc || dest + count - pc > 32 || !conditional(word, pc, dest, dest + count, loop_address))
                return false;
            pc = dest + count;
            break;
        case 0x29: { // LOOP
            if (depth == frames.size() || dest < pc) return false;
            const auto &integer = shader.i[(word >> 22) & 3];
            loop_address = integer[1];
            frames[depth++] = {dest + 1, dest + 1, pc, integer[0], integer[2]};
            break;
        }
        case 0x2d: // JMPU
            if (uniform != bool(count & 1)) pc = dest;
            break;
        case 0x21: // NOP
            break;
        default:
            return false;
        }
    }
    return false;
}

} // namespace pica
