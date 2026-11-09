"""Apply the ARM discovery corrections verified against LM2."""

import argparse
import shutil
from pathlib import Path

from prepare_runtime import change


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("upstream", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    shutil.copytree(args.upstream, args.output, dirs_exist_ok=True)
    change(args.output / "discover.rs", [
        ("        Op::Udf | Op::Bkpt(_) => Flow::Stop,",
         """        // An ARM predicated trap only terminates the path when its condition passes.
        Op::Udf | Op::Bkpt(_) if !conditional => Flow::Stop,"""),
        ("        d.add_entry(image.text.addr, false);",
         """        d.add_entry(image.text.addr, false);
        // LM2 EUR initializes this interpolation callback from an isolated rodata pointer.
        // The first outdoor scene calls it through BLX r12 at 0x006650b4.
        if image.u32(0x008d1710) == Some(0x0084b1d4)
            && image.u32(0x0084b1d4) == Some(0xe92d0030)
        {
            d.add_entry(0x0084b1d4, false);
        }"""),
    ])


if __name__ == "__main__":
    main()
