. "$PSScriptRoot/common.ps1"
$visualStudio = Find-Lgm2VisualStudio
$build = Join-Path $ProjectRoot 'build/windows-Release'
$dist = Join-Path $ProjectRoot 'dist'
$redist = Join-Path $visualStudio 'VC/Redist/MSVC'
$crt = Get-ChildItem -LiteralPath $redist -Directory |
    Where-Object Name -Match '^\d+\.\d+\.\d+$' |
    Sort-Object { [version]$_.Name } -Descending |
    ForEach-Object { Get-ChildItem -Path "$($_.FullName)/x64/Microsoft.VC*.CRT" -Directory } |
    Select-Object -First 1
if (!$crt) { throw 'The x64 Visual C++ runtime files were not found.' }
$paths = @(
    (Join-Path $build 'LuigisMansion2.exe'),
    (Join-Path $build 'SDL3.dll'),
    (Join-Path $ProjectRoot 'extracted/shared-font.bcfnt'),
    (Join-Path $ProjectRoot 'README.md'),
    (Join-Path $crt.FullName 'msvcp140.dll'),
    (Join-Path $crt.FullName 'vcruntime140.dll'),
    (Join-Path $crt.FullName 'vcruntime140_1.dll')
)
foreach ($file in $paths) {
    if (!(Test-Path -LiteralPath $file -PathType Leaf)) { throw "Missing file: $file" }
}
New-Item -ItemType Directory -Path "$dist/licenses" -Force | Out-Null
Copy-Item -LiteralPath $paths -Destination $dist
Copy-Item -LiteralPath "$ProjectRoot/build/upstream/clockwork-master/LICENSE" -Destination "$dist/licenses/Clockwork.txt"
Copy-Item -LiteralPath "$ProjectRoot/build/upstream/SDL3-3.4.0/LICENSE.txt" -Destination "$dist/licenses/SDL3.txt"
$fontLicense = "$ProjectRoot/build/upstream/citra_system_archives-f470e0c9d341db73b8a24880295d2eab4cd81660/license.txt"
if (Test-Path -LiteralPath $fontLicense) {
    Copy-Item -LiteralPath $fontLicense -Destination "$dist/licenses/System-Files-Generator.txt"
}
Get-FileHash -Algorithm SHA256 -LiteralPath "$dist/LuigisMansion2.exe", "$dist/SDL3.dll"
