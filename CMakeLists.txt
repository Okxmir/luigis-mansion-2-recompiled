cmake_minimum_required(VERSION 3.24)
if(POLICY CMP0141)
    cmake_policy(SET CMP0141 NEW)
endif()
set(CMAKE_MSVC_DEBUG_INFORMATION_FORMAT "$<$<CONFIG:Debug,RelWithDebInfo>:Embedded>")
set(CMAKE_TRY_COMPILE_CONFIGURATION Release)
project(LuigisMansion2Native LANGUAGES C CXX)

if(NOT WIN32 OR NOT MSVC OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
    message(FATAL_ERROR "Use the Windows x64 MSVC toolchain")
endif()

set(CMAKE_C_STANDARD 17)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(UPSTREAM "${CMAKE_CURRENT_SOURCE_DIR}/build/upstream/clockwork-master")
set(GENERATED "${CMAKE_CURRENT_SOURCE_DIR}/generated/lm2-eur")
set(RUNTIME "${CMAKE_CURRENT_BINARY_DIR}/runtime")
set(SDL3_DIR "${CMAKE_CURRENT_SOURCE_DIR}/build/upstream/SDL3-3.4.0/cmake")
find_package(Python3 REQUIRED COMPONENTS Interpreter)
find_package(SDL3 REQUIRED CONFIG COMPONENTS SDL3)

set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS tools/prepare_runtime.py)
execute_process(
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/prepare_runtime.py" "${UPSTREAM}" "${RUNTIME}"
    COMMAND_ERROR_IS_FATAL ANY
)

file(GLOB GAME_CODE CONFIGURE_DEPENDS "${GENERATED}/*.c")
if(NOT GAME_CODE)
    message(FATAL_ERROR "Generate the game code with the ARM recompiler first")
endif()

add_library(game_code OBJECT ${GAME_CODE})
target_include_directories(game_code PRIVATE "${RUNTIME}/include" "${GENERATED}")
target_compile_definitions(game_code PRIVATE RECOMP_TRACE_CALLS)
target_compile_options(game_code PRIVATE /bigobj /fp:precise /w)
option(LGM2_FAST_BUILD "Skip optimization of generated code for first boot diagnosis" ON)
if(LGM2_FAST_BUILD)
    target_compile_options(game_code PRIVATE /Od)
endif()

set(RUNTIME_FILES
    arm_ops.c
    audio/bcstm.cpp
    audio/dsp_hle.cpp
    dump.cpp
    frontend/sdl.cpp
    frontend/settings.cpp
    hle/apt.cpp
    hle/cecd.cpp
    hle/cfg.cpp
    hle/dsp.cpp
    hle/err.cpp
    hle/frd.cpp
    hle/fs.cpp
    hle/gsp.cpp
    hle/hid.cpp
    hle/offline.cpp
    hle/ptm.cpp
    hle/service.cpp
    hle/srv.cpp
    hle/stubs.cpp
    hle/uds.cpp
    hle/y2r.cpp
    kernel/kernel.cpp
    kernel/svc.cpp
    level5.cpp
    loader.cpp
    log.cpp
    memory.cpp
    mods.cpp
    net/air.cpp
    net/relay.cpp
    platform.cpp
    video/gpu/gpu.cpp
    video/lighting.cpp
    video/pica.cpp
    video/raster.cpp
    video/shader.cpp
    video/texture.cpp
    video/transfer.cpp
    video/upscale.cpp
    video/widescreen.cpp
)
list(TRANSFORM RUNTIME_FILES PREPEND "${RUNTIME}/src/")

add_executable(LuigisMansion2 src/main.cpp src/lm2_services.cpp src/shared_font.cpp src/save_storage.cpp
    tests/save_crc.cpp ${RUNTIME_FILES})
target_include_directories(LuigisMansion2 PRIVATE "${RUNTIME}/include" "${RUNTIME}/src" src tests)
target_compile_definitions(LuigisMansion2 PRIVATE NOMINMAX _CRT_SECURE_NO_WARNINGS)
target_compile_options(LuigisMansion2 PRIVATE /W3 /utf-8)
target_link_libraries(LuigisMansion2 PRIVATE game_code SDL3::SDL3 ws2_32 bcrypt)

