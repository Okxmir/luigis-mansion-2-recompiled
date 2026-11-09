#include "pica_shader_spirv.h"

#include "lm2_gpu_vertex.inc"
#include "log.h"
#include "pica_shader_decode.h"
#include "pica_shader_flow.h"

#include <SDL3/SDL_gpu.h>
#include <windows.h>
#include <dxcapi.h>
#include <wrl/client.h>

#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <cstring>
#include <format>
#include <future>
#include <string>
#include <vector>

namespace pica {
namespace {

class SpirvSource {
public:
    SpirvSource(const ShaderSetup &shader, const VertexShaderLayout &layout) : shader(shader), layout(layout) {}

    std::string build(uint32_t entry) {
        if (layout.inputs > 16) return {};
        source = LM2_VERTEX_PREFIX;
        if (layout.stride) {
            source += "struct VertexInput {\n";
            for (uint32_t i = 0; i < layout.inputs; ++i) {
                const uint16_t format = layout.formats[i];
                const unsigned type = (format >> 8) & 3, count = format >> 10;
                const unsigned width = type == 3 ? count : count <= 2 ? 2 : 4;
                const char *scalar = type == 3 ? "float" : type == 1 ? "uint" : "int";
                source += std::format("[[vk::location({})]] {}{} a{} : TEXCOORD{};\n",
                                      i, scalar, width == 1 ? "" : std::to_string(width), i, i);
            }
            source += "};\nVertexResult main(VertexInput input) {\n";
        } else {
            source += "VertexResult main(uint vertex : SV_VertexID) {\n";
            source += "uint input = (VertexData.x >> 4) + vertex * VertexData.y;\n";
        }
        source += R"(
    precise float4 r[48];
    [unroll] for (uint i = 0; i < 48; ++i) r[i] = 0.0;
    bool2 cc = false;
    int2 address = 0;
)";
        for (uint32_t i = 0; i < layout.inputs; ++i) {
            uint32_t reg = (layout.input_map >> (i * 4)) & 15;
            if (layout.stride) raw_attribute(reg, i, layout.formats[i]);
            else source += std::format("r[{}] = asfloat(Stream[input + {}]);\n", reg, i);
        }
        auto emit = [&](uint32_t word, int32_t loop) { return arithmetic(word, loop); };
        auto branch = [&](uint32_t word, uint32_t first, uint32_t alternate, uint32_t end, int32_t loop) {
            source += std::format("if (condition({}u, cc)) {{\n", word);
            if (!range(first, alternate, loop)) return false;
            source += "} else {\n";
            if (!range(alternate, end, loop)) return false;
            source += "}\n";
            return true;
        };
        if (!specialize_vertex_program(shader, entry, emit, branch)) return {};

        std::string suffix = LM2_VERTEX_SUFFIX;
        for (unsigned i = 0; i < layout.semantics.size(); ++i) {
            const uint32_t reg = layout.semantics[i];
            const std::string token = std::format("semantic_value(r, {})", i);
            const std::string value = reg < 64 ? std::format("r[{}][{}]", 32 + (reg >> 2), reg & 3) : "0.0";
            for (size_t at = suffix.find(token); at != std::string::npos; at = suffix.find(token, at + value.size()))
                suffix.replace(at, token.size(), value);
        }
        source += suffix;
        return std::move(source);
    }

private:
    const ShaderSetup &shader;
    const VertexShaderLayout &layout;
    std::string source;
    static constexpr std::string_view lanes = "xyzw";

    void raw_attribute(uint32_t reg, unsigned attribute, uint16_t format) {
        const unsigned type = (format >> 8) & 3, count = format >> 10;
        const unsigned width = type == 3 ? count : count <= 2 ? 2 : 4;
        source += std::format("r[{}] = float4(0, 0, 0, 1);\n", reg);
        auto value = std::format("input.a{}", attribute);
        if (count != width) value += std::format(".{}", lanes.substr(0, count));
        if (type != 3) value = std::format("float{}({})", count == 1 ? "" : std::to_string(count), value);
        source += std::format("r[{}].{} = {};\n", reg, lanes.substr(0, count), value);
    }

