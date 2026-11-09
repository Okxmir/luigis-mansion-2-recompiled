$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot

function Find-Lgm2VisualStudio {
    $finder = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    if (!(Test-Path -LiteralPath $finder)) { throw 'Install Visual Studio with the Desktop development with C++ workload.' }
    $instances = & $finder -all -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    foreach ($instance in $instances) {
        $cmake = Join-Path $instance 'Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'
        $ninja = Join-Path $instance 'Common7/IDE/CommonExtensions/Microsoft/CMake/Ninja/ninja.exe'
        if ((Test-Path -LiteralPath $cmake) -and (Test-Path -LiteralPath $ninja)) { return $instance }
    }
    throw 'Visual Studio with C++ and CMake tools was not found.'
}

function Build-Lgm2([string] $Configuration) {
    $visualStudio = Find-Lgm2VisualStudio
    $developerPrompt = Join-Path $visualStudio 'Common7/Tools/VsDevCmd.bat'
    & (Join-Path $PSScriptRoot 'native_build.cmd') $developerPrompt $visualStudio $Configuration
    if ($LASTEXITCODE -ne 0) { throw "Windows build failed ($LASTEXITCODE)." }
}
