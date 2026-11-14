"""Run the original game's native entry point with a bounded diagnostic log."""

import argparse
import os
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=10)
    parser.add_argument("--graphics", action="store_true")
    executable = parser.add_mutually_exclusive_group()
    executable.add_argument("--packaged", action="store_true")
    executable.add_argument("--executable", type=Path)
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--log", default="boot-probe.txt")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    logs = root / "logs"
    logs.mkdir(exist_ok=True)
    windows = os.name == "nt"
    name = "LuigisMansion2.exe" if windows else "LuigisMansion2"
    build_dir = "windows-Release" if windows else "linux-Release"
    if Path(args.log).name != args.log:
        parser.error("--log must be a filename")
    env = os.environ.copy()
    if args.graphics:
        env.pop("YW2_HEADLESS", None)
    else:
        env["YW2_HEADLESS"] = "1"
    env.update(
        LGM2_DATA_DIR=str(args.state_dir.resolve() if args.state_dir else root / "build" / "probe-userdata"),
        LGM2_NO_DIALOG="1",
        LGM2_TRACE_FIRST_SLEEP="1",
    )
    if args.packaged:
        directory = root / "dist" if windows else root / "dist" / "linux-x64"
        command = [str(directory / name)]
    else:
        env.setdefault("LGM2_SHARED_FONT", str(root / "extracted" / "shared-font.bcfnt"))
        binary = args.executable.resolve() if args.executable else root / "build" / build_dir / name
        command = [str(binary),
                   str(root / "extracted" / "LM2-EUR.cxi")]
    with (logs / args.log).open("wb") as output:
        try:
            run = subprocess.run(
                command,
                stdout=output,
                stderr=subprocess.STDOUT,
                env=env,
                timeout=args.seconds,
                creationflags=subprocess.CREATE_NO_WINDOW if windows else 0,
                cwd=logs,
                check=False,
            )
        except subprocess.TimeoutExpired:
            output.write(f"\nProbe ended after {args.seconds} seconds.\n".encode())
            return 124
        return run.returncode


if __name__ == "__main__":
    raise SystemExit(main())
