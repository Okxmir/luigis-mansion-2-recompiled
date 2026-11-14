#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ci=OFF
if [[ "${1:-}" == --ci ]]; then
    ci=ON
    build="$root/build/linux-CI"
    python3 "$root/tools/prepare_linux.py" --dependencies-only
else
    build="$root/build/linux-Release"
    python3 "$root/tools/prepare_linux.py" "$@"
fi

cmake -S "$root" -B "$build" -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DLGM2_RUNTIME_TEST_ONLY="$ci" -DLGM2_FAST_BUILD=OFF
cmake --build "$build" --parallel "${CMAKE_BUILD_PARALLEL_LEVEL:-4}"
ctest --test-dir "$build" --output-on-failure --no-tests=error

if [[ "$ci" == OFF ]]; then
    dist="$root/dist/linux-x64"
    mkdir -p "$dist"
    cp "$build/LuigisMansion2" "$build/libdxcompiler.so" \
        "$root/extracted/LM2-EUR.cxi" "$root/extracted/shared-font.bcfnt" "$dist/"
    printf 'Run %s/LuigisMansion2\n' "$dist"
fi
