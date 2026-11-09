// The PICA's rows are rotated relative to the LCD. Preserve the RGB565
// quantization when presenting the bottom screen without a CPU readback.
[[vk::combinedImageSampler]] Texture2D<float4> Source : register(t0, space2);
[[vk::combinedImageSampler]] SamplerState Filter : register(s0, space2);

cbuffer Blit : register(b0, space3) {
    float4 Size;
    int4 Mode;
};

float4 main(float4 position : SV_Position) : SV_Target0 {
    int x = int(Size.y) - 1 - int(position.y);
    int y = Mode.x != 0 ? int(Size.x) - 1 - int(position.x) : int(position.x);
    float2 block = float2(1 << Mode.y, 1 << Mode.z);
    float2 texel = float2(x, y) * block + block * 0.5;
    float3 color = Source.SampleLevel(Filter, texel / Size.zw, 0).rgb;
    if (Mode.w == 2) {
        uint3 rgb = uint3(color * 255.0 + 0.5);
        uint r = rgb.r >> 3, g = rgb.g >> 2, b = rgb.b >> 3;
        color = float3((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)) / 255.0;
    }
    return float4(color, 1);
}
