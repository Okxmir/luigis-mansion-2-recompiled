@echo off
setlocal
if "%~3"=="" exit /b 2
call "%~1" -arch=x64 -host_arch=x64 >nul
if errorlevel 1 exit /b 1
cd /d "%~dp0.."
set "CMAKEBIN=%~2\Common7\IDE\CommonExtensions\Microsoft\CMake"
set "PATH=%CMAKEBIN%\CMake\bin;%CMAKEBIN%\Ninja;%PATH%"
set "BUILDDIR=build\windows-%~3"
cmake -S . -B "%BUILDDIR%" -G Ninja "-DCMAKE_BUILD_TYPE=%~3"
if errorlevel 1 exit /b 1
cmake --build "%BUILDDIR%" --parallel 6
exit /b %errorlevel%
