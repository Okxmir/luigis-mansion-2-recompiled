#include "pica_shader_jit.h"

#include "pica_shader_decode.h"
#include "pica_shader_flow.h"

#include <array>
#include <cstring>
#include <intrin.h>
#include <memory>
#include <unordered_map>
#include <utility>

#define XBYAK_NO_OP_NAMES
#include <xbyak/xbyak.h>

namespace pica {
namespace {

// Uniform control flow is resolved once per draw state. Vertex-dependent control flow
// stays in the interpreter. Generated functions are leaf functions in the Win64 ABI.
class VertexEmitter final : public Xbyak::CodeGenerator {
public:
    VertexEmitter() : CodeGenerator(4096, Xbyak::AutoGrow) {}

    bool compile(const ShaderSetup &shader, uint32_t entry) {
        auto emit = [&](uint32_t word, int32_t loop) {
            loop_address = loop;
            const auto decoded = decode_arithmetic(word);
            return arithmetic(decoded, shader.swizzle[decoded.descriptor]);
        };
        auto branch = [&](uint32_t word, uint32_t start, uint32_t alternate, uint32_t end, int32_t loop) {
            loop_address = loop;
            return conditional(shader, word, start, alternate, end);
        };
        if (!specialize_vertex_program(shader, entry, emit, branch)) return false;
        ret();
        readyRE();
        return FlushInstructionCache(GetCurrentProcess(), getCode(), getSize()) != 0;
    }

private:
    static_assert(sizeof(Vec4) == 16);
    std::array<bool, 16> initialized{};
    std::array<bool, 2> moved_address{};
    int32_t loop_address = 0;
    bool compared = false;

    void splat_constant(const Xbyak::Xmm &dst, uint32_t bits) {
        mov(eax, bits);
        movd(dst, eax);
        shufps(dst, dst, 0);
    }

    void operand(const Xbyak::Xmm &dst, unsigned reg, unsigned relative, uint32_t selector) {
        if (reg < 16) {
            movups(dst, ptr[rdx + reg * sizeof(Vec4)]);
        } else if (reg < 32) {
            if (initialized[reg - 16]) movups(dst, ptr[r9 + (reg - 16) * sizeof(Vec4)]);
            else xorps(dst, dst);
        } else {
            const unsigned offset = reg - 32;
            if (relative == 1 || relative == 2) {
                if (moved_address[relative - 1]) {
                    Xbyak::Label out_of_range, loaded;
                    lea(eax, ptr[(relative == 1 ? r10 : r11) + offset]);
                    cmp(eax, 96);
                    jae(out_of_range);
                    shl(eax, 4);
                    movups(dst, ptr[rcx + rax]);
                    jmp(loaded);
                    L(out_of_range);
                    splat_constant(dst, 0x3f800000);
                    L(loaded);
                } else {
                    movups(dst, ptr[rcx + offset * sizeof(Vec4)]);
                }
            } else {
                const unsigned index = offset + (relative == 3 ? loop_address : 0);
                if (index < 96) movups(dst, ptr[rcx + index * sizeof(Vec4)]);
                else splat_constant(dst, 0x3f800000);
            }
        }
        const uint32_t order = (selector >> 1) & 255;
        if (order != 0x1b) {
            const uint32_t lanes = ((order & 3) << 6) | ((order & 12) << 2) |
                                   ((order & 48) >> 2) | ((order & 192) >> 6);
            shufps(dst, dst, lanes);
        }
        if (selector & 1) {
            pcmpeqd(xmm5, xmm5);
            pslld(xmm5, 31);
            xorps(dst, xmm5);
        }
    }

    void multiply() {
        // Match the interpreter's 0 * infinity rule without discarding NaN inputs.
        movaps(xmm2, xmm0);
        cmpordps(xmm2, xmm1);
        mulps(xmm0, xmm1);
        movaps(xmm3, xmm0);
        cmpunordps(xmm3, xmm0);
        andps(xmm2, xmm3);
        andnps(xmm2, xmm0);
        movaps(xmm0, xmm2);
    }

