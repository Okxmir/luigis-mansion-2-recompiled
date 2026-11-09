#include "video/internal.h"

#include <bit>
#include <cmath>
#include <cstdio>
#include <limits>
#include <random>
#include "pica_shader_jit.h"

namespace pica {
void run_shader_reference(const ShaderSetup &, uint32_t, const Vec4 in[16], Vec4 out[16]);
}

namespace {
using pica::ShaderSetup;
using pica::Vec4;

constexpr uint32_t END = 0x22u << 26;
constexpr uint32_t IDENTITY = 0x1b;
constexpr uint32_t MOV = 0x13u << 26;
unsigned compiled_cases = 0;

bool compare_outputs(const Vec4 expected[16], const Vec4 result[16], const char *label) {
    for (unsigned reg = 0; reg < 16; ++reg) {
        for (unsigned lane = 0; lane < 4; ++lane) {
            float a = expected[reg][lane], b = result[reg][lane];
            if (std::bit_cast<uint32_t>(a) == std::bit_cast<uint32_t>(b) || (std::isnan(a) && std::isnan(b))) continue;
            std::fprintf(stderr, "%s: o%u[%u] expected %a, got %a\n", label, reg, lane, double(a), double(b));
            return false;
        }
    }
    return true;
}

bool compare_shader(const ShaderSetup &setup, const Vec4 inputs[16], const char *label) {
    Vec4 expected[16]{}, result[16]{};
    pica::run_shader_reference(setup, 0, inputs, expected);
    pica::run_shader(setup, 0, inputs, result);
    if (!compare_outputs(expected, result, label)) return false;
#ifdef LGM2_VERTEX_JIT
    static uint64_t revision = 0;
    if (auto compiled = pica::find_compiled_shader(setup, 0, ++revision)) {
        Vec4 native[16]{}, scratch[16];
        compiled(setup.f, inputs, native, scratch);
        ++compiled_cases;
        return compare_outputs(expected, native, "compiled vertex shader");
    }
#endif
    return true;
}
} // namespace

int main() {
    ShaderSetup setup{};
    Vec4 inputs[16]{};
    const uint32_t identity = 15 | (IDENTITY << 5) | (IDENTITY << 14) | (IDENTITY << 23);
    setup.swizzle[0] = identity;
    setup.code[0] = MOV; // seed the output before testing partial writes
    setup.code[2] = END;
    constexpr uint32_t binary_ops[] = {0, 1, 2, 3, 4, 8, 9, 10, 12, 13, 0x18, 0x19, 0x1a, 0x1b};
    constexpr uint32_t unary_ops[] = {5, 6, 7, 11, 14, 15, 0x13};
    std::mt19937 rng(0x3d5);
    constexpr float infinity = std::numeric_limits<float>::infinity();
    constexpr float nan = std::numeric_limits<float>::quiet_NaN();
    const float corners[] = {-0.0f, 0.0f, -infinity, infinity, nan, -1.0f, 1.0f, 0.5f};
    unsigned cases = 0;
    for (unsigned trial = 0; trial < 512; ++trial) {
        for (unsigned lane = 0; lane < 4; ++lane) {
            inputs[0][lane] = corners[rng() & 7];
            inputs[1][lane] = trial & 1 ? float(int(rng() % 1000) - 500) / 256.0f : corners[rng() & 7];
            inputs[2][lane] = float(int(rng() % 1000) - 500) / 256.0f;
            setup.f[5][lane] = inputs[2][lane];
        }
        setup.swizzle[1] = rng() & 0x7fffffff;
        for (uint32_t op : binary_ops) {
            const bool inverted = op >= 0x18;
            const uint32_t operands = inverted ? (1u << 14) | (37u << 7) : (37u << 12) | (1u << 7);
            setup.code[1] = (op << 26) | operands | 1;
            if (!compare_shader(setup, inputs, "binary arithmetic")) return 1;
            ++cases;
        }
        for (uint32_t op : unary_ops) {
            setup.code[1] = (op << 26) | (1u << 12) | 1;
            if (!compare_shader(setup, inputs, "unary arithmetic")) return 1;
            ++cases;
        }
        for (uint32_t op : {0x30u, 0x38u}) {
            const uint32_t operands = op == 0x30 ? (1u << 12) | (37u << 5) : (37u << 10) | (1u << 5);
            setup.code[1] = (op << 26) | operands | 1;
            if (!compare_shader(setup, inputs, "multiply and add")) return 1;
            ++cases;
        }
    }

    // MOVA plus a relative uniform load through a0.x and a0.y.
    inputs[1] = {{2, 3, 0, 0}};
    setup.f[6] = {{6, 7, 8, 9}};
    setup.f[7] = {{10, 11, 12, 13}};
    setup.code[0] = (0x12u << 26) | (1u << 12);
    setup.code[1] = MOV | (1u << 19) | (36u << 12);
    setup.code[2] = MOV | (1u << 21) | (2u << 19) | (36u << 12);
    setup.code[3] = END;
    if (!compare_shader(setup, inputs, "relative uniform addressing")) return 1;
    ++cases;

    // LOOP updates aL between its iterations, and the shader returns at END.
    setup.i[0][0] = 1;
    setup.i[0][1] = 2;
    setup.i[0][2] = 1;
    setup.code[0] = (0x29u << 26) | (1u << 10);
    setup.code[1] = MOV | (3u << 19) | (36u << 12);
    setup.code[2] = END;
    if (!compare_shader(setup, inputs, "loop uniform addressing")) return 1;
    ++cases;

    // IFC can leave a partially written temporary untouched on one branch.
    setup.swizzle[1] = (identity & ~15u) | 8;
    setup.code[0] = (0x2eu << 26) | (1u << 7); // CMP v0.x == v1.x
    setup.code[1] = (0x28u << 26) | (1u << 25) | (2u << 22) | (3u << 10) | 1;
    setup.code[2] = MOV | (16u << 21) | 1;
    setup.code[3] = MOV | (16u << 21) | (1u << 12) | 1;
    setup.code[4] = MOV | (16u << 12);
    setup.code[5] = END;
    for (float value : {2.0f, 3.0f, nan}) {
        inputs[0][0] = value;
        if (!compare_shader(setup, inputs, "conditional temporary write")) return 1;
        ++cases;
    }
    std::printf("PICA vertex shader: %u interpreter and %u compiled comparisons passed\n", cases, compiled_cases);
}
