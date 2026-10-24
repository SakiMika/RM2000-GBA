#!/usr/bin/env python3
"""Compile RM2K sample's actual Title2.png to a GBA Mode4 240x160 title.
No XML decoder; title asset remains a host-side conversion task.
Title buttons and selection arrow are rendered at runtime by GBA.
"""
from pathlib import Path
from PIL import Image, ImageDraw
import struct
R=Path(__file__).resolve().parents[1]
A=R/'assets'
src=Image.open(R/'game'/'Title'/'Title2.png').convert('RGB')
assert src.size==(320,240), src.size
# Original artwork fits the 240x160 GBA display. No screen scroll.
im=src.resize((240,160),Image.Resampling.LANCZOS)
d=ImageDraw.Draw(im)
# Standard classic RM2K blue box; do not cover the title logo at the bottom.
d.rectangle((47,91,192,140), fill=(32,41,86), outline=(225,227,237), width=2)
d.rectangle((50,94,189,137), outline=(103,114,152), width=1)
# Labels, enabled status and cursor are drawn by title_screen() on the GBA.
# Reserve 240..242 for foreground pixels, leaving the 240 artwork colors intact.
# Palette quantization is done offline; title is copied as a flat bitmap once.
im=im.quantize(colors=240,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
pal=im.getpalette(); pal=pal+[0]*(768-len(pal))
# RGB values for runtime-rendered menu text and cursor.
# All 0..239 palette entries are used exclusively by the quantized image.
for index,rgb in {240:(248,248,255),241:(127,135,161),242:(255,248,138)}.items():
 pal[3*index:3*index+3]=list(rgb)
converted=[]
for i in range(256):
 r,g,b=pal[3*i:3*i+3]
 converted.append((r>>3)|((g>>3)<<5)|((b>>3)<<10))
(A/'title_palette.bin').write_bytes(struct.pack('<256H',*converted))
(A/'title_bitmap.bin').write_bytes(im.tobytes())
assert len((A/'title_bitmap.bin').read_bytes())==38400
print('Title packed: 240x160 indexed bitmap, 256-color GBA palette')
