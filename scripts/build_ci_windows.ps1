$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/common.ps1"
$env:CMAKE_BUILD_PARALLEL_LEVEL = '4'
& "$PSScriptRoot/prepare.ps1" -DependenciesOnly
$vs = Find-Lgm2VisualStudio
$dev = Join-Path $vs 'Common7/Tools/VsDevCmd.bat'
& "$PSScriptRoot/native_build.cmd" $dev $vs 'CI' 'ON'
if ($LASTEXITCODE -ne 0) { throw "CI build failed ($LASTEXITCODE)" }
$ctest = Join-Path $vs 'Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/ctest.exe'
& $ctest --test-dir "$ProjectRoot/build/windows-CI" --output-on-failure --no-tests=error
if ($LASTEXITCODE -ne 0) { throw "CI tests failed ($LASTEXITCODE)" }
