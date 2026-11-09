// PICA vertex programs are data uploaded by the game. This path runs them on Vulkan
// before the same fragment pipeline used by CPU-transformed draws.
ByteAddressBuffer Stream : register(t0, space0);

cbuffer Draw : register(b0, space1) {
    float4 Depth;       // scale, offset
    float4 Viewport;    // x scale, x shift, y scale, y shift
    uint4 VertexData;   // attributes base, attribute count, register map lo/hi
    uint4 ProgramData;  // program base, swizzle base, uniform base, entry
    uint4 UniformData;  // int uniforms base, bool uniforms, semantic map base, unused
};

struct VertexResult {
    float4 position : SV_Position;
    float2 clip : SV_ClipDistance0;
    [[vk::location(0)]] float4 color : COLOR0;
    [[vk::location(1)]] float4 tc01 : TEXCOORD0;
    [[vk::location(2)]] float4 tc2w : TEXCOORD1;
    [[vk::location(3)]] float4 quat : TEXCOORD2;
    [[vk::location(4)]] float4 view : TEXCOORD3;
    [[vk::location(5)]] float wdepth : TEXCOORD4;
};

float4 permute(float4 v, uint desc, uint shift) {
    uint p = desc >> (shift + 1);
    float4 lanes = float4(v[(p >> 6) & 3], v[(p >> 4) & 3], v[(p >> 2) & 3], v[p & 3]);
    return ((desc >> shift) & 1) != 0 ? -lanes : lanes;
}

float4 load_source(float4 registers[48], uint reg, int offset) {
    if (reg < 32) return registers[reg];
    int index = int(reg) - 32 + offset;
    if (index < 0 || index >= 96) return 1.0;
    return asfloat(Stream.Load4(ProgramData.z + uint(index) * 16));
}

float4 multiply(float4 a, float4 b) {
    precise float4 p = a * b;
    bool4 invalid = isnan(p) & !(isnan(a) | isnan(b));
    return select(invalid, 0.0.xxxx, p);
}

bool compare_value(float a, float b, uint op) {
    switch (op) {
    case 0: return a == b;
    case 1: return a != b;
    case 2: return a < b;
    case 3: return a <= b;
    case 4: return a > b;
    case 5: return a >= b;
    default: return true;
    }
}

bool condition(uint ins, bool2 cc) {
    bool x = (((ins >> 25) & 1) != 0) == cc.x;
    bool y = (((ins >> 24) & 1) != 0) == cc.y;
    switch ((ins >> 22) & 3) {
    case 0: return x || y;
    case 1: return x && y;
    case 2: return x;
    default: return y;
    }
}

struct ReturnFrame {
    uint end;
    uint next;
    uint start;
    uint iterations;
    uint increment;
};

float semantic_value(float4 registers[48], uint semantic) {
    uint from = Stream.Load(UniformData.z + semantic * 4);
    return from < 64 ? registers[32 + (from >> 2)][from & 3] : 0.0;
}

