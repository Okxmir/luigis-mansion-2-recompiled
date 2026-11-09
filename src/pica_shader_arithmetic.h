#pragma once

#include <array>
#include <atomic>
#include <cmath>
#include <immintrin.h>
#include <intrin.h>

namespace pica {
namespace {

struct ArithmeticInstruction {
    uint32_t word;
    uint8_t source[3], address[3];
    uint8_t destination, descriptor;
};

ArithmeticInstruction decode_arithmetic(uint32_t word) {
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

constexpr auto shader_swizzles() {
    std::array<std::array<uint8_t, 16>, 256> table{};
    for (unsigned selector = 0; selector < table.size(); ++selector) {
        for (unsigned lane = 0; lane < 4; ++lane) {
            unsigned source_lane = (selector >> (6 - 2 * lane)) & 3;
            for (unsigned byte = 0; byte < 4; ++byte) {
                table[selector][lane * 4 + byte] = uint8_t(source_lane * 4 + byte);
            }
        }
    }
    return table;
}

constexpr auto SWIZZLE_BYTES = shader_swizzles();

inline __m128 shader_operand(const Vec4 &v, uint32_t selector, bool negate, bool ssse3) {
    __m128 result;
    if (selector == 0x1b) {
        result = _mm_loadu_ps(v.v);
    } else if (ssse3) {
        const auto *order = reinterpret_cast<const __m128i *>(SWIZZLE_BYTES[selector].data());
        result = _mm_castsi128_ps(_mm_shuffle_epi8(_mm_castps_si128(_mm_loadu_ps(v.v)), _mm_loadu_si128(order)));
    } else {
        result = _mm_setr_ps(v[(selector >> 6) & 3], v[(selector >> 4) & 3], v[(selector >> 2) & 3], v[selector & 3]);
    }
    return negate ? _mm_xor_ps(result, _mm_set1_ps(-0.0f)) : result;
}

inline __m128 shader_multiply(__m128 a, __m128 b) {
    const __m128 product = _mm_mul_ps(a, b);
    // PICA multiplies 0 by infinity to 0 and preserves a NaN operand.
    const __m128 invalid = _mm_and_ps(_mm_cmpord_ps(a, b), _mm_cmpunord_ps(product, product));
    return _mm_andnot_ps(invalid, product);
}

template<int Lane>
inline float shader_lane(__m128 value) {
    return _mm_cvtss_f32(_mm_shuffle_ps(value, value, _MM_SHUFFLE(Lane, Lane, Lane, Lane)));
}

inline void shader_store(Vec4 &dst, __m128 value, uint32_t mask) {
    if (mask != 15) {
        const __m128 lanes = _mm_castsi128_ps(_mm_setr_epi32(-int((mask >> 3) & 1), -int((mask >> 2) & 1),
                                                           -int((mask >> 1) & 1), -int(mask & 1)));
        value = _mm_or_ps(_mm_and_ps(lanes, value), _mm_andnot_ps(lanes, _mm_loadu_ps(dst.v)));
    }
    _mm_storeu_ps(dst.v, value);
}

inline bool compare(float a, float b, uint32_t op) {
    switch (op) {
    case 0: return a == b;
    case 1: return a != b;
    case 2: return a < b;
    case 3: return a <= b;
    case 4: return a > b;
    case 5: return a >= b;
    default: return true;
    }
}

void run_arithmetic(const ShaderSetup &s, uint32_t pc, uint32_t ins, Vec4 const in[16], Vec4 out[16],
                    Vec4 tmp[16], int32_t addr[4], bool cond[2]) {
    static const bool ssse3 = [] {
        int cpu[4];
        __cpuid(cpu, 1);
        return (cpu[2] & (1 << 9)) != 0;
    }();
    static const Vec4 ones = {{1, 1, 1, 1}};
    thread_local ArithmeticInstruction cache[4096]{};
    ArithmeticInstruction &d = cache[pc & 4095];
    if (d.word != ins) d = decode_arithmetic(ins);
    const uint32_t op = ins >> 26;
    const uint32_t desc = s.swizzle[d.descriptor];
    const uint32_t mask = desc & 15;
    auto operand = [&](unsigned id, unsigned shift) {
        uint32_t reg = d.source[id];
        int32_t index = int32_t(reg) - 32 + addr[d.address[id]];
        const Vec4 &v = reg < 16 ? in[reg] : reg < 32 ? tmp[reg - 16] : index >= 0 && index < 96 ? s.f[index] : ones;
        return shader_operand(v, (desc >> (shift + 1)) & 255, (desc >> shift) & 1, ssse3);
    };

    const __m128 a = operand(0, 4);
    __m128 r;
    switch (op) {
    case 0x05:
        r = _mm_set1_ps(std::exp2(shader_lane<0>(a)));
        break;
    case 0x06:
        r = _mm_set1_ps(std::log2(shader_lane<0>(a)));
        break;
    case 0x07: {
        const float x = shader_lane<0>(a), y = shader_lane<1>(a), w = shader_lane<3>(a);
        r = _mm_setr_ps(std::fmax(x, 0.0f), std::fmin(std::fmax(y, -127.9961f), 127.9961f), 0.0f, std::fmax(w, 0.0f));
        cond[0] = x >= 0.0f;
        cond[1] = w >= 0.0f;
        break;
    }
    case 0x0b:
        r = _mm_setr_ps(std::floor(shader_lane<0>(a)), std::floor(shader_lane<1>(a)),
                        std::floor(shader_lane<2>(a)), std::floor(shader_lane<3>(a)));
        break;
    case 0x0e:
        r = _mm_set1_ps(1.0f / shader_lane<0>(a));
        break;
    case 0x0f:
        r = _mm_set1_ps(1.0f / std::sqrt(shader_lane<0>(a)));
        break;
    case 0x12:
        if (mask & 8) addr[1] = int32_t(shader_lane<0>(a));
        if (mask & 4) addr[2] = int32_t(shader_lane<1>(a));
        return;
    case 0x13:
        r = a;
        break;
    default: {
        const __m128 b = operand(1, 13);
        switch (op) {
        case 0x00:
            r = _mm_add_ps(a, b);
            break;
        case 0x01:
        case 0x02:
        case 0x03:
        case 0x18: {
            const __m128 product = shader_multiply(a, b);
            float sum = shader_lane<0>(product) + shader_lane<1>(product) + shader_lane<2>(product);
            if (op != 0x01) sum += shader_lane<3>(op == 0x02 ? product : b);
            r = _mm_set1_ps(sum);
            break;
        }
        case 0x04:
        case 0x19:
            r = _mm_setr_ps(1.0f, shader_lane<1>(shader_multiply(a, b)), shader_lane<2>(a), shader_lane<3>(b));
            break;
        case 0x08:
            r = shader_multiply(a, b);
            break;
        case 0x09:
        case 0x1a:
            r = _mm_and_ps(_mm_cmpge_ps(a, b), _mm_set1_ps(1.0f));
            break;
        case 0x0a:
        case 0x1b:
            r = _mm_and_ps(_mm_cmplt_ps(a, b), _mm_set1_ps(1.0f));
            break;
        case 0x0c:
            r = _mm_max_ps(a, b);
            break;
        case 0x0d:
            r = _mm_min_ps(a, b);
            break;
        case 0x2e:
        case 0x2f:
            cond[0] = compare(shader_lane<0>(a), shader_lane<0>(b), (ins >> 24) & 7);
            cond[1] = compare(shader_lane<1>(a), shader_lane<1>(b), (ins >> 21) & 7);
            return;
        default:
            if (op < 0x30) {
                static std::atomic_flag warned;
                if (!warned.test_and_set(std::memory_order_relaxed)) LOG("pica: unknown shader opcode %#x at %#x", op, pc);
                return;
            }
            r = _mm_add_ps(shader_multiply(a, b), operand(2, 22));
            break;
        }
        break;
    }
    }
    if (mask) shader_store(d.destination < 16 ? out[d.destination] : tmp[d.destination - 16], r, mask);
}

} // namespace
} // namespace pica
