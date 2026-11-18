#!/usr/bin/env bash
# Builds a simulation-only copy of the firmware (blinky.c with -DSIM_BUILD)
# into <app>/build_sim/peripheral_tests_sim.elf. The normal Vitis build (<app>/build/)
# is not touched.
# Copy this script into the Vitis application component folder (next to src/ and build/),
# with the platform component named "platform" one level up as Vitis lays it out, then run
# it from anywhere. See the board README, section 5.2, "Full-system RTL simulation".
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
VITIS=/workspace/01_software/xilinx/2026.1/Vitis
BSP="$HERE/../platform/export/platform/sw/standalone_microblaze_riscv_0"
CMAKE="$VITIS/tps/lnx64/cmake-4.0.1/bin/cmake"

export PATH="$VITIS/gnu/riscv/lin/bin:$PATH"

# Same configuration Vitis uses for the normal build, plus -DSIM_BUILD
"$CMAKE" -S "$HERE/src" -B "$HERE/build_sim" -G Ninja \
    -DCMAKE_MAKE_PROGRAM="$VITIS/bin/ninja" \
    -DCMAKE_TOOLCHAIN_FILE="$BSP/microblaze_riscv_toolchain.cmake" \
    -DCMAKE_SPECS_FILE="$BSP/Xilinx.spec" \
    -DCMAKE_INCLUDE_PATH="$BSP/include" \
    -DCMAKE_LIBRARY_PATH="$BSP/lib" \
    -DCMAKE_MODULE_PATH="$BSP" \
    -DAPPLICATION_SPECIFIC_FLAGS="-DSIM_BUILD" \
    -DYOCTO=OFF
"$CMAKE" --build "$HERE/build_sim"

cp "$HERE/build_sim/peripheral_tests.elf" "$HERE/build_sim/peripheral_tests_sim.elf"
echo "Simulation ELF: $HERE/build_sim/peripheral_tests_sim.elf"