    void dot(unsigned op) {
        multiply();
        movaps(xmm2, xmm0);
        shufps(xmm2, xmm2, 0x55);
        addss(xmm2, xmm0);
        movaps(xmm3, xmm0);
        shufps(xmm3, xmm3, 0xaa);
        addss(xmm2, xmm3);
        if (op != 0x01) {
            const auto &w = op == 0x02 ? xmm0 : xmm1;
            shufps(w, w, 0xff);
            addss(xmm2, w);
        }
        shufps(xmm2, xmm2, 0);
        movaps(xmm0, xmm2);
    }

    void compare_lane(const Xbyak::Xmm &result, const Xbyak::Xmm &left, const Xbyak::Xmm &right, unsigned mode) {
        if (mode >= 6) {
            pcmpeqd(result, result);
        } else if (mode >= 4) {
            movaps(result, right);
            cmpss(result, left, mode - 3);
        } else {
            static constexpr unsigned predicates[] = {0, 4, 1, 2};
            movaps(result, left);
            cmpss(result, right, predicates[mode]);
        }
    }

    bool conditional(const ShaderSetup &shader, uint32_t word, uint32_t start, uint32_t alternate, uint32_t end) {
        // Both paths may write temporaries and address registers. Give untouched registers
        // their interpreter defaults before the split so either path can reach the join.
        xorps(xmm5, xmm5);
        for (unsigned i = 0; i < initialized.size(); ++i) {
            if (!initialized[i]) movups(ptr[r9 + i * sizeof(Vec4)], xmm5);
        }
        initialized.fill(true);
        if (!moved_address[0]) xor_(r10d, r10d);
        if (!moved_address[1]) xor_(r11d, r11d);
        moved_address.fill(true);
        if (!compared) xorps(xmm4, xmm4);
        compared = true;

        Xbyak::Label otherwise, done;
        movmskps(eax, xmm4);
        const uint32_t reference = ((word >> 25) & 1) | (((word >> 24) & 1) << 1);
        if (reference) xor_(eax, reference);
        switch ((word >> 22) & 3) {
        case 0:
            and_(eax, 3);
            cmp(eax, 3);
            je(otherwise, T_NEAR);
            break;
        case 1: test(eax, 3); jnz(otherwise, T_NEAR); break;
        case 2: test(eax, 1); jnz(otherwise, T_NEAR); break;
        case 3: test(eax, 2); jnz(otherwise, T_NEAR); break;
        }
        auto emit_range = [&](uint32_t begin, uint32_t limit) {
            for (uint32_t pc = begin; pc < limit; ++pc) {
                const auto ins = decode_arithmetic(shader.code[pc & 4095]);
                const uint32_t op = ins.word >> 26;
                if (op == 0x21) continue;
                if (op >= 0x20 && op < 0x2e) return false;
                if (!arithmetic(ins, shader.swizzle[ins.descriptor])) return false;
            }
            return true;
        };
        if (!emit_range(start, alternate)) return false;
        if (alternate != end) jmp(done, T_NEAR);
        L(otherwise);
        if (!emit_range(alternate, end)) return false;
        L(done);
        return true;
    }