    bool range(uint32_t first, uint32_t end, int32_t loop) {
        for (uint32_t pc = first; pc < end; ++pc) {
            uint32_t word = shader.code[pc & 4095];
            uint32_t op = word >> 26;
            if (op == 0x21) continue;
            if (op >= 0x20 && op < 0x2e) return false;
            if (!arithmetic(word, loop)) return false;
        }
        return true;
    }

    void operand(char name, unsigned reg, unsigned relative, uint32_t selector, int32_t loop) {
        std::string value;
        if (reg < 32) {
            value = std::format("r[{}]", reg);
        } else if (relative == 1 || relative == 2) {
            value = std::format("load_source(r, {}, address[{}])", reg, relative - 1);
        } else {
            const int32_t index = int32_t(reg) - 32 + (relative == 3 ? loop : 0);
            value = index >= 0 && index < 96 ? std::format("asfloat(Stream[(ProgramData.z >> 4) + {}])", index) : "1.0.xxxx";
        }
        const unsigned order = (selector >> 1) & 255;
        source += std::format("float4 {} = {}({}).{}{}{}{};\n", name, selector & 1 ? "-" : "", value,
                              lanes[order >> 6], lanes[(order >> 4) & 3], lanes[(order >> 2) & 3], lanes[order & 3]);
    }

    bool arithmetic(uint32_t word, int32_t loop) {
        const auto ins = decode_arithmetic(word);
        const uint32_t op = word >> 26, desc = shader.swizzle[ins.descriptor], mask = desc & 15;
        const bool compare = op == 0x2e || op == 0x2f;
        if (!mask && !compare && op != 0x07) return true;
        source += "{\n";
        operand('a', ins.source[0], ins.address[0], desc >> 4, loop);
        if (op != 0x0b && op != 0x0e && op != 0x0f && op != 0x12 && op != 0x13)
            operand('b', ins.source[1], ins.address[1], desc >> 13, loop);
        if (op >= 0x30) operand('c', ins.source[2], ins.address[2], desc >> 22, loop);
        if (compare) {
            source += std::format("cc = bool2(compare_value(a.x, b.x, {}), compare_value(a.y, b.y, {}));\n",
                                  (word >> 24) & 7, (word >> 21) & 7);
        } else if (op == 0x12) {
            if (mask & 8) source += "address.x = int(a.x);\n";
            if (mask & 4) source += "address.y = int(a.y);\n";
        } else {
            std::string_view expression;
            switch (op) {
            case 0x00: expression = "a + b"; break;
            case 0x01:
            case 0x02:
            case 0x03:
            case 0x18:
                source += "precise float4 p = multiply(a, b);\n";
                expression = op == 0x01 ? "(p.x + p.y) + p.z" : op == 0x02 ? "((p.x + p.y) + p.z) + p.w"
                                                                          : "((p.x + p.y) + p.z) + b.w";
                break;
            case 0x08: expression = "multiply(a, b)"; break;
            case 0x09:
            case 0x1a: expression = "float4(a >= b)"; break;
            case 0x0a:
            case 0x1b: expression = "float4(a < b)"; break;
            case 0x0b: expression = "floor(a)"; break;
            case 0x0c: expression = "select(a > b, a, b)"; break;
            case 0x0d: expression = "select(a < b, a, b)"; break;
            case 0x0e: expression = "1.0 / a.x"; break;
            case 0x0f: expression = "1.0 / sqrt(a.x)"; break;
            case 0x13: expression = "a"; break;
            default:
                if (op < 0x30) return false;
                expression = "multiply(a, b) + c";
                break;
            }
            std::string written;
            for (unsigned lane = 0; lane < 4; ++lane)
                if (mask & (8 >> lane)) written += lanes[lane];
            const unsigned dst = ins.destination < 16 ? ins.destination + 32 : ins.destination;
            source += std::format("precise float4 result = {};\nr[{}].{} = result.{};\n", expression, dst, written, written);
        }
        source += "}\n";
        return true;
    }
};

DxcCreateInstanceProc compiler_entry() {
    static const auto create = []() -> DxcCreateInstanceProc {
        HMODULE dll = LoadLibraryExW(L"dxcompiler.dll", nullptr, LOAD_LIBRARY_SEARCH_APPLICATION_DIR);
        return dll ? reinterpret_cast<DxcCreateInstanceProc>(GetProcAddress(dll, "DxcCreateInstance")) : nullptr;
    }();
    return create;
}

std::vector<uint8_t> compile(const ShaderSetup &shader, uint32_t entry, const VertexShaderLayout &layout) {
    using Microsoft::WRL::ComPtr;
    const std::string source = SpirvSource(shader, layout).build(entry);
    if (source.empty()) return {};
    ComPtr<IDxcCompiler3> compiler;
    if (FAILED(compiler_entry()(CLSID_DxcCompiler, IID_PPV_ARGS(compiler.GetAddressOf())))) return {};
    const DxcBuffer buffer{source.data(), source.size(), DXC_CP_UTF8};
    const wchar_t *arguments[] = {L"-spirv", L"-fspv-target-env=vulkan1.0", L"-T", L"vs_6_0", L"-E", L"main",
                                  L"-HV", L"2021", L"-Ges", L"-O3"};
    ComPtr<IDxcResult> result;
    if (FAILED(compiler->Compile(&buffer, arguments, UINT32(std::size(arguments)), nullptr,
                                 IID_PPV_ARGS(result.GetAddressOf())))) return {};
    HRESULT status;
    if (FAILED(result->GetStatus(&status)) || FAILED(status)) return {};
    ComPtr<IDxcBlob> object;
    if (FAILED(result->GetOutput(DXC_OUT_OBJECT, IID_PPV_ARGS(object.GetAddressOf()), nullptr))) return {};
    const auto *start = static_cast<const uint8_t *>(object->GetBufferPointer());
    return {start, start + object->GetBufferSize()};
}

struct Key {
    uint64_t revision;
    uint32_t entry;
    uint16_t flags;
    std::array<uint8_t, 16> integers;
    VertexShaderLayout layout;
    bool operator==(const Key &) const = default;
};

struct Variant {
    Key key;
    SDL_GPUShader *shader = nullptr;
};

// The renderer owns the cache. Only DXC work runs on a background thread.
std::vector<Variant> variants;
std::future<std::vector<uint8_t>> pending;

} // namespace

