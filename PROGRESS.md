# Port status

## Verified results

- The tools read the European cartridge image from its original location and wrote the decrypted executable partition to `extracted/LM2-EUR.cxi`. The integrity checks and file inventory are in the local logs `logs/extraction-integrity.txt` and `logs/extraction.txt`.
- The recompiler translates ARM and Thumb to C ahead of time, and MSVC compiles the result for x64. The executable loads the `LM3DS` segments from the CXI. The latest run generated 57,971 functions.
- The original function at `0x003B4B98` passes 84 comparisons with an independent CRC implementation in both Debug and Release. The cases cover four alignments, several lengths, and three initial states. See `logs/tests.txt` and `logs/tests-debug.txt`.
- The recompiled program ran the original entry point at `0x00100000`. The first startup stall occurred while reading the hardware identity. The PTM fix resolved the loop recorded in `logs/first-sleep.txt`. Further startup analysis found a control-flow issue involving a conditional trap.
- Windows displayed the title screen, profile selection, and opening cutscene through Vulkan on an RTX 3080 Ti. See the local captures in `logs/mission-control` and `logs/vulkan-check-*.png`.
- The game wrote a 3,895-byte `profile1.sav`. Both CRCs were independently recalculated. The existing profile appeared in the menu after restart and retained the same SHA-256 through metadata migration. See `logs/resume-check-0.png` and `logs/boot-save-migrate.txt`.
- The packaged build in `dist/` loaded the font and local partition from their default locations. It displayed the Gloomy Manor selection screen and the A-1 briefing. See `logs/mission-run/mission-a1.png` and `logs/mission-final.txt`.
- A packaged build displayed the French title screen with its default settings. See `logs/titre-final-0.png` and `logs/packaged-title.txt`.
- After the interpolation routine called at the start of A-1 was recompiled, Luigi reached the garden. Forward and right Circle Pad input moved Luigi and aimed his flashlight. His position also changed on the map. See the local captures in `logs/a1-retry/`.
- The graphical test produced nonzero stereo audio samples at 32,728 Hz. The capture contains the mixer output.
- `scripts/prepare.ps1 -CodeOnly` reproduced extraction and recompilation with the pinned dependencies. Integrity checks reject an incorrect key before writing the final extracted partition. The original cartridge image matched its initial checksum.
- Each running instance locks its save directory. During testing, Windows rejected a second launch using the same directory while the first instance continued running. See `logs/save-lock-test.txt`.

## Remaining validation

Early Vulkan tests showed artifacts on the garden floor, steps, and gate. The first build defaulted to software rendering with Direct3D 11 display to avoid those artifacts. Completing A-1, saving its progress, later missions, and ScareScraper still need testing. The port uses a replacement system font.

## Rendering performance

The software renderer caches decoded ETC texels, rejects occluded fragments earlier, and reduces synchronization between rendering tasks. On the test PC, the bunker ran at about 7–9 FPS before these changes and 13–16 FPS afterward. The `YW2_FPS` counter counts new top-screen buffers over roughly five seconds of wall-clock time. See `logs/fps-cpu-before.txt` and `logs/fps-cpu-after.txt`.

During the A-1 arrival sequence, software rendering ran at about 8–10 FPS before the changes and 9–12 FPS afterward.

The updated Vulkan renderer uses 16-bit depth when the game requests it and reads native-size surfaces directly. In the garden test, the floor and gate rendered cleanly. Movement and flashlight aiming worked after the professor’s call. See the local captures in `logs/fps-gpu-vertices/`. CPU vertex calculations pass 11,778 comparisons with the reference interpreter, alongside the 84 save CRC checks.

The current executable in `dist/` defaults to Vulkan and presents the bottom screen directly while preserving RGB565 conversion. On the RTX 3080 Ti test system, it reached about 20–23 FPS in the bunker, 18–19 FPS in the garden after the introduction, and 17–18 FPS while moving through the garden. The experimental `LGM2_GPU_VERTICES=1` mode reached 25 FPS in the bunker and about 15 FPS during garden movement, so the packaged build uses x64 CPU vertex processing. The 60 FPS target remains open. See `logs/fps-vulkan-final.txt` and the local captures in `logs/fps-vulkan-final/`.