    bool arithmetic(const ArithmeticInstruction &ins, uint32_t desc) {
        const uint32_t op = ins.word >> 26;
        const uint32_t mask = desc & 15;
        if (op == 0x2e || op == 0x2f) {
            operand(xmm0, ins.source[0], ins.address[0], desc >> 4);
            operand(xmm1, ins.source[1], ins.address[1], desc >> 13);
            compare_lane(xmm2, xmm0, xmm1, (ins.word >> 24) & 7);
            shufps(xmm0, xmm0, 0x55);
            shufps(xmm1, xmm1, 0x55);
            compare_lane(xmm3, xmm0, xmm1, (ins.word >> 21) & 7);
            unpcklps(xmm2, xmm3);
            movaps(xmm4, xmm2);
            compared = true;
            return true;
        }
        if (op == 0x07) return false; // LITP also updates the condition flags.
        if (!mask) return true;
        operand(xmm0, ins.source[0], ins.address[0], desc >> 4);
        switch (op) {
        case 0x0b: // FLR
            roundps(xmm0, xmm0, 1 | 8);
            break;
        case 0x0e: // RCP
        case 0x0f: // RSQ
            if (op == 0x0f) sqrtss(xmm0, xmm0);
            splat_constant(xmm1, 0x3f800000);
            divss(xmm1, xmm0);
            shufps(xmm1, xmm1, 0);
            movaps(xmm0, xmm1);
            break;
        case 0x12: // MOVA
            if (mask & 8) {
                cvttss2si(r10d, xmm0);
                moved_address[0] = true;
            }
            if (mask & 4) {
                shufps(xmm0, xmm0, 0x55);
                cvttss2si(r11d, xmm0);
                moved_address[1] = true;
            }
            return true;
        case 0x13: // MOV
            break;
        default:
            operand(xmm1, ins.source[1], ins.address[1], desc >> 13);
            switch (op) {
            case 0x00: addps(xmm0, xmm1); break;
            case 0x01:
            case 0x02:
            case 0x03:
            case 0x18: dot(op); break;
            case 0x08: multiply(); break;
            case 0x09:
            case 0x1a: // SGE
                cmpleps(xmm1, xmm0);
                splat_constant(xmm0, 0x3f800000);
                andps(xmm0, xmm1);
                break;
            case 0x0a:
            case 0x1b: // SLT
                cmpltps(xmm0, xmm1);
                splat_constant(xmm1, 0x3f800000);
                andps(xmm0, xmm1);
                break;
            case 0x0c: maxps(xmm0, xmm1); break;
            case 0x0d: minps(xmm0, xmm1); break;
            default:
                if (op < 0x30) return false;
                multiply();
                operand(xmm1, ins.source[2], ins.address[2], desc >> 22);
                addps(xmm0, xmm1);
                break;
            }
            break;
        }

        const bool output = ins.destination < 16;
        const unsigned index = ins.destination & 15;
        const auto destination = ptr[(output ? r8 : r9) + index * sizeof(Vec4)];
        if (mask != 15) {
            if (output || initialized[index]) movups(xmm1, destination);
            else xorps(xmm1, xmm1);
            const uint32_t lanes = ((mask & 1) << 3) | ((mask & 2) << 1) |
                                   ((mask & 4) >> 1) | ((mask & 8) >> 3);
            blendps(xmm1, xmm0, lanes);
            movups(destination, xmm1);
        } else {
            movups(destination, xmm0);
        }
        if (!output) initialized[index] = true;
        return true;
    }
};

struct ShaderKey {
    uint32_t entry, booleans;
    std::array<uint32_t, 4> integers;
    bool operator==(const ShaderKey &) const = default;
};

struct ShaderKeyHash {
    size_t operator()(const ShaderKey &key) const {
        size_t hash = (size_t(key.entry) << 16) | key.booleans;
        for (auto integer : key.integers) hash = (hash ^ integer) * 0x9e3779b185ebca87ull;
        return hash;
    }
};

} // namespace

CompiledVertex find_compiled_shader(const ShaderSetup &shader, uint32_t entry, uint64_t revision) {
    static const bool available = [] {
        int cpu[4];
        __cpuid(cpu, 1);
        return (cpu[2] & (1 << 19)) != 0; // SSE4.1
    }();
    if (!available) return nullptr;

    static thread_local uint64_t last_revision = 0;
    static thread_local std::unordered_map<ShaderKey, std::unique_ptr<VertexEmitter>, ShaderKeyHash> cache;
    if (revision != last_revision) {
        cache.clear();
        last_revision = revision;
    }
    ShaderKey key{entry, shader.b, {}};
    std::memcpy(key.integers.data(), shader.i, sizeof(shader.i));
    if (auto it = cache.find(key); it != cache.end()) {
        return it->second ? it->second->getCode<CompiledVertex>() : nullptr;
    }
    if (cache.size() >= 128) cache.clear();
    auto &compiled = cache[key];
    try {
        auto code = std::make_unique<VertexEmitter>();
        if (code->compile(shader, entry)) compiled = std::move(code);
    } catch (const Xbyak::Error &) {
        // The interpreter also works when Windows disallows executable allocations.
    }
    return compiled ? compiled->getCode<CompiledVertex>() : nullptr;
}

} // namespace pica
