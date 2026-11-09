param(
    [string] $Cartridge,
    [string] $KeyFile,
    [switch] $CodeOnly,
    [switch] $WithGpuShaders = $true
)
. "$PSScriptRoot/common.ps1"

if ($Cartridge) { $Cartridge = (Resolve-Path -LiteralPath $Cartridge).Path }
if ($KeyFile) { $KeyFile = (Resolve-Path -LiteralPath $KeyFile).Path }
Push-Location -LiteralPath $ProjectRoot
try {
    $ProgressPreference = 'SilentlyContinue'
    $upstream = Join-Path $ProjectRoot 'build/upstream'
    New-Item -ItemType Directory -Path $upstream, 'logs' -Force | Out-Null

    function Get-VerifiedArchive([string] $Name, [string] $Url, [string] $Sha256) {
        $path = Join-Path $upstream $Name
        if (!(Test-Path -LiteralPath $path)) {
            $partial = "$path.partial"
            Invoke-WebRequest -Uri $Url -OutFile $partial -TimeoutSec 240
            if ((Get-FileHash -Algorithm SHA256 -LiteralPath $partial).Hash -ne $Sha256) {
                throw "SHA-256 mismatch for $Name"
            }
            Move-Item -LiteralPath $partial -Destination $path
        }
        if ((Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash -ne $Sha256) {
            throw "SHA-256 mismatch for $Name"
        }
        $path
    }

    $commit = '3047d9e990be4ac2c84174cb570dfec569c882e9'
    $clockwork = Get-VerifiedArchive 'clockwork-pinned.zip' `
        "https://codeload.github.com/watchmakerers/clockwork/zip/$commit" `
        '7923E82994E3A06F7AA17DFDB2A6E25A608E3495227BAF1A0FDBCC32DFBE1DED'
    $sdl = Get-VerifiedArchive 'SDL3-devel-3.4.0-VC.zip' `
        'https://github.com/libsdl-org/SDL/releases/download/release-3.4.0/SDL3-devel-3.4.0-VC.zip' `
        '4489BA0070B8CE047B8717E4B71FA7E35AC71362E7A6BB2A90A7A27F624B3D5D'
    $memmap = Get-VerifiedArchive 'memmap2-0.9.11.crate' `
        'https://static.crates.io/crates/memmap2/memmap2-0.9.11.crate' `
        'D1219ED1B7F229EE7104D281DD01D6802FE28BB6E95D292942C4DAACDEB798C0'
    $xbyakCommit = 'df112862583c2d327c1d9782fd28f53aa675f11d'
    $xbyak = Get-VerifiedArchive 'xbyak-pinned.zip' `
        "https://codeload.github.com/herumi/xbyak/zip/$xbyakCommit" `
        'B0E8D74A5813D4C4D2BAA550B889B7F7C2696E471DFB8DE1554CE47F7E52D7F8'
    $rustVersion = '1.90.0-x86_64-pc-windows-msvc'
    $rustc = Get-VerifiedArchive "rustc-$rustVersion.tar.xz" `
        "https://static.rust-lang.org/dist/rustc-$rustVersion.tar.xz" `
        'A18B3912905F154C34A7572954DDA9E9849AC6411A1E02FA390BF742F918FBCB'
    $rustStd = Get-VerifiedArchive "rust-std-$rustVersion.tar.xz" `
        "https://static.rust-lang.org/dist/rust-std-$rustVersion.tar.xz" `
        '3B8C22F81C93C7E914369433430792BD6C06403806AE25B0B95F3CFC540A8B48'

    if (!(Test-Path -LiteralPath "$upstream/clockwork-master")) {
        Expand-Archive -LiteralPath $clockwork -DestinationPath $upstream -Force
        Copy-Item -LiteralPath "$upstream/clockwork-$commit" -Destination "$upstream/clockwork-master" -Recurse
    }
    if (!(Test-Path -LiteralPath "$upstream/SDL3-3.4.0/cmake/SDL3Config.cmake")) {
        Expand-Archive -LiteralPath $sdl -DestinationPath $upstream -Force
    }
    if (!(Test-Path -LiteralPath "$upstream/xbyak-$xbyakCommit/xbyak/xbyak.h")) {
        Expand-Archive -LiteralPath $xbyak -DestinationPath $upstream -Force
    }
    if ($WithGpuShaders) {
        $dxc = Get-VerifiedArchive 'dxc_2025_07_14.zip' `
            'https://github.com/microsoft/DirectXShaderCompiler/releases/download/v1.8.2505.1/dxc_2025_07_14.zip' `
            '9AD895A6B039E3A8F8C22A1009F866800B840A74B50DB9218D13319E215EA8A4'
        $dxcDir = Join-Path $upstream 'dxc-1.8.2505.1'
        if (!(Test-Path -LiteralPath "$dxcDir/bin/x64/dxc.exe") -or
            !(Test-Path -LiteralPath "$dxcDir/bin/x64/dxcompiler.dll") -or
            !(Test-Path -LiteralPath "$dxcDir/inc/dxcapi.h")) {
            Expand-Archive -LiteralPath $dxc -DestinationPath $dxcDir -Force
        }
    }
    foreach ($archive in @($memmap, $rustc, $rustStd)) {
        tar.exe -xf $archive -C $upstream
        if ($LASTEXITCODE -ne 0) { throw "Could not unpack $archive" }
    }
    $compiler = Join-Path $upstream "rustc-$rustVersion/rustc"
    $standardLib = Join-Path $upstream "rust-std-$rustVersion/rust-std-x86_64-pc-windows-msvc/lib/rustlib/x86_64-pc-windows-msvc/lib"
    $targetLib = Join-Path $compiler 'lib/rustlib/x86_64-pc-windows-msvc/lib'
    New-Item -ItemType Directory -Path $targetLib -Force | Out-Null
    Copy-Item -Path "$standardLib/*" -Destination $targetLib -Recurse -Force

    $vs = Find-Lgm2VisualStudio
    & scripts/build_tools.cmd (Join-Path $vs 'Common7/Tools/VsDevCmd.bat')
    if ($LASTEXITCODE -ne 0) { throw 'Could not build the extraction and recompilation tools.' }

    $cxi = 'extracted/LM2-EUR.cxi'
    if (!(Test-Path -LiteralPath $cxi)) {
        $options = @('--extract', $cxi)
        if ($Cartridge) { $options += $Cartridge }
        if ($KeyFile) { $options += @('--key-file', $KeyFile) }
        python tools/cartridge.py @options
        if ($LASTEXITCODE -ne 0) { throw 'The original game partition could not be extracted.' }
    }
    python tools/verify_extraction.py $cxi
    if ($LASTEXITCODE -ne 0) { throw 'The extracted game partition did not pass its integrity check.' }
    $options = @($cxi, 'extracted/lm2-eur')
    if ($CodeOnly) { $options = @('--code-only') + $options }
    & build/tools/ctrx.exe @options | Tee-Object -FilePath logs/extraction.txt
    if ($LASTEXITCODE -ne 0) { throw 'Could not unpack ExeFS and RomFS.' }
    $expected = 'FEEAA71350C2712C5402FBEEFA9BE4AAED0A77442DF43AF0C14326B2524CA2C8'
    if ((Get-FileHash -LiteralPath 'extracted/lm2-eur/code.bin' -Algorithm SHA256).Hash -ne $expected) {
        throw 'The game code is not the supported European build.'
    }
    & build/tools/recomp.exe emit extracted/lm2-eur generated/lm2-eur | Tee-Object -FilePath logs/recompile.txt
    if ($LASTEXITCODE -ne 0) { throw 'Native code generation failed.' }
} finally {
    Pop-Location
}
