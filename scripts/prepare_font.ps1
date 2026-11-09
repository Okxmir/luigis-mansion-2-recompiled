. "$PSScriptRoot/common.ps1"

$ProgressPreference = 'SilentlyContinue'
$upstream = Join-Path $ProjectRoot 'build/upstream'
New-Item -ItemType Directory -Path $upstream, "$ProjectRoot/extracted" -Force | Out-Null
$commit = 'f470e0c9d341db73b8a24880295d2eab4cd81660'
$archive = Join-Path $upstream 'system-archives-pinned.zip'
if (!(Test-Path -LiteralPath $archive)) {
    Invoke-WebRequest -Uri "https://codeload.github.com/B3n30/citra_system_archives/zip/$commit" -OutFile $archive -TimeoutSec 60
}
if ((Get-FileHash -LiteralPath $archive).Hash -ne '2F2072DE4026462E786BC0E6040238A6FDE356325041CABC4D66F9432F75E3DB') {
    throw 'Shared-font generator archive SHA-256 mismatch.'
}
$wheelName = 'pypng-0.20220715.0-py3-none-any.whl'
$wheel = Join-Path $upstream $wheelName
if (!(Test-Path -LiteralPath $wheel)) {
    python -m pip download --no-cache-dir --no-deps --only-binary ':all:' --dest $upstream pypng==0.20220715.0
    if ($LASTEXITCODE -ne 0) { throw 'Could not download the PNG module.' }
}
if ((Get-FileHash -LiteralPath $wheel).Hash -ne '4A43E969B8F5AAAFB2A415536C1A8EC7E341CD6A3F957FD5B5F32A4CFEED902C') {
    throw 'PNG module SHA-256 mismatch.'
}
$source = Join-Path $upstream "citra_system_archives-$commit"
if (!(Test-Path -LiteralPath $source)) {
    Expand-Archive -LiteralPath $archive -DestinationPath $upstream -Force
}
$previousPythonPath = $env:PYTHONPATH
Push-Location -LiteralPath "$source/shared_font"
try {
    $env:PYTHONPATH = $wheel
    python create_png.py
    if ($LASTEXITCODE -ne 0) { throw 'Shared font glyph generation failed. Check that Pillow is installed.' }
    Copy-Item -Path 'reserved_unicode_chars/*.png' -Destination '.'
    python bcfnt.py -c -y -f code.bcfnt
    if ($LASTEXITCODE -ne 0) { throw 'BCFNT generation failed.' }
    Copy-Item -LiteralPath 'code.bcfnt' -Destination "$ProjectRoot/extracted/shared-font.bcfnt"
} finally {
    $env:PYTHONPATH = $previousPythonPath
    Pop-Location
}
