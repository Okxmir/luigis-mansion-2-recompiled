#pragma once

#include <cstdint>

namespace pica {

struct Vec4;
struct ShaderSetup;
using CompiledVertex = void (*)(const Vec4 *, const Vec4 *, Vec4 *, Vec4 *);

// Request on the draw thread before dispatching the vertices to workers.
CompiledVertex find_compiled_shader(const ShaderSetup &shader, uint32_t entry, uint64_t revision);

} // namespace pica
