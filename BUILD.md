# Building for Windows x64

You need Windows x64, Visual Studio with the **Desktop development with C++** workload, the Windows SDK, CMake and Ninja, and Python 3.11 or later on your PATH. The preparation script downloads and verifies the build dependencies in `build/upstream`, including those for the accelerated Vulkan renderer.

Use an image of your own European `CTR-P-AGGP` cartridge that matches the supported revision. Keep your cartridge image and any key file outside the repository. Open PowerShell in the project directory and replace the example paths with your own.

## Prepare the cartridge image

For an already decrypted `.3ds` image, run these commands.

```powershell
python -m pip install Pillow
.\scripts\prepare.ps1 -Cartridge "C:\Games\LM2-EUR-decrypted.3ds" -CodeOnly
```

For an encrypted image, supply your local retail slot `0x2C` KeyX as a text file containing 32 hexadecimal digits. You can also set the `LGM2_KEYX_2C` environment variable.

```powershell
python -m pip install cryptography Pillow
.\scripts\prepare.ps1 -Cartridge "C:\Games\LM2-EUR.3ds" -KeyFile "C:\Private\slot0x2c.key" -CodeOnly
```

If you already have a compatible decrypted CXI, place it at `extracted/LM2-EUR.cxi`, install Pillow, and run `.\scripts\prepare.ps1 -CodeOnly`. The preparation script reuses the local CXI when it exists. `-CodeOnly` verifies the RomFS and keeps its files in the CXI, where the game reads them directly.

## Build, test, and package

After preparing the image, run the following commands in order.

```powershell
.\scripts\prepare_font.ps1
.\scripts\build_release.ps1
.\scripts\run_tests.ps1
.\scripts\package.ps1
```

The Release configuration prints `Vulkan vertex shader compilation enabled` when it finds the full DXC SDK. Packaging places `dxcompiler.dll` next to `dist/LuigisMansion2.exe`. Launch the game from that folder to use the same renderer options as the benchmark build. Actual frame rates vary by hardware and scene.

For a Debug build, run `scripts/build_debug.ps1`, followed by `scripts/run_tests.ps1 -Configuration Debug`. The first build compiles a large amount of generated code. `LGM2_FAST_BUILD` speeds up iteration by disabling optimization for those sources.

## Game language

Close the game and open `userdata/settings.ini` in the same folder as `LuigisMansion2.exe`. For the packaged build, this is `dist/userdata/settings.ini`. Create the folder and file if needed. If you set `LGM2_DATA_DIR`, open `settings.ini` in that directory instead.

Add or replace the `language=` line with one of the following settings, then relaunch the game.

| Setting | Language |
| --- | --- |
| `language=1` | English |
| `language=2` | French (default) |
| `language=3` | German |
| `language=4` | Italian |
| `language=5` | Spanish |

## Shared font

The game requests a BCFNT system font at startup. `prepare_font.ps1` uses Pillow to generate a compatible font locally. [System Files Generator](https://github.com/B3n30/citra_system_archives)

The loader also accepts a local, unrelocated little-endian BCFNT. Name it `shared-font.bcfnt` and place it next to the executable, or set `LGM2_SHARED_FONT` to its path. To use it with the packaging script, place a copy at `extracted/shared-font.bcfnt` before running `scripts/package.ps1`.

## Runtime settings and diagnostics

Use the boot probe to run a time-limited startup test and capture a log.

```powershell
python tools/boot_probe.py --seconds 15 --log boot-probe.txt
python tools/boot_probe.py --graphics --seconds 15 --log boot-graphics.txt
```

The program looks for `LM2-EUR.cxi` next to the executable, then in `../extracted`. You can also pass an explicit path as a command-line argument. The program verifies the game code version before launching the recompiled code. It stores user data next to the executable by default. Use `LGM2_DATA_DIR` to select another directory. The boot probe isolates its files in `build/probe-userdata`.

Vulkan is the default renderer. Set `gpu_renderer=0` in `dist/userdata/settings.ini` to select software rendering with Direct3D 11 display.

The preparation script verifies and installs the pinned Xbyak headers for the x64 vertex shader compiler. Supported vertex programs use native SSE4.1 instructions. The interpreter handles other programs and CPUs. Set `LGM2_INTERPRET_VERTEX=1` for interpreter-only comparisons.

The preparation script installs the Windows x64 release of DXC 1.8.2505.1 by default. Its compiler DLL builds Vulkan vertex shaders in the background from the shader programs uploaded by the local game. Pending or unsupported programs run on the CPU. Pass `-WithGpuShaders:$false` to skip downloading DXC, or set `LGM2_CPU_VERTEX=1` to use CPU vertex processing with Vulkan at runtime. To use another SPIR-V-capable DXC installation, pass its executable path to CMake with `-DLGM2_DXC=...`. [Microsoft DXC 1.8.2505.1](https://github.com/microsoft/DirectXShaderCompiler/releases/tag/v1.8.2505.1)

Vulkan reads supported interleaved vertex buffers directly. Set `LGM2_UNPACK_VERTEX_INPUTS=1` to compare with the path that unpacks those attributes on the CPU.
