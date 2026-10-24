#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build
python3 tools/prepare_sample.py
python3 tools/make_mode4.py
python3 tools/make_font.py
python3 tools/make_hardware_bg.py
python3 tools/make_title.py
CC=${CC:-clang}
LD=${LD:-ld.lld}
OBJCOPY=${OBJCOPY:-llvm-objcopy}
COMMON=(-target armv4t-none-eabi -mcpu=arm7tdmi -marm -ffreestanding -fno-builtin -fno-unwind-tables -fno-asynchronous-unwind-tables -fdata-sections -ffunction-sections)
"$CC" "${COMMON[@]}" -O2 -c src/main.c -o build/main.o
"$CC" -target armv4t-none-eabi -mcpu=arm7tdmi -marm -c src/startup.s -o build/startup.o
"$CC" -target armv4t-none-eabi -mcpu=arm7tdmi -marm -c src/assets.s -o build/assets.o
"$LD" -T linker.ld --gc-sections -Map=build/sample.map -o build/sample.elf build/startup.o build/main.o build/assets.o
"$OBJCOPY" -O binary build/sample.elf build/sample.bin
python3 tools/make_rom.py build/sample.bin build/sample.gba
