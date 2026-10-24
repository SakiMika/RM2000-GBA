#!/usr/bin/env python3
"""Pack existing sample asset output into GBA Mode4 indexed bitmap (no runtime PNG/XML)."""
from pathlib import Path
import struct
ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'assets'
source=ASSETS/'bg.bin'
raw=source.read_bytes()
assert len(raw)==320*256*2
bg=struct.unpack('<81920H',raw)
sprites={(i,j):struct.unpack('<768H',(ASSETS/f'player_{i}_{j}.bin').read_bytes()) for i in range(4) for j in range(3)}
upper_raw=(ASSETS/'upper_raw.bin').read_bytes()
upper=struct.unpack('<%dH'%(len(upper_raw)//2),upper_raw)
colors={0} # palette 0 reserved for transparency
colors.update(bg)
for sprite in sprites.values(): colors.update(sprite)
colors.update(upper)
# Reserve palette values for dialogue and UI
UI_COLORS=[0x8000|3|(4<<5)|(8<<10), 0x8000|27|(27<<5)|(28<<10),
           0x8000|5|(6<<5)|(12<<10),0x8000|31|(31<<5)|(31<<10),
           0x8000|21|(23<<5)|(25<<10)]
colors.update(UI_COLORS)
# Keep the entire validated palette stable; append the new tree-stump
# colors *after* all old indices. Existing maps, bridges, and sprite indices
# remain byte-for-byte identical to the user-tested build.
base_palette=[0]+sorted(c for c in colors if c!=0)
visual_raw=(ASSETS/'event_visual_raw.bin').read_bytes()
visual_raw_555=struct.unpack('<%dH'%(len(visual_raw)//2),visual_raw)
extra_colors=set(visual_raw_555)-set(base_palette)
colors.update(extra_colors)
assert len(colors)<=256, f'Too many palette colors for Mode4: {len(colors)}'
# Ensure black is index 0; rest exact RGB555 colors stable.
palette=base_palette+sorted(c for c in extra_colors if c!=0)
index={v:i for i,v in enumerate(palette)}
# GBA BG palette uses bottom 15 bits; index0 reserved transparent, though background doesn't rely on transparency.
(ASSETS/'palette4.bin').write_bytes(struct.pack('<%dH'%len(palette),*[v&0x7fff for v in palette]))
(ASSETS/'bg4.bin').write_bytes(bytes(index[v] for v in bg))
for (i,j),sprite in sprites.items(): (ASSETS/f'player4_{i}_{j}.bin').write_bytes(bytes(index[v] if v else 0 for v in sprite))
(ASSETS/'upper4.bin').write_bytes(bytes(index[v] if v else 0 for v in upper))
(ASSETS/'event_visual4.bin').write_bytes(bytes(index[v] if v else 0 for v in visual_raw_555))
with open(ASSETS/'mode4_colors.h','w') as f:
 f.write('#pragma once\n')
 for name,v in zip(['UI_OUTER','UI_INNER','UI_BG','UI_TEXT','UI_HINT'],UI_COLORS):f.write(f'#define {name} {index[v]}\n')
 f.write(f'#define SAMPLE_PALETTE_COUNT {len(palette)}\n')
print(f'Prepared GBA Mode4 assets: {len(palette)} colors, bg {len(bg)} pixels, sprites 12 x 768 bytes; upper unique tiles')
