"""Verify the ExeFS file hashes and all three levels of the RomFS IVFC tree."""

import argparse
import hashlib
import mmap
import struct
from pathlib import Path

from cartridge import read_cartridge, read_partition, u32


def verify_exefs(image, start, size):
    entries = 0
    for i in range(10):
        at = 16 * i
        name, offset, length = struct.unpack_from("<8sII", image, start + at)
        if not name[0]:
            continue
        if offset + length > size - 512:
            raise ValueError(f"Invalid ExeFS range for {name!r}")
        digest_at = start + 512 - (i + 1) * 32
        data_at = start + 512 + offset
        actual = hashlib.sha256(image[data_at:data_at + length]).digest()
        if actual != image[digest_at:digest_at + 32]:
            raise ValueError(f"ExeFS hash mismatch for {name!r}")
        entries += 1
    return entries


def verify_romfs(image, start, size):
    def align(value, block):
        return (value + block - 1) & -block

    if image[start:start + 4] != b"IVFC" or u32(image, start + 4) != 0x10000:
        raise ValueError("Unsupported RomFS IVFC header")
    master_size = u32(image, start + 8)
    levels = [struct.unpack_from("<QQI", image, start + i) for i in (0x0C, 0x24, 0x3C)]
    if any(not 9 <= level[2] <= 20 for level in levels):
        raise ValueError("Unsupported IVFC block size")
    sizes = [level[1] for level in levels]
    blocks = [1 << level[2] for level in levels]
    level3 = align(0x60 + master_size, blocks[2])
    level1 = align(level3 + sizes[2], blocks[0])
    level2 = align(level1 + sizes[0], blocks[1])
    offsets = [level1, level2, level3]
    verified = 0
    for level, (offset, length, block) in enumerate(zip(offsets, sizes, blocks, strict=True)):
        parent, parent_length = (0x60, master_size) if level == 0 else (offsets[level - 1], sizes[level - 1])
        padded = align(length, block)
        count = padded // block
        if not length or offset + padded > size or count * 32 != parent_length:
            raise ValueError(f"Invalid IVFC level {level + 1} extent")
        for i in range(count):
            at = start + offset + i * block
            digest_at = start + parent + i * 32
            if hashlib.sha256(image[at:at + block]).digest() != image[digest_at:digest_at + 32]:
                raise ValueError(f"RomFS IVFC level {level + 1}, block {i} hash mismatch")
        verified += count
    return verified


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cxi", type=Path)
    args = parser.parse_args()
    try:
        with args.cxi.open("rb") as stream:
            size = stream.seek(0, 2)
            _, partitions = read_cartridge(stream, size)
            base, length, _ = partitions[0]
            header, _, regions = read_partition(stream, base, length, 0)
            if not header[0x18F] & 4:
                raise ValueError("Expected a decrypted NCCH")
            with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as image:
                for name in ("ExHeader", "ExeFS", "RomFS"):
                    offset, _, length, digest_at, _ = regions[name]
                    actual = hashlib.sha256(image[base + offset:base + offset + length]).digest()
                    if not length or actual != header[digest_at:digest_at + 32]:
                        raise ValueError(f"{name} NCCH digest mismatch")
                exe, exe_size, *_ = regions["ExeFS"]
                rom, rom_size, *_ = regions["RomFS"]
                print(f"ExeFS: {verify_exefs(image, base + exe, exe_size)} file hashes verified")
                print(f"RomFS: {verify_romfs(image, base + rom, rom_size)} IVFC block hashes verified")
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    main()