VertexResult main(uint vertex : SV_VertexID) {
    float4 r[48];
    [unroll] for (uint i = 0; i < 48; ++i) r[i] = 0.0;
    uint input = VertexData.x + vertex * VertexData.y * 16;
    [loop] for (uint attr = 0; attr < VertexData.y; ++attr) {
        uint map = attr < 8 ? VertexData.z : VertexData.w;
        r[(map >> (4 * (attr & 7))) & 15] = asfloat(Stream.Load4(input + attr * 16));
    }
    int4 address = 0;
    bool2 cc = false;
    ReturnFrame stack[16];
    uint sp = 0;
    uint pc = ProgramData.w;
    [loop] for (uint step = 0; step < 0x40000; ++step) {
        [loop] while (sp != 0) {
            ReturnFrame frame = stack[sp - 1];
            if (pc != frame.end) break;
            if (frame.iterations != 0) address.w += int(frame.increment);
            if (frame.iterations > 1) {
                stack[sp - 1].iterations--;
                pc = frame.start;
            } else {
                pc = frame.next;
                --sp;
            }
        }
        uint ins = Stream.Load(ProgramData.x + (pc & 4095) * 4);
        uint op = ins >> 26;
        if (op < 0x20 || op >= 0x2e) {
            uint3 src = 0;
            int3 relative = 0;
            uint destination;
            uint descriptor;
            if (op >= 0x30) {
                descriptor = ins & 31;
                destination = (ins >> 24) & 31;
                src.x = (ins >> 17) & 31;
                if (op >= 0x38) {
                    src.y = (ins >> 10) & 127;
                    src.z = (ins >> 5) & 31;
                    relative.y = address[(ins >> 22) & 3];
                } else {
                    src.y = (ins >> 12) & 31;
                    src.z = (ins >> 5) & 127;
                    relative.z = address[(ins >> 22) & 3];
                }
            } else {
                descriptor = ins & 127;
                destination = (ins >> 21) & 31;
                if (op >= 0x18 && op <= 0x1b) {
                    src.x = (ins >> 14) & 31;
                    src.y = (ins >> 7) & 127;
                    relative.y = address[(ins >> 19) & 3];
                } else {
                    src.x = (ins >> 12) & 127;
                    src.y = (ins >> 7) & 31;
                    relative.x = address[(ins >> 19) & 3];
                }
            }
            uint desc = Stream.Load(ProgramData.y + descriptor * 4);
            uint mask = desc & 15;
            float4 a = permute(load_source(r, src.x, relative.x), desc, 4);
            float4 b = permute(load_source(r, src.y, relative.y), desc, 13);
            precise float4 result = a;
            switch (op) {
            case 0x00: result = a + b; break;
            case 0x01:
            case 0x02:
            case 0x03:
            case 0x18: {
                float4 p = multiply(a, b);
                precise float d = (p.x + p.y) + p.z;
                if (op != 0x01) d += op == 0x02 ? p.w : b.w;
                result = d;
                break;
            }
            case 0x04:
            case 0x19: result = float4(1, multiply(a, b).y, a.z, b.w); break;
            case 0x05: result = exp2(a.x); break;
            case 0x06: result = log2(a.x); break;
            case 0x07:
                result = float4(max(a.x, 0), clamp(a.y, -127.9961, 127.9961), 0, max(a.w, 0));
                cc = bool2(a.x >= 0, a.w >= 0);
                break;
            case 0x08: result = multiply(a, b); break;
            case 0x09:
            case 0x1a: result = float4(a >= b); break;
            case 0x0a:
            case 0x1b: result = float4(a < b); break;
            case 0x0b: result = floor(a); break;
            case 0x0c: result = select(a > b, a, b); break;
            case 0x0d: result = select(a < b, a, b); break;
            case 0x0e: result = 1.0 / a.x; break;
            case 0x0f: result = 1.0 / sqrt(a.x); break;
            case 0x12:
                if ((mask & 8) != 0) address.y = int(a.x);
                if ((mask & 4) != 0) address.z = int(a.y);
                mask = 0;
                break;
            case 0x13: break;
            case 0x2e:
            case 0x2f:
                cc = bool2(compare_value(a.x, b.x, (ins >> 24) & 7), compare_value(a.y, b.y, (ins >> 21) & 7));
                mask = 0;
                break;
            default:
                if (op >= 0x30) result = multiply(a, b) + permute(load_source(r, src.z, relative.z), desc, 22);
                else mask = 0;
                break;
            }
            uint dst = destination < 16 ? destination + 32 : destination;
            if (mask == 15) r[dst] = result;
            else if (mask != 0) {
                bool4 write = (mask & uint4(8, 4, 2, 1)) != 0;
                r[dst] = select(write, result, r[dst]);
            }
            ++pc;
            continue;
        }
        if (op == 0x22) break;
        uint count = ins & 255;
        uint dst = (ins >> 10) & 4095;
        bool flag = ((UniformData.y >> ((ins >> 22) & 15)) & 1) != 0;
        ReturnFrame frame = {0, 0, 0, 0, 0};
        switch (op) {
        case 0x20:
        case 0x23:
            if (op == 0x20 || condition(ins, cc)) {
                int depth = int(sp) - 1;
                [loop] while (depth >= 0 && stack[depth].iterations == 0) --depth;
                if (depth >= 0) {
                    pc = stack[depth].next;
                    sp = uint(depth);
                    continue;
                }
            }
            break;
        case 0x24:
        case 0x25:
        case 0x26:
            if (op == 0x24 || (op == 0x25 && condition(ins, cc)) || (op == 0x26 && flag)) {
                frame.end = dst + count;
                frame.next = pc + 1;
                if (sp < 16) stack[sp++] = frame;
                pc = dst;
                continue;
            }
            break;
        case 0x27:
        case 0x28: {
            bool taken = op == 0x27 ? flag : condition(ins, cc);
            frame.end = taken ? dst : dst + count;
            frame.next = dst + count;
            if (sp < 16) stack[sp++] = frame;
            pc = taken ? pc + 1 : dst;
            continue;
        }
        case 0x29: {
            uint loop_data = Stream.Load(UniformData.x + ((ins >> 22) & 3) * 4);
            frame.end = frame.next = dst + 1;
            frame.start = pc + 1;
            frame.iterations = (loop_data & 255) + 1;
            frame.increment = (loop_data >> 16) & 255;
            address.w = int((loop_data >> 8) & 255);
            if (sp < 16) stack[sp++] = frame;
            break;
        }
        case 0x2c:
        case 0x2d:
            if (op == 0x2c ? condition(ins, cc) : flag == ((count & 1) == 0)) {
                pc = dst;
                continue;
            }
            break;
        }
        ++pc;
    }
    float4 position = float4(semantic_value(r, 0), semantic_value(r, 1), semantic_value(r, 2), semantic_value(r, 3));
    VertexResult output;
    precise float z = position.z * Depth.x + Depth.y * position.w;
    output.position = float4(Viewport.x * position.x + Viewport.y * position.w,
                             Viewport.z * position.y + Viewport.w * position.w, z, position.w);
    output.clip = float2(-position.z, position.z + position.w);
    output.color = min(abs(float4(semantic_value(r, 8), semantic_value(r, 9),
                                  semantic_value(r, 10), semantic_value(r, 11))), 1.0);
    output.tc01 = float4(semantic_value(r, 12), semantic_value(r, 13), semantic_value(r, 14), semantic_value(r, 15));
    output.tc2w = float4(semantic_value(r, 22), semantic_value(r, 23), semantic_value(r, 16), 0);
    output.quat = float4(semantic_value(r, 4), semantic_value(r, 5), semantic_value(r, 6), semantic_value(r, 7));
    output.view = float4(semantic_value(r, 18), semantic_value(r, 19), semantic_value(r, 20), 0);
    output.wdepth = z;
    return output;
}
