"""Prepare pinned Linux dependencies and generate game code from a local cartridge."""

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "build" / "upstream"
CLOCKWORK = "3047d9e990be4ac2c84174cb570dfec569c882e9"
XBYAK = "df112862583c2d327c1d9782fd28f53aa675f11d"
FONT = "f470e0c9d341db73b8a24880295d2eab4cd81660"
CODE_HASH = "feeaa71350c2712c5402fbeefa9be4aaed0a77442df43af0c14326b2524ca2c8"


def fetch(name, url, digest):
    path = UPSTREAM / name
    candidate = path if path.exists() else path.with_suffix(path.suffix + ".partial")
    if candidate != path:
        with urllib.request.urlopen(url, timeout=90) as download, candidate.open("wb") as output:
            shutil.copyfileobj(download, output)
    with candidate.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
            raise ValueError(f"SHA-256 mismatch for {candidate}")
    if candidate != path:
        candidate.replace(path)
    return path


def github_zip(name, repo, commit, digest):
    return fetch(name, f"https://codeload.github.com/{repo}/zip/{commit}", digest)


def unpack_zip(archive, name, directory, marker):
    target = UPSTREAM / directory
    if not (target / marker).is_file():
        with zipfile.ZipFile(archive) as source:
            source.extractall(UPSTREAM)
        if name != directory:
            (UPSTREAM / name).rename(target)
    return target


def unpack_tar(archive, directory, marker, strip_root=False):
    target = UPSTREAM / directory
    if not (target / marker).is_file():
        target.mkdir(exist_ok=True)
        command = ["tar", "-xf", str(archive), "-C", str(target)]
        if strip_root:
            command += ["--strip-components=1"]
        subprocess.run(command, check=True)
    return target


def dependencies():
    UPSTREAM.mkdir(parents=True, exist_ok=True)
    clockwork = github_zip("clockwork-pinned.zip", "watchmakerers/clockwork", CLOCKWORK,
                           "7923e82994e3a06f7aa17dfdb2a6e25a608e3495227baf1a0fdbcc32dfbe1ded")
    source = unpack_zip(clockwork, f"clockwork-{CLOCKWORK}", "clockwork-master", "Cargo.lock")
    xbyak = github_zip("xbyak-pinned.zip", "herumi/xbyak", XBYAK,
                       "b0e8d74a5813d4c4d2baa550b889b7f7c2696e471dfb8de1554ce47f7e52d7f8")
    unpack_zip(xbyak, f"xbyak-{XBYAK}", f"xbyak-{XBYAK}", "xbyak/xbyak.h")
    sdl = fetch("SDL3-3.4.0.tar.gz",
                "https://github.com/libsdl-org/SDL/releases/download/release-3.4.0/SDL3-3.4.0.tar.gz",
                "082cbf5f429e0d80820f68dc2b507a94d4cc1b4e70817b119bbb8ec6a69584b8")
    unpack_tar(sdl, "SDL3-3.4.0-linux", "CMakeLists.txt", strip_root=True)
    dxc = fetch("linux_dxc_2025_07_14.x86_64.tar.gz",
                "https://github.com/microsoft/DirectXShaderCompiler/releases/download/v1.8.2505.1/"
                "linux_dxc_2025_07_14.x86_64.tar.gz",
                "f2213da1fc99dc8778c8823078e16ba97c7f80f86a1d4520ab1adf4b462bc48c")
    unpack_tar(dxc, "dxc-linux-1.8.2505.1", "lib/libdxcompiler.so")
    return source


def python(script, *args, cwd=ROOT):
    subprocess.run([sys.executable, script, *args], cwd=cwd, check=True)


def prepare_font(output):
    archive = github_zip("system-archives-pinned.zip", "B3n30/citra_system_archives", FONT,
                         "2f2072de4026462e786bc0e6040238a6fde356325041cabc4d66f9432f75e3db")
    source = unpack_zip(archive, f"citra_system_archives-{FONT}",
                        f"citra_system_archives-{FONT}", "shared_font/create_png.py")
    font = source / "shared_font"
    python("create_png.py", cwd=font)
    for glyph in (font / "reserved_unicode_chars").glob("*.png"):
        shutil.copyfile(glyph, font / glyph.name)
    python("bcfnt.py", "-c", "-y", "-f", "code.bcfnt", cwd=font)
    shutil.copy2(font / "code.bcfnt", output)


def prepare_game(args, source):
    cxi = ROOT / "extracted" / "LM2-EUR.cxi"
    if args.cartridge:
        if args.cartridge.suffix.lower() == ".cxi":
            python("tools/verify_extraction.py", args.cartridge)
            cxi.parent.mkdir(exist_ok=True)
            if args.cartridge.resolve() != cxi:
                shutil.copy2(args.cartridge, cxi)
        else:
            # Extract and verify a new input before replacing prepared data.
            cxi.parent.mkdir(exist_ok=True)
            with tempfile.TemporaryDirectory(dir=cxi.parent) as work:
                partition = Path(work) / cxi.name
                options = ["--key-file", args.key_file] if args.key_file else []
                python("tools/cartridge.py", args.cartridge, "--extract", partition, *options)
                python("tools/verify_extraction.py", partition)
                partition.replace(cxi)
    python("tools/verify_extraction.py", cxi)

    # Build against the pinned workspace lockfile, and apply LM2's recompiler patch in a local copy.
    workspace = ROOT / "build" / "linux-tools"
    workspace.mkdir(exist_ok=True)
    for name in ("Cargo.toml", "Cargo.lock"):
        shutil.copyfile(source / name, workspace / name)
    for name in ("ctrx", "recomp"):
        shutil.copytree(source / "tools" / name, workspace / "tools" / name, dirs_exist_ok=True)
    python("tools/prepare_recompiler.py", source / "tools/recomp/src", workspace / "tools/recomp/src")
    subprocess.run(["cargo", "build", "--release", "--locked", "--manifest-path", workspace / "Cargo.toml",
                    "--target-dir", workspace / "target"], check=True)
    tools = workspace / "target" / "release"
    extracted = cxi.parent / "lm2-eur"
    subprocess.run([tools / "ctrx", "--code-only", cxi, extracted], check=True)
    with (extracted / "code.bin").open("rb") as code:
        if hashlib.file_digest(code, "sha256").hexdigest() != CODE_HASH:
            raise ValueError("The game code is not the supported European build")
    subprocess.run([tools / "recomp", "emit", extracted, ROOT / "generated" / "lm2-eur"], check=True)
    prepare_font(cxi.parent / "shared-font.bcfnt")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cartridge", type=Path)
    parser.add_argument("--key-file", type=Path)
    parser.add_argument("--dependencies-only", action="store_true")
    args = parser.parse_args()
    if not args.dependencies_only and not args.cartridge and not (ROOT / "extracted/LM2-EUR.cxi").is_file():
        parser.error("Pass --cartridge with the path to your European game image")
    try:
        source = dependencies()
        if not args.dependencies_only:
            prepare_game(args, source)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    main()
