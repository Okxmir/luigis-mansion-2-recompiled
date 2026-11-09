#pragma once

#include <array>
#include <cstdint>

struct SDL_GPUDevice;
struct SDL_GPUShader;

namespace pica {

struct ShaderSetup;

struct VertexShaderLayout {
    uint32_t inputs;
    uint64_t input_map;
    std::array<uint32_t, 24> semantics;
    uint32_t stride = 0;
    std::array<uint16_t, 16> formats{};
    bool operator==(const VertexShaderLayout &) const = default;
};

// A pending or unsupported specialization returns 0 so the draw can use the CPU.
uint8_t find_spirv_vertex_shader(SDL_GPUDevice *device, const ShaderSetup &shader, uint32_t entry,
                                 uint64_t revision, const VertexShaderLayout &layout);
SDL_GPUShader *get_spirv_vertex_shader(uint8_t index);
const VertexShaderLayout &get_spirv_vertex_layout(uint8_t index);

} // namespace pica
