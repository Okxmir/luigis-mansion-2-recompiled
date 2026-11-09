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
};
NativeVertices begin_native_vertices(uint32_t vertex_count, uint32_t index_count, uint32_t attribute_count,
                                    const uint32_t semantic_map[24]);
void end_draw();"""),
    ])
    change(gpu, [
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
         "stencil_zfail, stencil_zpass, stencil_read, stencil_write, has_depth, wdepth, depth_format, native_cull;"),
        ("    info.vertex_shader = vs_pica, info.fragment_shader =",
         "    info.vertex_shader = k.native_cull ? vs_native : vs_pica;\n    info.fragment_shader ="),
        ("""    info.vertex_input_state.vertex_buffer_descriptions = &vb;
    info.vertex_input_state.num_vertex_buffers = 1;
    info.vertex_input_state.vertex_attributes = attrs;
    info.vertex_input_state.num_vertex_attributes = 6;""",
         """    if (!k.native_cull) {
        info.vertex_input_state.vertex_buffer_descriptions = &vb;
        info.vertex_input_state.num_vertex_buffers = 1;
        info.vertex_input_state.vertex_attributes = attrs;
        info.vertex_input_state.num_vertex_attributes = 6;
    }"""),
        ("    info.rasterizer_state.cull_mode = SDL_GPU_CULLMODE_NONE; // culled per triangle on the CPU",
         """    info.rasterizer_state.cull_mode = k.native_cull >= 2 ? SDL_GPU_CULLMODE_BACK : SDL_GPU_CULLMODE_NONE;
    info.rasterizer_state.front_face = k.native_cull == 2 ? SDL_GPU_FRONTFACE_CLOCKWISE
                                                          : SDL_GPU_FRONTFACE_COUNTER_CLOCKWISE;"""),
        ("struct DrawRec {", """struct NativeUniforms {
    float depth[4], viewport[4];
    uint32_t attributes[4], program[4], uniforms[4];
};
static_assert(sizeof(NativeUniforms) == 80);

