#!/usr/bin/env python3
"""Prepends a correct, checksummed 192-byte GBA cartridge header."""
from pathlib import Path
import sys
source,dest=map(Path,sys.argv[1:3]); code=source.read_bytes()
logo=bytes.fromhex('''
24 FF AE 51 69 9A A2 21 3D 84 82 0A 84 E4 09 AD
11 24 8B 98 C0 81 7F 21 A3 52 BE 19 93 09 CE 20
10 46 4A 4A F8 27 31 EC 58 C7 E8 33 82 E3 CE BF
85 F4 DF 94 CE 4B 09 C1 94 56 8A C0 13 72 A7 FC
9F 84 4D 73 A3 CA 9A 61 58 97 A3 27 FC 03 98 76
23 1D C7 61 03 04 AE 56 BF 38 84 00 40 A7 0E FD
FF 52 FE 03 6F 95 30 F1 97 FB C0 85 60 D6 80 25
A9 63 BE 03 01 4E 38 E2 F9 A2 34 FF BB 3E 03 44
78 00 90 CB 88 11 3A 94 65 C0 7C 63 87 F0 3C AF
D6 25 E4 8B 38 0A AC 72 21 D4 F8 07
''')
assert len(logo)==156,len(logo)
hdr=bytearray(0xC0)
hdr[0:4]=(0xEA00002E).to_bytes(4,'little') # B 0x080000C0
hdr[4:0xA0]=logo
title=b'RM2K GBA'.ljust(12, b' ')  # GBA title field is exactly 12 bytes
assert len(title)==12
hdr[0xA0:0xAC]=title
hdr[0xAC:0xB0]=b'RG2K'
hdr[0xB0:0xB2]=b'HB'
hdr[0xB2]=0x96
hdr[0xBD]=(-0x19-sum(hdr[0xA0:0xBD]))&255
assert len(hdr)==0xC0, f'Invalid GBA header length: {len(hdr)} (expected 192)'
assert len(code)>=4, 'ARM program is empty'
assert (int.from_bytes(code[:4], 'little') & 0xFFFFF000)==0xE59FD000, 'Expected ARM LDR sp startup instruction'
rom=bytes(hdr)+code
assert rom[0xC0:0xC4]==code[:4], 'ROM program offset error'
rom+=b'\0'*(4-len(rom)%4 if len(rom)%4 else 0)
dest.write_bytes(rom)
assert (sum(hdr[0xA0:0xBE])+0x19)&255==0
print('ROM:',dest,len(rom),'bytes; header=192 bytes; entry opcode=%s; GBA logo/header checksum OK' % rom[0xC0:0xC4].hex())
