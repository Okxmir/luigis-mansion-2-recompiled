# Luigi’s Mansion 2 Recompiled

An experimental community port of **Luigi’s Mansion 2** for Windows x64. The project translates the European 3DS release’s ARM and Thumb code (`CTR-P-AGGP`) into native code and loads assets from a local copy of the cartridge.

**You need your own European cartridge image.** This repository provides the port’s source code and the tools to build it locally. Keep the cartridge image, extracted assets, and recompiled executable on your PC.

## Build and run

Prepare your cartridge image and build the project, then launch `dist/LuigisMansion2.exe`. Vulkan is the default renderer. The software renderer uses Direct3D 11 for display. [Build guide](BUILD.md)

Testing reached the garden in mission A-1 and verified movement, the flashlight, and loading an existing profile. The full campaign and multiplayer still need testing. The 60 FPS target remains open. [Test results](PROGRESS.md)

## Controls

| 3DS control | AZERTY keyboard |
| --- | --- |
| Circle Pad | ZQSD |
| A / B / X / Y | K / J / I / U |
| L / R | Left Shift / E |
| Start / Select | Enter / Backspace |
| Touch screen | Click the bottom screen |

Save files are stored in `dist/userdata/games/0004000000076500/save`. The program keeps earlier versions in `save-backups`.

## Local testing

Run the game from the project directory with an explicit path to the extracted partition.

```powershell
.\dist\LuigisMansion2.exe .\extracted\LM2-EUR.cxi
```

The save checksum test runs the recompiled ARM function and compares its output with an independent CRC implementation.

```powershell
.\dist\LuigisMansion2.exe --verify-crc .\extracted\LM2-EUR.cxi
```

## Contributing

Bug reports and code contributions are welcome. When reporting a gameplay issue, include the mission or screen, your Windows version, the renderer, and steps to reproduce it. Keep game data, keys, and save files private.

Generated code, executables containing that code, and extracted assets belong in the local project folder. The tools store analysis and test outputs in `extracted/`, `generated/`, `build/`, and `logs/`.

[MIT license for the port](LICENSE) · [Clockwork license](licenses/Clockwork.txt)
