"""Apply the LM2 frontend changes to the pinned Clockwork runtime."""

import argparse
import shutil
from pathlib import Path


def change(path, replacements):
    source = path.read_text(encoding="utf-8")
    for old, new in replacements:
        if source.count(old) != 1:
            raise ValueError(f"{path}: expected one match for {old[:80]!r}")
        source = source.replace(old, new)
    path.write_text(source, encoding="utf-8")


def span(path, start, end):
    source = path.read_text(encoding="utf-8")
    first = source.index(start)
    return source[first:source.index(end, first)]


def prepare(upstream, output):
    for directory in ("src", "include"):
        shutil.copytree(upstream / "runtime" / directory, output / directory, dirs_exist_ok=True)
    src = output / "src"
    frontend = src / "frontend"
    sdl = frontend / "sdl.cpp"
    change(sdl, [
        ('#include "handoff.h"\n', ""),
        ('#include "launcher.h"\n', ""),
        (span(sdl, "bool hand_off_or_explain", "void run(void (*start)"), ""),
        ("const char *cli_dump, bool force_launcher, bool play", "const char *cli_dump"),
        ("        if (std::string problem; !hand_off_or_explain(cli_dump, &problem)) fatal(\"%s\", problem.c_str());\n", ""),
        ('SDL_SetAppMetadata("Clockwork", nullptr, "io.github.yw2recomp")',
         'SDL_SetAppMetadata("Luigi\'s Mansion 2", nullptr, "local.lgm2.native")'),
        ('"Clockwork - Yo-kai Watch 2"', '"Luigi\'s Mansion 2"'),
        ('"Clockwork: Yo-kai Watch 2 stopped"', '"Luigi\'s Mansion 2"'),
        ("    fatal_hook = show_fatal;", '    if (!std::getenv("LGM2_NO_DIALOG")) fatal_hook = show_fatal;'),
        ("        if (s.gpu_renderer) {", '        if (s.gpu_renderer && !std::getenv("LGM2_CPU_PICA")) {'),
        ("""        if (!renderer && !(renderer = SDL_CreateRenderer(window, nullptr)))
            fatal("cannot create a renderer: %s", SDL_GetError());""",
         """        if (!renderer) renderer = SDL_CreateRenderer(window, "direct3d11");
        if (!renderer) renderer = SDL_CreateRenderer(window, nullptr);
        if (!renderer) fatal("cannot create a renderer: %s", SDL_GetError());"""),
        (span(sdl, "    // the launcher, unless", "    if (device && !pica::gpu::init"),
         '    game_path = s.game_path;\n    const std::string game_id = "lm2";\n'),
        (span(sdl, '        LOG("no window', "    s.load();"), '        fatal("SDL initialization failed: %s", SDL_GetError());\n    }\n'),
    ])
    header = frontend / "frontend.h"
    change(header, [
        (span(header, "// Shows the launcher", "\n} // namespace frontend"),
         '// The main thread draws both screens while the native game code runs on its own thread.\n'
         '[[noreturn]] void run(void (*start)(const char *dump), const char *cli_dump);\n')
    ])
    games = frontend / "games.h"
    change(games, [
        (span(games, "inline constexpr GameInfo GAMES[]", "inline constexpr int GAME_COUNT"),
         'inline constexpr GameInfo GAMES[] = {{"lm2", "Luigi\'s Mansion 2", ""}};\n'),
        (span(games, "inline constexpr KnownDump KNOWN_DUMPS[]", "};") + "};",
         'inline constexpr KnownDump KNOWN_DUMPS[] = {\n'
         '    {0x0004000000076500, "lm2", "", "LuigisMansion2", Region::EUR},\n};'),
    ])
    platform = src / "platform.cpp"
    change(platform, [
        ('#include "log.h"\n', '#include "log.h"\n#include <SDL3/SDL.h>\n'),
        (span(platform, "        std::filesystem::path base;", "        std::filesystem::create_directories(d);"),
         '''        const char *override_path = std::getenv("LGM2_DATA_DIR");
        const char *base = SDL_GetBasePath();
        if (!base && (!override_path || !*override_path)) fatal("could not find the executable directory");
        auto d = override_path && *override_path ? std::filesystem::path(override_path)
                                                 : std::filesystem::path(base) / "userdata";
'''),
        ('"YW2_STATE_DIR"', '"LGM2_SAVE_DIR"'),
    ])
    settings = frontend / "settings.h"
    change(settings, [
        ("    int hud_size = 80;", "    int hud_size = 100;"),
        ("    int camera_zoom = 90;", "    int camera_zoom = 100;"),
        ("    int language = 1;", "    int language = 2;"),
    ])
    # SDL scancodes are physical positions. WASD scancodes are ZQSD on AZERTY.
    controls = frontend / "settings.cpp"
    change(controls, [
        ("SDL_SCANCODE_U,    SDL_SCANCODE_Q,", "SDL_SCANCODE_U,    SDL_SCANCODE_LSHIFT,"),
    ])
    svc = src / "kernel" / "svc.cpp"
    change(svc, [
        ("#include <cstring>\n", "#include <cstring>\n#include <cstdlib>\n"),
        ("    uint32_t r = kernel::dispatch(lk, ctx, imm, addr);", """    static bool first_sleep = true;
    if (first_sleep && imm == 0x0a && std::getenv("LGM2_TRACE_FIRST_SLEEP")) {
        first_sleep = false;
        LOG("first sleep: r0=%08x r1=%08x lr=%08x", ctx->r[0], ctx->r[1], ctx->r[14]);
        print_trace();
    }
    uint32_t r = kernel::dispatch(lk, ctx, imm, addr);"""),
    ])
    kernel = src / "kernel" / "kernel.cpp"
    change(kernel, [
        ("    // WIFI_MACADDR:", """    // LM2 polls the PTM readiness byte before querying RUNNING_HW.
    // Windows has already supplied our retail hardware identity above.
    *mem::ptr(mem::SHARED_PAGE + 0x86) = 1;
    // WIFI_MACADDR:"""),
    ])
    apt = src / "hle" / "apt.cpp"
    change(apt, [
        ("namespace hle {\nnamespace {", "namespace hle {\nvoid reply_lm2_shared_font(Request &req);\nnamespace {"),
        ("        case 0x004B:", """        case 0x0044: // GetSharedFont
            reply_lm2_shared_font(req);
            break;
        case 0x004B:"""),
    ])
    gpu = src / "video" / "gpu" / "gpu.cpp"
    gpu_header = src / "video" / "gpu" / "gpu.h"
    change(gpu_header, [
        ("void end_draw();", """struct NativeVertices {
    uint32_t *attributes;
    uint32_t *indices;
    bool raw;
};
struct RawVertexInput {
    const uint8_t *data = nullptr;
    uint32_t bytes = 0, stride = 0;
    uint16_t formats[16]{}; // byte offset, element type, component count
};
NativeVertices begin_native_vertices(uint32_t vertex_count, uint32_t index_count, uint32_t attribute_count,
                                    const uint32_t semantic_map[24], uint64_t revision, const RawVertexInput &raw);
uint32_t *begin_indexed_vertices(const Vertex *shaded, uint32_t vertex_count, uint32_t index_count);
void end_draw();"""),
    ])
    change(gpu, [
        ('#include "gpu.h"\n', '#include "gpu.h"\n#include "pica_shader_spirv.h"\n'),
        ('#include "shaders.inc"', """#include "shaders.inc"
#ifdef LGM2_GPU_VERTEX_SHADER
#include "lm2_gpu_vertex.inc"
#endif"""),
        ("SDL_GPUTextureFormat depth_format;",
         "SDL_GPUShader *vs_native;\nbool quantized_lcd;\nSDL_GPUTextureFormat depth_format;"),
        ("SDL_GPUTextureFormat depth_format;",
         """SDL_GPUTextureFormat depth_format;
bool supports_depth16;

SDL_GPUTextureFormat surface_depth_format(uint32_t guest_format) {
    return guest_format == 0 && supports_depth16 ? SDL_GPU_TEXTUREFORMAT_D16_UNORM : depth_format;
}"""),
        ("    s->tex = depth ? make_texture(s->tw, s->th, depth_format, SDL_GPU_TEXTUREUSAGE_DEPTH_STENCIL_TARGET)",
         "    s->tex = depth ? make_texture(s->tw, s->th, surface_depth_format(format), SDL_GPU_TEXTUREUSAGE_DEPTH_STENCIL_TARGET)"),
        ("stencil_zfail, stencil_zpass, stencil_read, stencil_write, has_depth, wdepth, pad[2];",
         """stencil_zfail, stencil_zpass, stencil_read, stencil_write, has_depth, wdepth, depth_format, cull;
    uint8_t native, pad[3];"""),
        ("    info.vertex_shader = vs_pica, info.fragment_shader =",
         """    info.vertex_shader = k.native ? vs_native : vs_pica;
#ifdef LGM2_GPU_SPECIALIZED
    if (k.native > 1) info.vertex_shader = get_spirv_vertex_shader(k.native);
#endif
    info.fragment_shader ="""),
        ('    if (!p) fatal("GPU pipeline: %s", SDL_GetError());',
         """    if (!p && k.native > 1) {
        LOG("gpu: specialized vertex pipeline unavailable: %s", SDL_GetError());
        pipelines[key] = nullptr;
        return nullptr;
    }
    if (!p) fatal("GPU pipeline: %s", SDL_GetError());"""),
        ("    SDL_GPUVertexAttribute attrs[6];", "    SDL_GPUVertexAttribute attrs[16];"),
        ("""    info.vertex_input_state.vertex_buffer_descriptions = &vb;
    info.vertex_input_state.num_vertex_buffers = 1;
    info.vertex_input_state.vertex_attributes = attrs;
    info.vertex_input_state.num_vertex_attributes = 6;""",
         """    if (!k.native) {
        info.vertex_input_state.vertex_buffer_descriptions = &vb;
        info.vertex_input_state.num_vertex_buffers = 1;
        info.vertex_input_state.vertex_attributes = attrs;
        info.vertex_input_state.num_vertex_attributes = 6;
    }
#ifdef LGM2_GPU_SPECIALIZED
    if (k.native > 1) {
        const auto &layout = get_spirv_vertex_layout(k.native);
        if (layout.stride) {
            static constexpr SDL_GPUVertexElementFormat floats[] = {
                SDL_GPU_VERTEXELEMENTFORMAT_FLOAT, SDL_GPU_VERTEXELEMENTFORMAT_FLOAT2,
                SDL_GPU_VERTEXELEMENTFORMAT_FLOAT3, SDL_GPU_VERTEXELEMENTFORMAT_FLOAT4
            };
            static constexpr SDL_GPUVertexElementFormat integers[][2] = {
                {SDL_GPU_VERTEXELEMENTFORMAT_BYTE2, SDL_GPU_VERTEXELEMENTFORMAT_BYTE4},
                {SDL_GPU_VERTEXELEMENTFORMAT_UBYTE2, SDL_GPU_VERTEXELEMENTFORMAT_UBYTE4},
                {SDL_GPU_VERTEXELEMENTFORMAT_SHORT2, SDL_GPU_VERTEXELEMENTFORMAT_SHORT4}
            };
            vb.pitch = layout.stride;
            for (uint32_t i = 0; i < layout.inputs; ++i) {
                const uint32_t value = layout.formats[i], type = (value >> 8) & 3, count = value >> 10;
                const auto format = type == 3 ? floats[count - 1] : integers[type][count > 2];
                attrs[i] = {i, 0, format, value & 255};
            }
            info.vertex_input_state.vertex_buffer_descriptions = &vb;
            info.vertex_input_state.num_vertex_buffers = 1;
            info.vertex_input_state.vertex_attributes = attrs;
            info.vertex_input_state.num_vertex_attributes = layout.inputs;
        }
    }
#endif"""),
        ("    info.rasterizer_state.cull_mode = SDL_GPU_CULLMODE_NONE; // culled per triangle on the CPU",
         """    info.rasterizer_state.cull_mode = k.cull ? SDL_GPU_CULLMODE_BACK : SDL_GPU_CULLMODE_NONE;
    info.rasterizer_state.front_face = k.cull == 1 ? SDL_GPU_FRONTFACE_CLOCKWISE
                                                  : SDL_GPU_FRONTFACE_COUNTER_CLOCKWISE;"""),
        ("struct DrawRec {", """struct NativeUniforms {
    float depth[4], viewport[4];
    uint32_t attributes[4], program[4], uniforms[4];
};
static_assert(sizeof(NativeUniforms) == 80);

struct DrawRec {
    PipelineKey key;
    bool native, indexed, raw;
    uint32_t first_index;
    NativeUniforms native_uniforms;"""),
        ("std::vector<DrawRec> batch;", """std::vector<DrawRec> batch;
std::vector<uint32_t> native_data, batch_indices;
uint32_t native_code, native_swizzle;
bool native_program_cached = false;

uint32_t append_native(const void *source, size_t words) {
    const size_t begin = native_data.size();
    native_data.resize(begin + words);
    if (source) std::memcpy(native_data.data() + begin, source, words * sizeof(uint32_t));
    return uint32_t(begin * sizeof(uint32_t));
}

void upload_indexed(SDL_GPUCommandBuffer *cmd, SDL_GPUBuffer **data, SDL_GPUBuffer **indices) {
    if (batch_indices.empty()) return;
    const uint32_t data_bytes = uint32_t(native_data.size() * sizeof(uint32_t));
    const uint32_t index_bytes = uint32_t(batch_indices.size() * sizeof(uint32_t));
    SDL_GPUTransferBufferCreateInfo transfer_info{SDL_GPU_TRANSFERBUFFERUSAGE_UPLOAD, data_bytes + index_bytes, 0};
    SDL_GPUTransferBuffer *transfer = SDL_CreateGPUTransferBuffer(dev, &transfer_info);
    SDL_GPUBufferCreateInfo data_info{SDL_GPU_BUFFERUSAGE_GRAPHICS_STORAGE_READ | SDL_GPU_BUFFERUSAGE_VERTEX, data_bytes, 0};
    SDL_GPUBufferCreateInfo index_info{SDL_GPU_BUFFERUSAGE_INDEX, index_bytes, 0};
    if (data_bytes) *data = SDL_CreateGPUBuffer(dev, &data_info);
    *indices = SDL_CreateGPUBuffer(dev, &index_info);
    if (!transfer || (data_bytes && !*data) || !*indices) fatal("GPU vertex buffers: %s", SDL_GetError());
    auto *mapped = static_cast<uint8_t *>(SDL_MapGPUTransferBuffer(dev, transfer, false));
    if (!mapped) fatal("GPU vertex upload mapping: %s", SDL_GetError());
    if (data_bytes) std::memcpy(mapped, native_data.data(), data_bytes);
    std::memcpy(mapped + data_bytes, batch_indices.data(), index_bytes);
    SDL_UnmapGPUTransferBuffer(dev, transfer);
    SDL_GPUCopyPass *copy = SDL_BeginGPUCopyPass(cmd);
    SDL_GPUTransferBufferLocation data_source{transfer, 0}, index_source{transfer, data_bytes};
    SDL_GPUBufferRegion data_dest{*data, 0, data_bytes}, index_dest{*indices, 0, index_bytes};
    if (data_bytes) SDL_UploadToGPUBuffer(copy, &data_source, &data_dest, false);
    SDL_UploadToGPUBuffer(copy, &index_source, &index_dest, false);
    SDL_EndGPUCopyPass(copy);
    SDL_ReleaseGPUTransferBuffer(dev, transfer);
}"""),
        ("                           uint32_t uniforms) {", "                           uint32_t uniforms, uint32_t storage = 0) {"),
        ("    info.num_uniform_buffers = uniforms;", "    info.num_uniform_buffers = uniforms;\n    info.num_storage_buffers = storage;"),
        ("    vs_pica = make_shader(SPIRV_pica_vert, sizeof SPIRV_pica_vert, SDL_GPU_SHADERSTAGE_VERTEX, 0, 1);",
         """    vs_pica = make_shader(SPIRV_pica_vert, sizeof SPIRV_pica_vert, SDL_GPU_SHADERSTAGE_VERTEX, 0, 1);
#ifdef LGM2_GPU_VERTEX_SHADER
    if (std::getenv("LGM2_GPU_VERTICES")) {
        vs_native = make_shader(LM2_GPU_VERTEX, sizeof LM2_GPU_VERTEX, SDL_GPU_SHADERSTAGE_VERTEX, 0, 1, 1);
        if (vs_native) LOG("gpu: PICA vertex programs run on Vulkan for large triangle lists");
    }
#endif"""),
        ("    fs_blit = make_shader(SPIRV_blit_lcd_frag, sizeof SPIRV_blit_lcd_frag, SDL_GPU_SHADERSTAGE_FRAGMENT, 1, 1);",
         """#ifdef LGM2_GPU_VERTEX_SHADER
    if (!std::getenv("LGM2_GPU_LCD_READBACK")) {
        fs_blit = make_shader(LM2_GPU_LCD, sizeof LM2_GPU_LCD, SDL_GPU_SHADERSTAGE_FRAGMENT, 1, 1);
        quantized_lcd = fs_blit != nullptr;
    }
#endif
    if (!fs_blit)
        fs_blit = make_shader(SPIRV_blit_lcd_frag, sizeof SPIRV_blit_lcd_frag, SDL_GPU_SHADERSTAGE_FRAGMENT, 1, 1);"""),
        ("    d.pipeline = pipeline(k);", "    d.key = k;"),
        ("void end_draw() {\n    if (cur_skip) return;",
         """NativeVertices begin_native_vertices(uint32_t vertex_count, uint32_t index_count, uint32_t attribute_count,
                                    const uint32_t semantic_map[24], uint64_t revision, const RawVertexInput &raw) {
    static const bool cpu_only = std::getenv("LGM2_CPU_VERTEX") || std::getenv("LGM2_INTERPRET_VERTEX");
    if (cpu_only || cur_skip || interp_on || interp_wanted || cur_ky != 1.0f || hud_scale() < 1.0f) return {};
    uint8_t native = vs_native ? 1 : 0;
    bool use_raw = false;
#ifdef LGM2_GPU_SPECIALIZED
    if (!native && vertex_count >= 256) {
        const uint64_t inputs = regs[VS_INPUT_MAP_LO] | (uint64_t(regs[VS_INPUT_MAP_HI]) << 32);
        VertexShaderLayout layout{attribute_count, inputs, {}};
        std::copy_n(semantic_map, layout.semantics.size(), layout.semantics.begin());
        layout.stride = raw.stride;
        std::copy_n(raw.formats, layout.formats.size(), layout.formats.begin());
        native = find_spirv_vertex_shader(dev, vs, regs[VS_ENTRY] & 0xffff, revision, layout);
        use_raw = native && layout.stride;
        if (!native && layout.stride) {
            layout.stride = 0;
            layout.formats = {};
            native = find_spirv_vertex_shader(dev, vs, regs[VS_ENTRY] & 0xffff, revision, layout);
        }
    }
#endif
    if (!native) return {};
    PipelineKey key = cur.key;
    key.native = native;
    key.cull = cur_cull <= 2 ? uint8_t(cur_cull) : 0;
    SDL_GPUGraphicsPipeline *native_pipeline = pipeline(key);
    if (!native_pipeline) return {};
    NativeUniforms &u = cur.native_uniforms;
    std::memcpy(u.depth, cur.depth_map, sizeof(u.depth));
    u.viewport[0] = cur_refit ? refit_ax : 1.0f;
    u.viewport[1] = cur_refit ? refit_bx : 0.0f;
    u.viewport[2] = cur_refit ? refit_ay : 1.0f;
    u.viewport[3] = cur_refit ? refit_by : 0.0f;
    if (native == 1 && (!native_program_cached ||
        std::memcmp(native_data.data() + native_code / 4, vs.code, sizeof(vs.code)) ||
        std::memcmp(native_data.data() + native_swizzle / 4, vs.swizzle, sizeof(vs.swizzle)))) {
        native_code = append_native(vs.code, std::size(vs.code));
        native_swizzle = append_native(vs.swizzle, std::size(vs.swizzle));
        native_program_cached = true;
    }
    u.program[0] = native_code;
    u.program[1] = native_swizzle;
    u.program[2] = append_native(vs.f, sizeof(vs.f) / 4);
    u.program[3] = regs[VS_ENTRY] & 0xffff;
    u.uniforms[0] = native == 1 ? append_native(vs.i, sizeof(vs.i) / 4) : 0;
    u.uniforms[1] = vs.b;
    u.uniforms[2] = native == 1 ? append_native(semantic_map, 24) : 0;
    if (use_raw) {
        u.attributes[0] = append_native(nullptr, (size_t(raw.bytes) + 15) / 16 * 4);
        std::memcpy(native_data.data() + u.attributes[0] / 4, raw.data, raw.bytes);
    } else {
        u.attributes[0] = append_native(nullptr, size_t(vertex_count) * attribute_count * 4);
    }
    u.attributes[1] = attribute_count;
    u.attributes[2] = regs[VS_INPUT_MAP_LO];
    u.attributes[3] = regs[VS_INPUT_MAP_HI];
    cur.native = true;
    cur.indexed = true;
    cur.raw = use_raw;
    cur.key = key;
    cur.pipeline = native_pipeline;
    cur.first_index = uint32_t(batch_indices.size());
    cur.count = index_count;
    batch_indices.resize(batch_indices.size() + index_count);
    return {native_data.data() + u.attributes[0] / 4, batch_indices.data() + cur.first_index, use_raw};
}

uint32_t *begin_indexed_vertices(const Vertex *shaded, uint32_t vertex_count, uint32_t index_count) {
    static const bool expanded = std::getenv("LGM2_EXPANDED_VERTICES") != nullptr;
    if (expanded || cur_skip || interp_on || interp_wanted || cur_ky != 1.0f || hud_scale() < 1.0f) return nullptr;
    // Store each transformed vertex once. Vulkan assembles and culls the triangle list.
    cur.indexed = true;
    cur.key.cull = cur_cull <= 2 ? uint8_t(cur_cull) : 0;
    cur.pipeline = pipeline(cur.key);
    cur.first = uint32_t(vertices.size());
    cur.first_index = uint32_t(batch_indices.size());
    cur.count = index_count;
    vertices.resize(vertices.size() + vertex_count);
    for (uint32_t i = 0; i < vertex_count; ++i) {
        const float *a = shaded[i].a;
        GpuVertex &g = vertices[cur.first + i];
        std::memcpy(g.pos, a + POS, sizeof(g.pos));
        if (cur_refit) {
            g.pos[0] = refit_ax * g.pos[0] + refit_bx * g.pos[3];
            g.pos[1] = refit_ay * g.pos[1] + refit_by * g.pos[3];
        }
        std::memcpy(g.color, a + COLOR, sizeof(g.color));
        std::memcpy(g.quat, a + QUAT, sizeof(g.quat));
        g.tc01[0] = a[TEX0], g.tc01[1] = a[TEX0 + 1], g.tc01[2] = a[TEX1], g.tc01[3] = a[TEX1 + 1];
        g.tc2w[0] = a[TEX2], g.tc2w[1] = a[TEX2 + 1], g.tc2w[2] = a[TEX0_W], g.tc2w[3] = 0;
        g.view[0] = a[VIEW], g.view[1] = a[VIEW + 1], g.view[2] = a[VIEW + 2], g.view[3] = 0;
    }
    batch_indices.resize(batch_indices.size() + index_count);
    return batch_indices.data() + cur.first_index;
}

void end_draw() {
    if (cur_skip) return;
    if (cur.indexed) {
        batch.push_back(cur);
        return;
    }"""),
        ("        cur.tris = cur_tris, cur.match = match_key(cur);\n        batch.push_back(cur);",
         "        cur.pipeline = pipeline(cur.key);\n        cur.tris = cur_tris, cur.match = match_key(cur);\n        batch.push_back(cur);"),
        ("    if (!vbuf) batch.clear(); // out of GPU memory: this batch is lost",
         """    SDL_GPUBuffer *native_buffer = nullptr, *index_buffer = nullptr;
    upload_indexed(cmd, &native_buffer, &index_buffer);"""),
        ("    for (const DrawRec &d : batch) {\n        begin_render_pass",
         "    for (const DrawRec &d : batch) {\n        if (!d.native && !vbuf) continue;\n        begin_render_pass"),
        ("        SDL_GPUBufferBinding vb{vbuf, 0};\n        SDL_BindGPUVertexBuffers(pass, 0, &vb, 1);",
         """        if (d.indexed) {
            SDL_GPUBufferBinding ib{index_buffer, 0};
            SDL_BindGPUIndexBuffer(pass, &ib, SDL_GPU_INDEXELEMENTSIZE_32BIT);
        }
        if (d.native) {
            SDL_BindGPUVertexStorageBuffers(pass, 0, &native_buffer, 1);
            if (d.raw) {
                SDL_GPUBufferBinding vb{native_buffer, d.native_uniforms.attributes[0]};
                SDL_BindGPUVertexBuffers(pass, 0, &vb, 1);
            }
        } else {
            SDL_GPUBufferBinding vb{vbuf, 0};
            SDL_BindGPUVertexBuffers(pass, 0, &vb, 1);
        }"""),
        ("""        SDL_PushGPUVertexUniformData(cmd, 0, d.depth_map, sizeof d.depth_map);
        SDL_PushGPUFragmentUniformData(cmd, 0, &d.fu, sizeof d.fu);
        SDL_DrawGPUPrimitives(pass, d.count, 1, d.first, 0);""",
         """        SDL_PushGPUFragmentUniformData(cmd, 0, &d.fu, sizeof d.fu);
        if (d.native) {
            SDL_PushGPUVertexUniformData(cmd, 0, &d.native_uniforms, sizeof(d.native_uniforms));
        } else {
            SDL_PushGPUVertexUniformData(cmd, 0, d.depth_map, sizeof d.depth_map);
        }
        if (d.indexed) {
            SDL_DrawGPUIndexedPrimitives(pass, d.count, 1, d.first_index, d.native ? 0 : int32_t(d.first), 0);
        } else {
            SDL_DrawGPUPrimitives(pass, d.count, 1, d.first, 0);
        }"""),
        ("    if (vbuf) SDL_ReleaseGPUBuffer(dev, vbuf);\n    batch.clear();",
         """    if (vbuf) SDL_ReleaseGPUBuffer(dev, vbuf);
    if (native_buffer) SDL_ReleaseGPUBuffer(dev, native_buffer);
    if (index_buffer) SDL_ReleaseGPUBuffer(dev, index_buffer);
    native_data.clear();
    batch_indices.clear();
    native_program_cached = false;
    batch.clear();"""),
        ("    info.target_info.depth_stencil_format = depth_format;",
         "    info.target_info.depth_stencil_format = surface_depth_format(k.depth_format);"),
        ("            s->twin = s->depth ? make_texture(s->tw, s->th, depth_format, SDL_GPU_TEXTUREUSAGE_DEPTH_STENCIL_TARGET)",
         "            s->twin = s->depth ? make_texture(s->tw, s->th, surface_depth_format(s->format), SDL_GPU_TEXTUREUSAGE_DEPTH_STENCIL_TARGET)"),
        ("    depth_format = SDL_GPU_TEXTUREFORMAT_D24_UNORM_S8_UINT;",
         """    supports_depth16 = SDL_GPUTextureSupportsFormat(dev, SDL_GPU_TEXTUREFORMAT_D16_UNORM, SDL_GPU_TEXTURETYPE_2D,
                                                       SDL_GPU_TEXTUREUSAGE_DEPTH_STENCIL_TARGET);
    depth_format = SDL_GPU_TEXTUREFORMAT_D24_UNORM_S8_UINT;"""),
        ("    k.has_depth = d.depth != nullptr;",
         "    k.has_depth = d.depth != nullptr;\n    k.depth_format = k.has_depth ? uint8_t(dfmt) : 0;"),
        (span(gpu, "    SDL_GPUTexture *tmp = make_texture(w, h,", "    SDL_GPUCopyPass *copy = SDL_BeginGPUCopyPass(cmd);"),
         """    SDL_GPUCommandBuffer *cmd = SDL_AcquireGPUCommandBuffer(dev);
    if (!cmd) fatal("GPU readback command buffer: %s", SDL_GetError());
    SDL_GPUTexture *source = s->tex;
    if (s->tw != w || s->th != h) {
        source = make_texture(w, h, SDL_GPU_TEXTUREFORMAT_R8G8B8A8_UNORM,
                              SDL_GPU_TEXTUREUSAGE_SAMPLER | SDL_GPU_TEXTUREUSAGE_COLOR_TARGET);
        SDL_GPUBlitInfo blit{};
        blit.source.texture = s->tex;
        blit.source.y = uint32_t(s->margin * s->scale);
        blit.source.w = s->tw, blit.source.h = h * uint32_t(s->scale);
        blit.destination.texture = source;
        blit.destination.w = w, blit.destination.h = h;
        blit.load_op = SDL_GPU_LOADOP_DONT_CARE;
        blit.filter = SDL_GPU_FILTER_LINEAR;
        SDL_BlitGPUTexture(cmd, &blit);
    }
    // Readbacks are serialized by GSP and wait for completion before reusing the buffer.
    static SDL_GPUTransferBuffer *tb = nullptr;
    static uint32_t capacity = 0;
    const uint32_t bytes = w * h * 4;
    if (bytes > capacity) {
        if (tb) SDL_ReleaseGPUTransferBuffer(dev, tb);
        SDL_GPUTransferBufferCreateInfo tbi{SDL_GPU_TRANSFERBUFFERUSAGE_DOWNLOAD, bytes, 0};
        tb = SDL_CreateGPUTransferBuffer(dev, &tbi);
        if (!tb) fatal("GPU readback buffer: %s", SDL_GetError());
        capacity = bytes;
    }
"""),
        ("    src.texture = tmp, src.w = w, src.h = h, src.d = 1;",
         "    src.texture = source, src.w = w, src.h = h, src.d = 1;"),
        ("    SDL_WaitForGPUFences(dev, true, &fence, 1);\n    SDL_ReleaseGPUFence(dev, fence);",
         """    if (!fence || !SDL_WaitForGPUFences(dev, true, &fence, 1))
        fatal("GPU readback wait: %s", SDL_GetError());
    SDL_ReleaseGPUFence(dev, fence);"""),
        ("    const auto *rgba = static_cast<const uint8_t *>(SDL_MapGPUTransferBuffer(dev, tb, false));",
         "    const auto *rgba = static_cast<const uint8_t *>(SDL_MapGPUTransferBuffer(dev, tb, false));\n"
         "    if (!rgba) fatal(\"GPU readback mapping: %s\", SDL_GetError());"),
        ("    SDL_ReleaseGPUTransferBuffer(dev, tb);\n    SDL_ReleaseGPUTexture(dev, tmp);",
         "    if (source != s->tex) SDL_ReleaseGPUTexture(dev, source);"),
        ("    bool to_lcd = !(flags & 2) && !(flags & 0x20) && (((flags >> 12) & 7) <= 1);",
         """    // LM2 performs RGB transfers into padded scratch buffers before TextureCopy.
    // They must write guest memory; the LCD-only shortcut leaves that data stale.
    const bool bottom_rgb565 = quantized_lcd && in_h == 320 && flags == 0x00002000
        && (out == mem::VRAM_BASE + 0x68000 || out == mem::VRAM_BASE + 0x8d800);
    bool to_lcd = in_w == 240 && (in_h == 400 || in_h == 320)
        && in_w == out_w && in_h == out_h
        && !(flags & 2) && !(flags & 0x20) && (((flags >> 12) & 7) <= 1 || bottom_rgb565);"""),
        ("{int32_t(flags & 1), int32_t(hs), int32_t(vs), 0}};",
         "{int32_t(flags & 1), int32_t(hs), int32_t(vs), int32_t((flags >> 12) & 7)}};"),
    ])
    gsp = src / "hle" / "gsp.cpp"
    change(gsp, [
        ("#include <array>\n", "#include <array>\n#include <chrono>\n"),
        ("    uint32_t frames_rendered = 0; // display transfers to the top screen, for YW2_FPS",
         "    uint32_t frames_rendered = 0; // top-screen framebuffer swaps, for YW2_FPS"),
        ("        lcd[screen] = {info[1], info[3], info[4]};",
         "        lcd[screen] = {info[1], info[3], info[4]};\n"
         "        if (screen == 0) frames_rendered++;"),
        ("        static int vblanks = 0;\n        if (fps && ++vblanks % 300 == 0) { // every ~5 s",
         """        using Clock = std::chrono::steady_clock;
        static auto interval_start = Clock::now();
        const auto now = fps ? Clock::now() : interval_start;
        const double elapsed = std::chrono::duration<double>(now - interval_start).count();
        if (elapsed >= 5.0) {
            interval_start = now;"""),
        ("frames_rendered / 5.0, pica::time_commands.exchange(0) / 5e6, pica::time_setup.exchange(0) / 5e6,\n"
         "                pica::time_vertices.exchange(0) / 5e6, (long long)(pica::vertex_count.exchange(0) / 5),\n"
         "                pica::time_raster.exchange(0) / 5e6, pica::time_transfer.exchange(0) / 5e6);",
         "frames_rendered / elapsed, pica::time_commands.exchange(0) / (elapsed * 1e6),\n"
         "                pica::time_setup.exchange(0) / (elapsed * 1e6), pica::time_vertices.exchange(0) / (elapsed * 1e6),\n"
         "                static_cast<long long>(pica::vertex_count.exchange(0) / elapsed),\n"
         "                pica::time_raster.exchange(0) / (elapsed * 1e6), pica::time_transfer.exchange(0) / (elapsed * 1e6));"),
        ("            if ((c[3] >> 16) == 400) frames_rendered++;\n", ""),
    ])
    raster = src / "video" / "raster.cpp"
    change(raster, [
        ("    for (uint32_t base : {uint32_t(TEX0_ADDR), 0x095u, 0x09Du}) {",
         """    constexpr uint32_t texture_addresses[] = {TEX0_ADDR, 0x095, 0x09D};
    for (unsigned unit = 0; unit < 3; unit++) {
        if (!(regs[TEX_CONFIG] & (1u << unit))) continue;
        const uint32_t base = texture_addresses[unit];"""),
        ("    auto attr = [&](int i)", """    const uint32_t index = tiled_index(uint32_t(x), st.height - 1 - uint32_t(y), st.width);
    uint8_t *dp = st.depth ? st.depth + index * st.depth_bpp : nullptr;
    uint32_t stored = 0;
    uint32_t z = 0;
    if (dp) {
        stored = st.depth_format == 0 ? load16(dp) : dp[0] | (dp[1] << 8) | (dp[2] << 16);
        z = uint32_t(depth * float(st.depth_max));
        // A hidden fragment cannot change the buffer when stencil is off.
        if (!st.stencil && st.depth_test && !test(st.depth_func, z, stored)) return;
    }

    auto attr = [&](int i)"""),
        ("""    uint32_t index = tiled_index(uint32_t(x), st.height - 1 - uint32_t(y), st.width);

    // stencil and depth
    if (st.depth) {
        uint8_t *dp = st.depth + index * st.depth_bpp;
        uint32_t stored = st.depth_format == 0 ? load16(dp) : dp[0] | (dp[1] << 8) | (dp[2] << 16);
        uint8_t stencil = st.depth_format == 3 ? dp[3] : 0;
        uint32_t z = uint32_t(depth * float(st.depth_max));""",
         """    // stencil and depth
    if (dp) {
        uint8_t stencil = st.depth_format == 3 ? dp[3] : 0;"""),
        ("        if (st.depth_test && !test(st.depth_func, z, stored)) {\n"
         "            if (st.stencil) update_stencil(st.stencil_ops >> 4);",
         "        if (st.stencil && st.depth_test && !test(st.depth_func, z, stored)) {\n"
         "            update_stencil(st.stencil_ops >> 4);"),
        ("""    bool inside = true;
    for (int i = 0; i < 3 && inside; i++)
        for (int plane = 0; plane < 7 && inside; plane++) inside = plane_distance(in[i], plane, ky) >= 0;
    for (int plane = 0; plane < 7 && n >= 3 && !inside; plane++) {""",
         """    unsigned outside[3]{};
    for (int i = 0; i < 3; i++)
        for (int plane = 0; plane < 7; plane++)
            if (!(plane_distance(in[i], plane, ky) >= 0)) outside[i] |= 1u << plane;
    if (outside[0] & outside[1] & outside[2]) return;
    const unsigned crossed = outside[0] | outside[1] | outside[2];
    for (int plane = 0; plane < 7 && n >= 3 && crossed; plane++) {
        if (!(crossed & (1u << plane))) continue;"""),
    ])
    pica = src / "video" / "pica.cpp"
    change(pica, [
        ('#include "gpu/gpu.h"\n', '#include "gpu/gpu.h"\n#include "pica_shader_jit.h"\n'),
        ("#include <condition_variable>\n", "#include <atomic>\n"),
        ("ShaderSetup vs;", "ShaderSetup vs;\nstatic uint64_t shader_revision = 0;"),
        ("    uint32_t stride, type, count;", "    uint32_t stride, type, count, address;"),
        ("                attrs[attr] = {nullptr, stride, type, count};\n                uint32_t addr = base + r[0] + offset;",
         "                uint32_t addr = base + r[0] + offset;\n                attrs[attr] = {nullptr, stride, type, count, addr};"),
        ("    void read(uint32_t index, Vec4 out[16]) const {",
         """    gpu::RawVertexInput raw_input(uint32_t first, uint32_t last, uint32_t count) const {
        gpu::RawVertexInput raw;
        if (!count || count > attr_count || count > 12 || (((1u << count) - 1) & fixed_mask)) return raw;
        const uint32_t stride = attrs[0].stride;
        if (!stride || (stride & 3)) return raw;
        uint32_t base = attrs[0].address;
        for (uint32_t i = 0; i < count; ++i) {
            if (!attrs[i].data || attrs[i].stride != stride) return raw;
            base = std::min(base, attrs[i].address);
        }
        if (base & 3) return raw;
        uint32_t tail = 0;
        for (uint32_t i = 0; i < count; ++i) {
            const auto &attr = attrs[i];
            const uint32_t size = attr_type_size(attr.type), offset = attr.address - base;
            const uint32_t width = attr.type == 3 ? attr.count : attr.count <= 2 ? 2 : 4;
            if (offset >= stride || offset + width * size > stride || (offset & (size - 1))) return {};
            raw.formats[i] = uint16_t(offset | (attr.type << 8) | (attr.count << 10));
            tail = std::max(tail, offset + width * size);
        }
        const uint64_t start = uint64_t(base) + uint64_t(first) * stride;
        const uint64_t bytes = uint64_t(last - first) * stride + tail;
        if (start + bytes > UINT32_MAX) return {};
        raw.data = phys(uint32_t(start), uint32_t(bytes));
        if (!raw.data) return {};
        raw.bytes = uint32_t(bytes);
        raw.stride = stride;
        return raw;
    }

    void read(uint32_t index, Vec4 out[16]) const {"""),
        ("            vs.code[at & 4095] = value;",
         """            auto &word = vs.code[at & 4095];
            if (word != value) ++shader_revision;
            word = value;"""),
        ("            vs.swizzle[at & 127] = value;",
         """            auto &word = vs.swizzle[at & 127];
            if (word != value) ++shader_revision;
            word = value;"""),
        ("    OutputMap map;\n", """    OutputMap map;
    auto cpu_shader = [&]() -> CompiledVertex {
#ifdef LGM2_VERTEX_JIT
        static const bool interpret = std::getenv("LGM2_INTERPRET_VERTEX") != nullptr;
        if (!interpret) return find_compiled_shader(vs, map.entry, shader_revision);
#endif
        return nullptr;
    };
"""),
        ("shaded[k] = shade(attrs, map);", "shaded[k] = shade(attrs, map, compiled);"),
        ("e.v = shade(attrs, map);", "e.v = shade(attrs, map, compiled);"),
        ("Vertex v = shade(attrs, map);", "Vertex v = shade(attrs, map, compiled);"),
        (span(pica, "        if (lanes == 1 || count < 64)", "    void slice("),
         """        if (lanes == 1 || count < 256) return fn(0, count);
        job = &fn;
        job_count = count;
        pending.store(lanes - 1, std::memory_order_relaxed);
        generation.fetch_add(1, std::memory_order_release);
        generation.notify_all();
        slice(0, fn, count);
        for (int left = pending.load(std::memory_order_acquire); left;
             left = pending.load(std::memory_order_acquire)) {
            pending.wait(left, std::memory_order_acquire);
        }
    }

private:
    int lanes = 1;
    std::atomic<int> pending{0};
    std::atomic<uint64_t> generation{0};
    size_t job_count = 0;
    const std::function<void(size_t, size_t)> *job = nullptr;

"""),
        (span(pica, "        uint64_t seen = 0;", "\n};\n\nWorkers &workers"),
         """        uint64_t seen = 0;
        for (;;) {
            generation.wait(seen, std::memory_order_acquire);
            seen = generation.load(std::memory_order_acquire);
            slice(lane, *job, job_count);
            if (pending.fetch_sub(1, std::memory_order_acq_rel) == 1) pending.notify_one();
        }
    }"""),
        (span(pica, "            Vec4 v = {{0, 0, 0, 1}};", "            out[i] = v;"),
         """            Vec4 v = {{0, 0, 0, 1}};
            const uint8_t *p = a.data + size_t(index) * a.stride;
            switch (a.type) {
            case 0:
                for (uint32_t c = 0; c < a.count; ++c) v[c] = float(int8_t(p[c]));
                break;
            case 1:
                for (uint32_t c = 0; c < a.count; ++c) v[c] = float(p[c]);
                break;
            case 2:
                for (uint32_t c = 0; c < a.count; ++c) v[c] = float(int16_t(load16(p + 2 * c)));
                break;
            default:
                std::memcpy(v.v, p, a.count * sizeof(float));
                break;
            }
"""),
        (span(pica, "struct OutputMap {", "    // colors are clamped"),
         """struct OutputMap {
    struct Component {
        uint8_t reg, lane, semantic;
    };
    Component components[28];
    uint8_t input_map[16];
    uint32_t output_count = 0;
    uint32_t input_count = (regs[VS_INPUT_CONFIG] & 0xF) + 1;
    uint32_t entry = regs[VS_ENTRY] & 0xFFFF;

    OutputMap() {
        const uint64_t inputs = regs[VS_INPUT_MAP_LO] | (uint64_t(regs[VS_INPUT_MAP_HI]) << 32);
        for (uint32_t i = 0; i < input_count; ++i) input_map[i] = (inputs >> (4 * i)) & 0xF;
        const uint32_t mask = regs[VS_OUTPUT_MASK] & 0xFFFF;
        const uint32_t count = regs[VS_OUTPUT_COUNT] & 7;
        uint32_t reg = 0;
        for (uint32_t k = 0; k < count; ++k) {
            while (reg < 16 && !((mask >> reg) & 1)) ++reg;
            if (reg >= 16) break;
            const uint32_t mapping = regs[VS_OUTPUT_MAP + k];
            for (unsigned lane = 0; lane < 4; ++lane) {
                const uint32_t semantic = (mapping >> (8 * lane)) & 0x1F;
                if (semantic < SEMANTIC_COUNT) {
                    components[output_count++] = {uint8_t(reg), uint8_t(lane), uint8_t(semantic)};
                }
            }
            ++reg;
        }
    }
};

Vertex shade(const Vec4 attrs[16], const OutputMap &map, CompiledVertex compiled = nullptr) {
    Vec4 in[16] = {}, out[16] = {};
    for (uint32_t i = 0; i < map.input_count; ++i) in[map.input_map[i]] = attrs[i];
    if (compiled) {
        Vec4 scratch[16];
        compiled(vs.f, in, out, scratch);
    } else {
        run_shader(vs, map.entry, in, out);
    }

    Vertex v{};
    for (uint32_t i = 0; i < map.output_count; ++i) {
        const auto &component = map.components[i];
        v.a[component.semantic] = out[component.reg][component.lane];
    }
"""),
        ("            Vec4 attrs[16];", "            Vec4 attrs[16]{};"),
        ("        Vec4 attrs[16];\n        for (uint32_t i", "        Vec4 attrs[16]{};\n        for (uint32_t i"),
        ("    auto index_at = [&](uint32_t i) {\n        return indexed ? (wide ? load16(indices + 2 * i) : indices[i])",
         "    auto index_at = [&](const uint8_t *source, uint32_t i) {\n        return indexed ? (wide ? load16(source + 2 * i) : source[i])"),
        (span(pica, "        static std::vector<int32_t> slot;", "        shaded.resize(unique.size());"),
         """        struct IndexList {
            const uint8_t *source = nullptr;
            uint32_t first = 0, last = 0;
            std::vector<uint8_t> bytes;
            std::vector<uint32_t> unique, remapped;
        };
        static IndexList cache[64], scratch;
        static std::vector<int32_t> slot;
        static std::vector<Vertex> shaded;
        const bool cacheable = indexed && n <= 65536;
        const uintptr_t address = reinterpret_cast<uintptr_t>(indices);
        IndexList &list = cacheable ? cache[((address >> 3) ^ (address >> 12) ^ n) & 63] : scratch;
        const size_t bytes = n * size_t(wide ? 2 : 1);
        if (!cacheable || list.source != indices || list.remapped.size() != n || list.bytes.size() != bytes ||
            std::memcmp(list.bytes.data(), indices, bytes)) {
            if (cacheable) {
                list.bytes.assign(indices, indices + bytes);
                list.source = indices;
            }
            list.unique.clear();
            list.remapped.resize(n);
            const uint8_t *source = cacheable ? list.bytes.data() : indices;
            list.first = UINT32_MAX;
            list.last = 0;
            for (uint32_t i = 0; i < n; ++i) {
                uint32_t index = index_at(source, i);
                if (index >= slot.size()) slot.resize(index + 1, -1);
                if (slot[index] < 0) {
                    slot[index] = int32_t(list.unique.size());
                    list.unique.push_back(index);
                    list.first = std::min(list.first, index);
                    list.last = std::max(list.last, index);
                }
                list.remapped[i] = uint32_t(slot[index]);
            }
            for (uint32_t index : list.unique) slot[index] = -1;
        }
        const auto &unique = list.unique;
"""),
        ("        shaded.resize(unique.size());", """        uint32_t topology = (regs[PRIMITIVE_CONFIG] >> 8) & 3;
        const bool indexed_list = gpu::active() && indexed && !deferring && draw_log_state == 0 &&
            (topology == 0 || topology == 3) && assembler.list_count == 0 && n % 3 == 0;
        if (indexed_list) {
            uint32_t semantics[SEMANTIC_COUNT];
            std::fill(std::begin(semantics), std::end(semantics), UINT32_MAX);
            for (uint32_t i = 0; i < map.output_count; ++i) {
                const auto &component = map.components[i];
                semantics[component.semantic] = 4u * component.reg + component.lane;
            }
            gpu::RawVertexInput raw;
#ifdef LGM2_GPU_SPECIALIZED
            static const bool raw_vertices = !std::getenv("LGM2_UNPACK_VERTEX_INPUTS") && !std::getenv("LGM2_CPU_VERTEX")
                && !std::getenv("LGM2_INTERPRET_VERTEX") && !std::getenv("LGM2_GPU_VERTICES");
            if (raw_vertices) raw = loader.raw_input(list.first, list.last, map.input_count);
#endif
            auto draw = gpu::begin_native_vertices(uint32_t(unique.size()), n, map.input_count, semantics, shader_revision, raw);
            if (draw.attributes) {
                if (draw.raw) {
                    if (cacheable) {
                        const uint8_t *snapshot = list.bytes.data();
                        for (uint32_t i = 0; i < n; ++i) draw.indices[i] = index_at(snapshot, i) - list.first;
                    } else {
                        for (uint32_t i = 0; i < n; ++i) draw.indices[i] = unique[list.remapped[i]] - list.first;
                    }
                } else {
                    std::memcpy(draw.indices, list.remapped.data(), n * sizeof(uint32_t));
                    workers().run(unique.size(), [&](size_t begin, size_t end) {
                        Vec4 attrs[16]{};
                        for (size_t i = begin; i < end; ++i) {
                            loader.read(unique[i], attrs);
                            std::memcpy(draw.attributes + i * map.input_count * 4, attrs, map.input_count * sizeof(Vec4));
                        }
                    });
                }
                time_vertices += std::chrono::duration_cast<std::chrono::nanoseconds>(
                                     std::chrono::steady_clock::now() - t_shade).count();
                vertex_count += n;
                end_draw();
                count_draw(true);
                return;
            }
        }
        const auto compiled = cpu_shader();
        shaded.resize(unique.size());"""),
        ("        for (uint32_t i = 0; i < n; i++) assembler.push(shaded[size_t(slot[index_at(i)])]);",
         """        auto *draw_indices = indexed_list ? gpu::begin_indexed_vertices(shaded.data(), uint32_t(shaded.size()), n)
                                          : nullptr;
        if (draw_indices) {
            std::memcpy(draw_indices, list.remapped.data(), n * sizeof(uint32_t));
        } else {
            for (uint32_t position : list.remapped) assembler.push(shaded[position]);
        }"""),
        ("        for (uint32_t index : unique) slot[index] = -1;\n    } else {", "    } else {"),
        ("            uint32_t index = index_at(i);", "            uint32_t index = index_at(indices, i);"),
        ("        // indexed draws reuse shaded vertices",
         "        const auto compiled = cpu_shader();\n        // indexed draws reuse shaded vertices"),
    ])
    shader = src / "video" / "shader.cpp"
    change(shader, [
        ('#include "log.h"\n', '#include "log.h"\n#include "pica_shader_arithmetic.h"\n'),
        (span(shader, "// 0 * anything", "struct Frame"), ""),
        (span(shader, "    static const Vec4 ones", "    auto evaluate"), ""),
        ("    int32_t addr[3] = {0, 0, 0}; // a0.x, a0.y, aL",
         "    int32_t addr[4] = {}; // constant zero, a0.x, a0.y, aL"),
        ("addr[2] += f.increment;", "addr[3] += f.increment;"),
        ("addr[2] = iu[1];", "addr[3] = iu[1];"),
        (span(shader, "        // arithmetic:", "        // flow control"),
         """        if (op < 0x20 || op >= 0x2E) {
            run_arithmetic(s, pc, ins, in, out, tmp, addr, cond);
            pc++;
            continue;
        }

"""),
    ])
    transfer = src / "video" / "transfer.cpp"
    change(transfer, [
        ("    auto src_offset = [&](uint32_t x, uint32_t y) {",
         """    // The game's padded top-screen transfers repeatedly untile 8-bit color.
    // Horizontal samples are adjacent in Morton order when the first x is even.
    if (!flip && !tiled_both && !input_linear && scale <= 1 && in_fmt <= FB_RGB8 && out_fmt <= FB_RGB8 &&
        in_w == out_w && in_h == out_h && !((in_w | in_h) & 7) &&
        (uintptr_t(src) + uint64_t(in_w) * in_h * ibpp <= uintptr_t(dst) ||
         uintptr_t(dst) + uint64_t(w) * h * obpp <= uintptr_t(src))) {
        const uint32_t in_color = ibpp == 4 ? 1 : 0, out_color = obpp == 4 ? 1 : 0;
        for (uint32_t y = 0; y < h; ++y) {
            uint8_t *row = dst + size_t(y) * w * obpp;
            const uint8_t *tiles = src + size_t(tiled_index(0, y, in_w)) * ibpp;
            for (uint32_t x = 0; x < w; ++x, row += obpp) {
                const uint32_t ix = x << hs;
                const uint8_t *p = tiles + size_t((ix & ~7u) * 8 + morton8(ix, 0)) * ibpp;
                if (out_color) row[0] = in_color ? (scale ? (unsigned(p[0]) + p[ibpp]) >> 1 : p[0]) : 255;
                for (uint32_t c = 0; c < 3; ++c) {
                    const auto offset = c + in_color;
                    row[c + out_color] = scale ? (unsigned(p[offset]) + p[ibpp + offset]) >> 1 : p[offset];
                }
            }
        }
        return;
    }
    auto src_offset = [&](uint32_t x, uint32_t y) {"""),
    ])
    texture = src / "video" / "texture.cpp"
    change(texture, [
        ("""        uint8_t a = 255;
        uint64_t word;
        if (alpha) {
            std::memcpy(&word, sub, 8);
            a = expand4((word >> (4 * (4 * x + y))) & 15);
            sub += 8;
        }
        std::memcpy(&word, sub, 8);
        Rgba c = etc1(word, x, y);
        c.a = a;
        return c;""",
         """        uint64_t color_word, alpha_word = UINT64_MAX;
        if (alpha) std::memcpy(&alpha_word, sub, 8);
        std::memcpy(&color_word, sub + (alpha ? 8 : 0), 8);
        // Adjacent pixels and bilinear samples tend to reuse the same compressed block.
        // Compare the actual bytes so a rewritten guest texture never reuses stale texels.
        struct Block {
            uint64_t color, alpha;
            uint32_t decoded;
            Rgba texels[16];
        };
        thread_local Block blocks[256]{};
        uintptr_t address = reinterpret_cast<uintptr_t>(sub) >> 3;
        Block &block = blocks[(address ^ (address >> 8)) & 255];
        if (block.color != color_word || block.alpha != alpha_word) {
            block.color = color_word;
            block.alpha = alpha_word;
            block.decoded = 0;
        }
        uint32_t index = 4 * x + y;
        uint32_t bit = 1u << index;
        if (!(block.decoded & bit)) {
            Rgba c = etc1(color_word, x, y);
            c.a = expand4((alpha_word >> (4 * index)) & 15);
            block.texels[index] = c;
            block.decoded |= bit;
        }
        return block.texels[index];"""),
        ("    case 7: return ((c % size) + size) % size;",
         """    case 7:
        if ((size & (size - 1)) == 0) return c & (size - 1);
        return ((c % size) + size) % size;"""),
    ])
    filesystem = src / "hle" / "fs.cpp"
    change(filesystem, [
        ('#include "platform.h"\n', '#include "platform.h"\n#include "save_storage.h"\n'),
        ("        if (!write && !create) p = fill_version(a, *p);",
         """        if (!write && !create) p = fill_version(a, *p);
        if (a.id == SAVE_DATA) {
            if (lm2::is_save_format_file(*p)) return ERR_FILE_NOT_FOUND;
            if (write) lm2::backup_save_entry(a.root, *p);
        }"""),
        ("                if (req.id() == 0x0807) fs::remove_all(*p, ec);",
         """                if (a->id == SAVE_DATA) {
                    if (*p == a->root || lm2::is_save_format_file(*p)) {
                        req.reply(1, 0, ERR_UNSUPPORTED);
                        break;
                    }
                    lm2::backup_save_entry(a->root, *p);
                }
                if (req.id() == 0x0807) fs::remove_all(*p, ec);"""),
        (span(filesystem, "            for (auto &e : fs::directory_iterator(*p, ec))", "            // another game's"),
         """            for (auto &e : fs::directory_iterator(*p, ec)) {
                if (a->id == SAVE_DATA && lm2::is_save_format_file(e.path())) continue;
                d->entries.push_back({e.path().filename().string(), e.is_directory(ec), e.is_directory(ec) ? 0 : e.file_size(ec)});
            }
"""),
        (span(filesystem, "        case 0x0845:", "        // Secure values"),
         """        case 0x0845: { // GetFormatInfo
            lm2::SaveFormat format = {512 << 10, 32, 32, 0};
            if (req.arg(0) == SAVE_DATA) {
                auto stored = lm2::read_save_format(save_root());
                if (!stored) {
                    req.reply(1, 0, ERR_NOT_FORMATTED);
                    break;
                }
                format = *stored;
            }
            auto r = req.reply(5, 0);
            for (auto field : format) r.push(field);
            break;
        }
"""),
        (span(filesystem, "        case 0x084C:", "        default:"),
         """        case 0x084C: { // FormatSaveData
            if (req.arg(0) != SAVE_DATA || req.arg(1) != PATH_EMPTY || req.arg(3) > UINT32_MAX / 512) {
                req.reply(1, 0, ERR_UNSUPPORTED);
                break;
            }
            lm2::SaveFormat format = {req.arg(3) * 512, req.arg(4), req.arg(5), req.arg(8) & 1};
            LOG_IPC("fs LM2 format: %#x bytes, %u directories, %u files, duplicate %u",
                    format[0], format[1], format[2], format[3]);
            lm2::format_save(save_root(), format);
            req.reply(1, 0);
            break;
        }
"""),
    ])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("upstream", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    prepare(arguments.upstream, arguments.output)
