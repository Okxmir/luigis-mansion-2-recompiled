# Technical research

## Cartridge image

| Field | Observation |
| --- | --- |
| Container | 1,073,741,824-byte NCSD image |
| SHA-256 | `EB4E7193904F704D1984F9F6DFDB14D32629DADA12EB43B8A4E3DE29FF8F87ED` |
| Identification | `CTR-P-AGGP`, title ID `0004000000076500`, ExHeader title `LM3DS` |
| Region | SMDH region mask `0xC`, European product code |
| Revision | ExHeader remaster field 0, NCCH format version 2 |
| Partitions | 0 application, 1 manual, 2 local distribution, 7 system update |
| SDK | `CTR_SDK-4_2_3_200_none`, firmware `02_35_00`, NEX `3_1_0` |

Nintendo’s manual confirms the European product code. The NCCH version describes the container format. [Official electronic manual](https://www.nintendo.com/eu/media/downloads/games_8/emanuals/nintendo_3ds_2/luigi_s_mansion_1/ElectronicManual_Nintendo3DS_LuigisMansion2_ES.pdf)

The primary partition starts at `0x4000` and spans 850,268,160 bytes. It uses the original NCCH v2 AES-CTR scheme with retail slot `0x2C`, without a secondary method or seed. The converter opens the cartridge image read-only and writes a separate CXI. The key is supplied locally. Verification covered all three NCCH hashes, all four ExeFS files, and all 206,276 IVFC blocks. RSA signatures and the contents of partitions 1 and 2 require separate verification. Partition 7 was temporarily decrypted in memory to verify its RomFS header hash and look for the Western system font. Its 60-file inventory showed that title `0004009b00010202` was absent. [Project CTR implementation](https://github.com/3DSGuy/Project_CTR/tree/master/ctrtool) · [NCCH v2 parameters](https://github.com/aszuraz/3DS-Decrypt/blob/main/decrypt_3ds.py)

The 4,908,592-byte `.code` file uses reverse LZSS compression. After decompression, `code.bin` is 8,716,288 bytes with SHA-256 `FEEAA71350C2712C5402FBEEFA9BE4AAED0A77442DF43AF0C14326B2524CA2C8`.

| Segment | Address | Size |
| --- | --- | --- |
| .text | `0x00100000` | `0x799BE8` |
| .rodata | `0x0089A000` | `0x05EED0` |
| .data | `0x008F9000` | `0x056108` |
| .bss | `0x0094F108` | `0x062AFC` |

The RomFS contains 1,878 files, including 755 pairs of `.dict` and `.data` files. The dictionaries all start with the four bytes `58 24 F3 A9`, and several `.data` streams start with a zlib header. The 338 audio banks start with `BKHD`, and `art/wwiseaudio/streamedfiles.pck` starts with `AKPK`. These signatures and the directory name point to a Wwise audio pipeline. The inventory found zero CRO, CRS, or CRR files. Animation, scene, and archive handling still need validation. [LM2L research on asset formats](https://github.com/hadashisora/LM2L)

## Recompilation and native services

- The ARM11 MPCore implements ARMv6K. Recompilation must track ARM and Thumb mode switches, condition flags, VFP registers, and little-endian memory accesses. Original addresses remain 32-bit offsets. The runtime reserves the corresponding virtual address space and commits memory as needed. [ARM11 MPCore manual](https://documentation-service.arm.com/static/5e8e1e0388295d1e18d368b2)
- The port uses Clockwork’s ARM and Thumb to C emitter at revision `3047d9e990be4ac2c84174cb570dfec569c882e9`. MSVC compiles the generated C for x64. Indirect calls look up their targets in the compiled function table and report missing entries. The project uses Clockwork’s Windows services and SDL3 presentation in an executable dedicated to LM2. Game-specific entry points, system calls, and protocols need separate validation. The pinned revision uses the MIT license. [Clockwork and its license](https://github.com/watchmakerers/clockwork) · [Clockwork architecture](https://github.com/watchmakerers/clockwork/blob/master/docs/ARCHITECTURE.md)
- LLVM IR could express ARM operations in SSA form and use the x64 backend. That approach would still require translating ARM and Thumb modes, flags, and control flow. The C emitter lets the project verify these details with an established toolchain. [LLVM IR reference](https://llvm.org/docs/LangRef.html)
- Capstone 5.0.9 was used to cross-check the startup disassembly. Other analysis and lifting tools include Ghidra and its p-code, RetDec, and Binary Ninja IL. LIEF can inspect containers such as ELF and PE. The extracted file here is a flat image, and its ExHeader supplies the memory map. These tools serve research and analysis. [Capstone](https://github.com/capstone-engine/capstone) · [Ghidra p-code](https://ghidra.re/ghidra_docs/languages/html/pcoderef.html) · [RetDec](https://github.com/avast/retdec) · [Binary Ninja IL](https://docs.binary.ninja/dev/bnil-overview.html) · [LIEF](https://lief-project.github.io/LIEF/)
- TriAevum for Ocarina of Time 3D and MM3D-PC demonstrate ahead-of-time recompilation and Vulkan on other titles. TriAevum uses GPL-3.0 and includes a third-party module with its own licensing terms. `fearkov/3dsrecomp` integrates with Zakuro and falls back to its interpreter. The Luigi’s Mansion GameCube work targets a different architecture. These projects served as research references. [TriAevum](https://github.com/coccofresco/TriAevum) · [MM3D-PC](https://github.com/Volpe34/MM3D-PC) · [3dsrecomp](https://github.com/fearkov/3dsrecomp) · [Luigi’s Mansion GameCube](https://github.com/ThePlayerRolo/lm-decomp)
- LM2_SaveEditor identifies the European save checksum function at `0x003B4B98`. Local disassembly shows a 61-instruction routine at that address. The native test uses an independent CRC implementation with the reflected polynomial `0xEDB88320`. LM2_SaveEditor and LM2L served as research references. [LM2 save analysis](https://github.com/TollyH/LM2_SaveEditor#crc-checksums) · [LM2L](https://github.com/hadashisora/LM2L)

## Startup and first mission fixes

At `0x0010B08C`, the original game waits for bit 0 at `0x1FF81086` before reading the hardware identity. The runtime now sets that bit after writing the retail console identity. [Configuration memory map](https://3dbrew.org/wiki/Configuration_Memory#Shared_Memory_Page_For_ARM11_Processes)

At `0x005277D4`, the ARM word `0xB1200A76` uses the LT condition. Clockwork’s analyzer treated every instruction of this type as an unconditional terminator. The fix preserves fall-through when the condition fails. When the condition holds, the generated code still reports the trap.

During startup, the game calls `dlp:SRVR IsChild`. The local implementation handles that query and reports an idle Download Play state. [Download Play protocol](https://www.3dbrew.org/wiki/DLP_Services)

The game then requests `APT:GetSharedFont`. The runtime loads a local BCFNT, relocates its pointers, and exposes the block in linear memory so the GPU can access the glyph atlases. A GPLv2 generator produces the compatible font as a separate build tool. [Font block format in libctru](https://github.com/devkitPro/libctru/blob/master/libctru/include/3ds/font.h) · [Generator and license](https://github.com/B3n30/citra_system_archives/tree/f470e0c9d341db73b8a24880295d2eab4cd81660)

LM2 transfers the top-screen image through 256 × 416 and 128 × 416 intermediate buffers. The Vulkan shortcut assumed an RGB transfer to a linear buffer went straight to the display, so subsequent `TextureCopy` commands read stale game memory. The fix restricts the shortcut to LCD dimensions and routes intermediate transfers through game memory.

The game requested a `0x40000`-byte save archive with zero directories, three files, and duplication enabled. Returning default metadata triggered a reformat. The runtime now preserves the requested format, imports metadata for existing local profiles, and backs up data before writing or reformatting. [FormatSaveData](https://www.3dbrew.org/wiki/FS%3AFormatSaveData) · [GetFormatInfo](https://www.3dbrew.org/wiki/FS%3AGetFormatInfo)

When Luigi arrived at the manor in A-1, `BLX r12` at `0x006650B4` called a VFP interpolation routine missing from the compiled function table. The constructor writes a pointer to `0x008D1710` into a BSS table. That address holds the ARM entry point `0x0084B1D4`, which the recompiler now treats as a verified entry. The other two targets in the table were already compiled.