find_program(LGM2_DXC dxc HINTS "${CMAKE_CURRENT_SOURCE_DIR}/build/upstream/dxc-1.8.2505.1/bin/x64" NO_DEFAULT_PATH)
if(LGM2_DXC AND EXISTS "${LGM2_DXC}")
    set(GPU_VERTEX_HEADER "${CMAKE_CURRENT_BINARY_DIR}/lm2_gpu_vertex.inc")
    add_custom_command(OUTPUT "${GPU_VERTEX_HEADER}"
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/compile_gpu_vertex.py"
                "${LGM2_DXC}" "${CMAKE_CURRENT_SOURCE_DIR}/src/pica_gpu_vertex.hlsl"
                "${CMAKE_CURRENT_SOURCE_DIR}/src/pica_lcd_blit.hlsl" "${GPU_VERTEX_HEADER}"
        DEPENDS tools/compile_gpu_vertex.py src/pica_gpu_vertex.hlsl src/pica_lcd_blit.hlsl
        VERBATIM
    )
    target_sources(LuigisMansion2 PRIVATE "${GPU_VERTEX_HEADER}")
    target_include_directories(LuigisMansion2 PRIVATE "${CMAKE_CURRENT_BINARY_DIR}")
    target_compile_definitions(LuigisMansion2 PRIVATE LGM2_GPU_VERTEX_SHADER)
    get_filename_component(DXC_BIN "${LGM2_DXC}" DIRECTORY)
    get_filename_component(DXC_SDK "${DXC_BIN}/../.." ABSOLUTE)
    if(EXISTS "${DXC_SDK}/inc/dxcapi.h" AND EXISTS "${DXC_BIN}/dxcompiler.dll")
        target_sources(LuigisMansion2 PRIVATE src/pica_shader_spirv.cpp)
        target_include_directories(LuigisMansion2 PRIVATE "${DXC_SDK}/inc")
        target_compile_definitions(LuigisMansion2 PRIVATE LGM2_GPU_SPECIALIZED)
        add_custom_command(TARGET LuigisMansion2 POST_BUILD
            COMMAND "${CMAKE_COMMAND}" -E copy_if_different "${DXC_BIN}/dxcompiler.dll" "$<TARGET_FILE_DIR:LuigisMansion2>"
        )
        foreach(DXC_NOTICE LICENSE-LLVM.txt LICENSE-MIT.txt LICENSE-MS.txt)
            if(EXISTS "${DXC_SDK}/${DXC_NOTICE}")
                configure_file("${DXC_SDK}/${DXC_NOTICE}" "dxc-licenses/${DXC_NOTICE}" COPYONLY)
            endif()
        endforeach()
        message(STATUS "Vulkan vertex shader compilation enabled")
    else()
        message(STATUS "Full DXC SDK missing. Run scripts/prepare.ps1 to enable Vulkan vertex shader compilation.")
    endif()
else()
    message(STATUS "DXC missing. Run scripts/prepare.ps1 to enable the accelerated Vulkan build.")
endif()
add_custom_command(TARGET LuigisMansion2 POST_BUILD
    COMMAND "${CMAKE_COMMAND}" -E copy_if_different "$<TARGET_FILE:SDL3::SDL3>" "$<TARGET_FILE_DIR:LuigisMansion2>"
)

enable_testing()
add_test(NAME lm2_save_crc
    COMMAND LuigisMansion2 --verify-crc "${CMAKE_CURRENT_SOURCE_DIR}/extracted/LM2-EUR.cxi"
)

set(PICA_SHADER_REFERENCE "${UPSTREAM}/runtime/src/video/shader.cpp")
set_source_files_properties("${PICA_SHADER_REFERENCE}" PROPERTIES COMPILE_DEFINITIONS "run_shader=run_shader_reference")
add_executable(lm2_vertex_test tests/pica_vertex.cpp "${PICA_SHADER_REFERENCE}" "${RUNTIME}/src/video/shader.cpp")
target_include_directories(lm2_vertex_test PRIVATE "${RUNTIME}/include" "${RUNTIME}/src" src)
target_compile_definitions(lm2_vertex_test PRIVATE NOMINMAX)
add_test(NAME lm2_pica_vertex COMMAND lm2_vertex_test)

set(LGM2_XBYAK "${CMAKE_CURRENT_SOURCE_DIR}/build/upstream/xbyak-df112862583c2d327c1d9782fd28f53aa675f11d")
if(EXISTS "${LGM2_XBYAK}/xbyak/xbyak.h")
    foreach(target LuigisMansion2 lm2_vertex_test)
        target_sources(${target} PRIVATE src/pica_shader_jit.cpp)
        target_include_directories(${target} PRIVATE "${LGM2_XBYAK}")
        target_compile_definitions(${target} PRIVATE LGM2_VERTEX_JIT)
    endforeach()
endif()