uint8_t find_spirv_vertex_shader(SDL_GPUDevice *device, const ShaderSetup &shader, uint32_t entry,
                                 uint64_t revision, const VertexShaderLayout &layout) {
    if (!compiler_entry()) return 0;
    if (pending.valid() && pending.wait_for(std::chrono::seconds(0)) == std::future_status::ready) {
        try {
            const auto bytes = pending.get();
            if (!bytes.empty()) {
                SDL_GPUShaderCreateInfo info{};
                info.code = bytes.data();
                info.code_size = bytes.size();
                info.entrypoint = "main";
                info.format = SDL_GPU_SHADERFORMAT_SPIRV;
                info.stage = SDL_GPU_SHADERSTAGE_VERTEX;
                info.num_uniform_buffers = 1;
                info.num_storage_buffers = 1;
                variants.back().shader = SDL_CreateGPUShader(device, &info);
            }
        } catch (const std::exception &) {
            // A failed specialization leaves this variant on the CPU.
        }
        static const bool trace = std::getenv("LGM2_GPU_SHADER_LOG") != nullptr;
        if (trace) {
            const auto &v = variants.back();
            LOG("gpu: vertex program %#x flags %#x %s%s", v.key.entry, v.key.flags,
                v.shader ? "compiled for Vulkan" : "uses the CPU", v.key.layout.stride ? " (packed attributes)" : "");
        }
    }
    Key key{revision, entry, shader.b, {}, layout};
    std::memcpy(key.integers.data(), shader.i, sizeof(shader.i));
    auto it = std::find_if(variants.begin(), variants.end(), [&](const Variant &v) { return v.key == key; });
    if (it != variants.end()) return it->shader ? uint8_t(2 + (it - variants.begin())) : 0;
    if (pending.valid() || variants.size() >= 128) return 0;
    variants.push_back({key});
    try {
        pending = std::async(std::launch::async, [shader, entry, layout] { return compile(shader, entry, layout); });
    } catch (const std::exception &) {
        // The CPU renderer can still process this draw.
    }
    return 0;
}

SDL_GPUShader *get_spirv_vertex_shader(uint8_t index) {
    return variants[index - 2].shader;
}

const VertexShaderLayout &get_spirv_vertex_layout(uint8_t index) {
    return variants[index - 2].key.layout;
}

} // namespace pica