struct DrawRec {
    PipelineKey key;
    bool native;
    NativeUniforms native_uniforms;"""),
        ("std::vector<DrawRec> batch;", """std::vector<DrawRec> batch;
std::vector<uint32_t> native_data, native_indices;
uint32_t native_code, native_swizzle;
bool native_program_cached = false;

uint32_t append_native(const void *source, size_t words) {
    const size_t begin = native_data.size();
    native_data.resize(begin + words);
    if (source) std::memcpy(native_data.data() + begin, source, words * sizeof(uint32_t));
    return uint32_t(begin * sizeof(uint32_t));
}

void upload_native(SDL_GPUCommandBuffer *cmd, SDL_GPUBuffer **data, SDL_GPUBuffer **indices) {
    if (native_indices.empty()) return;
    const uint32_t data_bytes = uint32_t(native_data.size() * sizeof(uint32_t));
    const uint32_t index_bytes = uint32_t(native_indices.size() * sizeof(uint32_t));
    SDL_GPUTransferBufferCreateInfo transfer_info{SDL_GPU_TRANSFERBUFFERUSAGE_UPLOAD, data_bytes + index_bytes, 0};
    SDL_GPUTransferBuffer *transfer = SDL_CreateGPUTransferBuffer(dev, &transfer_info);
    SDL_GPUBufferCreateInfo data_info{SDL_GPU_BUFFERUSAGE_GRAPHICS_STORAGE_READ, data_bytes, 0};
    SDL_GPUBufferCreateInfo index_info{SDL_GPU_BUFFERUSAGE_INDEX, index_bytes, 0};
    *data = SDL_CreateGPUBuffer(dev, &data_info);
    *indices = SDL_CreateGPUBuffer(dev, &index_info);
    if (!transfer || !*data || !*indices) fatal("GPU vertex buffers: %s", SDL_GetError());
    auto *mapped = static_cast<uint8_t *>(SDL_MapGPUTransferBuffer(dev, transfer, false));
    if (!mapped) fatal("GPU vertex upload mapping: %s", SDL_GetError());
    std::memcpy(mapped, native_data.data(), data_bytes);
    std::memcpy(mapped + data_bytes, native_indices.data(), index_bytes);
    SDL_UnmapGPUTransferBuffer(dev, transfer);
    SDL_GPUCopyPass *copy = SDL_BeginGPUCopyPass(cmd);
    SDL_GPUTransferBufferLocation data_source{transfer, 0}, index_source{transfer, data_bytes};
    SDL_GPUBufferRegion data_dest{*data, 0, data_bytes}, index_dest{*indices, 0, index_bytes};
    SDL_UploadToGPUBuffer(copy, &data_source, &data_dest, false);
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
        ("    d.pipeline = pipeline(k);", "    d.key = k;\n    d.pipeline = pipeline(k);"),
        ("void end_draw() {\n    if (cur_skip) return;",
         """NativeVertices begin_native_vertices(uint32_t vertex_count, uint32_t index_count, uint32_t attribute_count,
                                    const uint32_t semantic_map[24]) {
    if (!vs_native || cur_skip || interp_wanted || cur_ky != 1.0f || hud_scale() < 1.0f) return {};
    NativeUniforms &u = cur.native_uniforms;
    std::memcpy(u.depth, cur.depth_map, sizeof(u.depth));
    u.viewport[0] = cur_refit ? refit_ax : 1.0f;
    u.viewport[1] = cur_refit ? refit_bx : 0.0f;
    u.viewport[2] = cur_refit ? refit_ay : 1.0f;
    u.viewport[3] = cur_refit ? refit_by : 0.0f;
    if (!native_program_cached ||
        std::memcmp(native_data.data() + native_code / 4, vs.code, sizeof(vs.code)) ||
        std::memcmp(native_data.data() + native_swizzle / 4, vs.swizzle, sizeof(vs.swizzle))) {
        native_code = append_native(vs.code, std::size(vs.code));
        native_swizzle = append_native(vs.swizzle, std::size(vs.swizzle));
        native_program_cached = true;
    }
    u.program[0] = native_code;
    u.program[1] = native_swizzle;
    u.program[2] = append_native(vs.f, sizeof(vs.f) / 4);
    u.program[3] = regs[VS_ENTRY] & 0xffff;
    u.uniforms[0] = append_native(vs.i, sizeof(vs.i) / 4);
    u.uniforms[1] = vs.b;
    u.uniforms[2] = append_native(semantic_map, 24);
    u.attributes[0] = append_native(nullptr, size_t(vertex_count) * attribute_count * 4);
    u.attributes[1] = attribute_count;
    u.attributes[2] = regs[VS_INPUT_MAP_LO];
    u.attributes[3] = regs[VS_INPUT_MAP_HI];
    cur.native = true;
    cur.key.native_cull = cur_cull == 1 || cur_cull == 2 ? uint8_t(cur_cull + 1) : 1;
    cur.pipeline = pipeline(cur.key);
    cur.first = uint32_t(native_indices.size());
    cur.count = index_count;
    native_indices.resize(native_indices.size() + index_count);
    return {native_data.data() + u.attributes[0] / 4, native_indices.data() + cur.first};
}

void end_draw() {
    if (cur_skip) return;
    if (cur.native) {
        batch.push_back(cur);
        return;
    }"""),
        ("    if (!vbuf) batch.clear(); // out of GPU memory: this batch is lost",
         """    SDL_GPUBuffer *native_buffer = nullptr, *index_buffer = nullptr;
    upload_native(cmd, &native_buffer, &index_buffer);"""),
        ("    for (const DrawRec &d : batch) {\n        begin_render_pass",
         "    for (const DrawRec &d : batch) {\n        if (!d.native && !vbuf) continue;\n        begin_render_pass"),
        ("        SDL_GPUBufferBinding vb{vbuf, 0};\n        SDL_BindGPUVertexBuffers(pass, 0, &vb, 1);",
         """        if (d.native) {
            SDL_GPUBufferBinding ib{index_buffer, 0};
            SDL_BindGPUIndexBuffer(pass, &ib, SDL_GPU_INDEXELEMENTSIZE_32BIT);
            SDL_BindGPUVertexStorageBuffers(pass, 0, &native_buffer, 1);
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
            SDL_DrawGPUIndexedPrimitives(pass, d.count, 1, d.first, 0, 0);
        } else {
            SDL_PushGPUVertexUniformData(cmd, 0, d.depth_map, sizeof d.depth_map);
            SDL_DrawGPUPrimitives(pass, d.count, 1, d.first, 0);
        }"""),
        ("    if (vbuf) SDL_ReleaseGPUBuffer(dev, vbuf);\n    batch.clear();",
         """    if (vbuf) SDL_ReleaseGPUBuffer(dev, vbuf);
    if (native_buffer) SDL_ReleaseGPUBuffer(dev, native_buffer);
    if (index_buffer) SDL_ReleaseGPUBuffer(dev, index_buffer);
    native_data.clear();
    native_indices.clear();
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
        ("if (lanes == 1 || count < 64)", "if (lanes == 1 || count < 256)"),
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

Vertex shade(const Vec4 attrs[16], const OutputMap &map) {
    Vec4 in[16] = {}, out[16] = {};
    for (uint32_t i = 0; i < map.input_count; ++i) in[map.input_map[i]] = attrs[i];
    run_shader(vs, map.entry, in, out);

    Vertex v{};
    for (uint32_t i = 0; i < map.output_count; ++i) {
        const auto &component = map.components[i];
        v.a[component.semantic] = out[component.reg][component.lane];
    }
"""),
        ("            Vec4 attrs[16];", "            Vec4 attrs[16]{};"),
        ("        Vec4 attrs[16];\n        for (uint32_t i", "        Vec4 attrs[16]{};\n        for (uint32_t i"),
        ("        shaded.resize(unique.size());", """        uint32_t topology = (regs[PRIMITIVE_CONFIG] >> 8) & 3;
        if (gpu::active() && indexed && !deferring && draw_log_state == 0 &&
            (topology == 0 || topology == 3) && assembler.list_count == 0 && n % 3 == 0) {
            uint32_t semantics[SEMANTIC_COUNT];
            std::fill(std::begin(semantics), std::end(semantics), UINT32_MAX);
            for (uint32_t i = 0; i < map.output_count; ++i) {
                const auto &component = map.components[i];
                semantics[component.semantic] = 4u * component.reg + component.lane;
            }
            auto draw = gpu::begin_native_vertices(uint32_t(unique.size()), n, map.input_count, semantics);
            if (draw.attributes) {
                for (uint32_t i = 0; i < n; ++i) draw.indices[i] = uint32_t(slot[index_at(i)]);
                workers().run(unique.size(), [&](size_t begin, size_t end) {
                    Vec4 attrs[16]{};
                    for (size_t i = begin; i < end; ++i) {
                        loader.read(unique[i], attrs);
                        std::memcpy(draw.attributes + i * map.input_count * 4, attrs, map.input_count * sizeof(Vec4));
                    }
                });
                for (uint32_t index : unique) slot[index] = -1;
                time_vertices += std::chrono::duration_cast<std::chrono::nanoseconds>(
                                     std::chrono::steady_clock::now() - t_shade).count();
                vertex_count += n;
                end_draw();
                count_draw(true);
                return;
            }
        }
        shaded.resize(unique.size());"""),
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
