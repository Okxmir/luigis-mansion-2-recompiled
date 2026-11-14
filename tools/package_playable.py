"""Create a versioned playable RAR from the local release build."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from ci_version import parse

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
UPSTREAM = ROOT / "build" / "upstream"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rar", default="rar", help="RAR command or path to the RAR executable")
    args = parser.parse_args()
    rar = shutil.which(args.rar)
    if not rar:
        parser.error("RAR was not found. Provide its path with --rar.")
    rar = str(Path(rar).resolve())

    if sys.platform == "win32":
        platform = "Windows"
        source = DIST
        build = ROOT / "build" / "windows-Release"
        cartridge = ROOT / "extracted" / "LM2-EUR.cxi"
        launcher = "LuigisMansion2.exe"
        runtime = ("SDL3.dll", "dxcompiler.dll", "msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll")
        sdl = "SDL3-3.4.0"
        launch = f"Open {launcher} from the extracted folder."
    elif sys.platform == "linux":
        platform = "Linux"
        source = DIST / "linux-x64"
        build = ROOT / "build" / "linux-Release"
        cartridge = source / "LM2-EUR.cxi"
        launcher = "LuigisMansion2"
        runtime = ("libdxcompiler.so",)
        sdl = "SDL3-3.4.0-linux"
        launch = (
            f"Run ./{launcher} from the extracted folder on Ubuntu 24.04 x64 or a compatible system.\n"
            f"For software rendering, run LGM2_CPU_PICA=1 ./{launcher}."
        )
    else:
        parser.error("Playable packages are available for Windows and Linux.")

    version, _ = parse((ROOT / "VERSION").read_text(encoding="utf-8"))
    filename = f"Luigis-Mansion-2-{platform}-x64-v{version}.rar"
    output = DIST / "releases"
    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="package-", dir=output) as temporary:
        staging = Path(temporary) / "game"
        staging.mkdir()
        for name in (launcher, "shared-font.bcfnt", *runtime):
            shutil.copy2(source / name, staging / name)
        shutil.copyfile(cartridge, staging / cartridge.name)
        if platform == "Linux":
            (staging / launcher).chmod(0o755)

        notices = staging / "licenses"
        notices.mkdir()
        for name, path in {
            "Port.txt": ROOT / "LICENSE",
            "Clockwork.txt": ROOT / "licenses" / "Clockwork.txt",
            "Dear-ImGui.txt": UPSTREAM / "clockwork-master/runtime/third_party/imgui/LICENSE.txt",
            "SDL3.txt": UPSTREAM / sdl / "LICENSE.txt",
            "Xbyak.txt": UPSTREAM / "xbyak-df112862583c2d327c1d9782fd28f53aa675f11d/COPYRIGHT",
            "System-Files-Generator.txt": UPSTREAM / "citra_system_archives-f470e0c9d341db73b8a24880295d2eab4cd81660/license.txt",
        }.items():
            shutil.copyfile(path, notices / name)
        shutil.copytree(build / "dxc-licenses", notices / "DXC")
        (staging / "PLAY.txt").write_text(
            f"Luigi's Mansion 2 Recompiled {version} ({platform} x64)\n\n"
            f"Extract all files to a writable folder.\n{launch}\n\n"
            "Press F4 to change the controls. Saves are created in userdata.\n",
            encoding="utf-8",
        )

        archive = Path(temporary) / filename
        subprocess.run([rar, "a", "-cfg-", "-ma5", "-m3", "-mt4", "-idq", "-r", str(archive), "*"],
                       cwd=staging, check=True)
        subprocess.run([rar, "t", "-cfg-", "-idq", str(archive)], check=True)
        os.replace(archive, output / filename)
    print(output / filename)


if __name__ == "__main__":
    main()
