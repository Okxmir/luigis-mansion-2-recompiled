"""Compile the optional Vulkan shaders and embed them in the executable."""

import argparse
import subprocess
import tempfile
from pathlib import Path

def compile_shader(compiler, source, shader, profile):
    subprocess.run(
        [str(compiler), "-spirv", "-fspv-target-env=vulkan1.0", "-T", profile,
         "-E", "main", "-HV", "2021", "-Ges", "-Fo", str(shader), str(source)],
        check=True,
    )
    return shader.read_bytes()


def byte_array(name, data):
    rows = ["    " + ", ".join(f"0x{byte:02x}" for byte in data[i:i + 16]) + ","
            for i in range(0, len(data), 16)]
    return f"alignas(4) static constexpr unsigned char {name}[] = {{\n" + "\n".join(rows) + "\n};\n"


def specialization_template(source):
    prefix = source[:source.index("struct ReturnFrame")]
    prefix = prefix.replace("ByteAddressBuffer Stream", "StructuredBuffer<uint4> Stream")
    prefix = prefix.replace("asfloat(Stream.Load4(ProgramData.z + uint(index) * 16))",
                            "asfloat(Stream[(ProgramData.z >> 4) + uint(index)])")
    suffix = source[source.index("    float4 position ="):]
    return (f'inline constexpr char LM2_VERTEX_PREFIX[] = R"LM2({prefix})LM2";\n'
            f'inline constexpr char LM2_VERTEX_SUFFIX[] = R"LM2({suffix})LM2";\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("compiler", type=Path)
    parser.add_argument("vertex", type=Path)
    parser.add_argument("lcd", type=Path)
    parser.add_argument("header", type=Path)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(dir=args.header.parent) as directory:
        shader = Path(directory) / "shader.spv"
        vertex = compile_shader(args.compiler, args.vertex, shader, "vs_6_0")
        lcd = compile_shader(args.compiler, args.lcd, shader, "ps_6_0")
        args.header.write_text(byte_array("LM2_GPU_VERTEX", vertex) + byte_array("LM2_GPU_LCD", lcd)
                               + specialization_template(args.vertex.read_text(encoding="ascii")), encoding="ascii")


if __name__ == "__main__":
    main()
