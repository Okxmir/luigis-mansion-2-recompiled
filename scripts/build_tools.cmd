@echo off
setlocal
if "%~1"=="" exit /b 2
call "%~1" -arch=x64 -host_arch=x64 >nul
if errorlevel 1 exit /b 1
cd /d "%~dp0.."
if not exist build\tools mkdir build\tools
set "UP=build\upstream"
set "RUST=%UP%\rustc-1.90.0-x86_64-pc-windows-msvc\rustc\bin\rustc.exe"
set "CLOCKWORK=%UP%\clockwork-master"
set "RUSTFLAGS=--edition=2024 -C opt-level=2 -C debuginfo=0"

python tools\prepare_recompiler.py "%CLOCKWORK%\tools\recomp\src" build\tools\recomp-src
if errorlevel 1 exit /b 1
"%RUST%" %RUSTFLAGS% --crate-name recomp "build\tools\recomp-src\main.rs" -o build\tools\recomp.exe
if errorlevel 1 exit /b 1
"%RUST%" --edition=2021 -C opt-level=2 --crate-type rlib --crate-name memmap2 "%UP%\memmap2-0.9.11\src\lib.rs" -o build\tools\libmemmap2.rlib
if errorlevel 1 exit /b 1
"%RUST%" %RUSTFLAGS% --crate-name ctrx --extern memmap2=build\tools\libmemmap2.rlib "%CLOCKWORK%\tools\ctrx\src\main.rs" -o build\tools\ctrx.exe
exit /b %errorlevel%
