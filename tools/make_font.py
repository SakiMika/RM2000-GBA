#!/usr/bin/env python3
"""Convert supplied 8x16 mono BMP font directly into GBA assets.

The supplied vertical strip has 228 consecutive 8x16 glyphs:
  !..~ (94), then 134 Vietnamese glyphs listed in the supplied header.
There is intentionally NO space glyph: U+0020 is handled as a blank advance.
All unicode mappings and widths originate in the supplied header.
"""
from pathlib import Path
from PIL import Image
import re,struct
ROOT=Path(__file__).resolve().parents[1]
FS=ROOT/'font_source'
A=ROOT/'assets'
source=(FS/'common_variable_8x16_sprite_font.h').read_text(encoding='utf-8')
extra_section=source.split('variable_8x16_sprite_font_utf8_characters[] = {',1)[1].split('};',1)[0]
extra=re.findall(r'"([^"\n]+)"',extra_section)
width_section=source.split('variable_8x16_sprite_font_character_widths[] = {',1)[1].split('};',1)[0]
width_section=re.sub(r'//[^\n]*','',width_section)
widths=[int(s) for s in re.findall(r'\b\d+\b',width_section)]
im=Image.open(FS/'common_variable_8x16_font.bmp').convert('P')
assert im.size==(8,3648),im.size
assert len(extra)==134,len(extra)
assert len(widths)==229,len(widths) # first entry is width for missing space glyph
assert all(len(s)==1 for s in extra)
assert 94+len(extra)==im.height//16
# 16 bytes / glyph, MSB is leftmost pixel, 1 is ink.
data=bytearray()
for index in range(228):
    for y in range(16):
        bits=0
        for x in range(8):
            if im.getpixel((x,index*16+y))!=0:bits|=0x80>>x
        data.append(bits)
assert len(data)==228*16
(A/'rm2k_font_mono.bin').write_bytes(data)
# Rust/Butano are not linked at runtime. This header is pure freestanding C.
points=','.join(str(ord(s))+'u' for s in extra)
w=','.join(str(v) for v in widths)
(A/'rm2k_font_meta.h').write_text(
  '#pragma once\n#include <stdint.h>\n'
  '#define RM2K_FONT_GLYPH_COUNT 228\n'
  '#define RM2K_FONT_EXTRA_COUNT 134\n'
  'static const uint16_t rm2k_font_extra[134] = {'+points+'};\n'
  'static const uint8_t rm2k_font_widths[229] = {'+w+'};\n',encoding='utf-8')
print('Font: 228 glyphs (94 ASCII, 134 Vietnamese); 8x16; 229 width entries; space=synthetic')
