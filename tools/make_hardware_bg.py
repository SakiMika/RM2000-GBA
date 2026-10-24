#!/usr/bin/env python3
"""Compile the actual LCF-derived sample image to GBA hardware tile BG + OAM.

No XML or on-device LCF parser. This stage follows prepare_sample.py and
make_mode4.py, and it retains original map/event/collision data.
"""
from pathlib import Path
import struct
ROOT = Path(__file__).resolve().parents[1]
A = ROOT / 'assets'
W, H = 320, 256
bg = bytearray((A/'bg4.bin').read_bytes())
assert len(bg) == W * H
upper = (A/'upper4.bin').read_bytes()
eventgfx = (A/'event_visual4.bin').read_bytes()
assert len(upper)%256 == 0 and len(eventgfx)%256 == 0

def parse_entries(path, expr_marker):
    import re
    s=path.read_text()
    return [tuple(map(int, x)) for x in re.findall(expr_marker, s)]

uppers = parse_entries(A/'upper_layout.h', r'\{(\d+),(\d+),(\d+),(\d+)\}')
events = parse_entries(A/'event_visual_layout.h', r'\{(\d+),(\d+),(\d+),(\d+)\}')
base=bytearray(bg)
over=bytearray(W*H)

def place(tile, xx, yy, above):
    target=over if above else base
    for y in range(16):
        for x in range(16):
            px=xx*16+x; py=yy*16+y
            if 0<=px<W and 0<=py<H:
                c=tile[y*16+x]
                if c: target[py*W+px]=c

for x,y,idx,above in uppers:
    assert idx < len(upper)//256
    place(upper[idx*256:(idx+1)*256],x,y,above)
for eid,x,y,idx in events:
    assert idx < len(eventgfx)//256
    place(eventgfx[idx*256:(idx+1)*256],x,y,False)

# The GBA's 8bpp tile is 8x8 pixels. Both BG1/BG2 share the same tile atlas
# (BG tile 0 is all transparent). 64x32 tile map uses 2 screenblocks/layer.
tiles=[bytes(64)]
tile_to_id={tiles[0]:0}
def id_tile(tile):
    if tile not in tile_to_id:
        n=len(tiles)
        if n>=256:
            raise RuntimeError('Tile atlas exceeds charblock0 capacity: needs '+str(n+1)+' tiles')
        tile_to_id[tile]=n
        tiles.append(tile)
    return tile_to_id[tile]

def to_tilemap(img):
    entries=[0]*(64*32)
    for y in range(32):
        for x in range(40):
            tile=b''.join(img[(8*y+i)*W+8*x:(8*y+i)*W+8*x+8] for i in range(8))
            entries[y*64+x]=id_tile(tile)
    # For a 64x32 map the left and right halves go into adjacent screenblocks.
    order=[entries[y*64 +bx*32+x] for bx in range(2) for y in range(32) for x in range(32)]
    assert len(order)==2048
    return struct.pack('<2048H',*order)

base_entries=to_tilemap(base)
over_entries=to_tilemap(over)
(A/'hardware_bg_tiles.bin').write_bytes(b''.join(tiles))
(A/'hardware_bg2_map.bin').write_bytes(base_entries)
(A/'hardware_bg1_map.bin').write_bytes(over_entries)

# 32x32, 8bpp sprite arranged as 16 GBA 8x8 tiles (1D OBJ mapping).
obj=[]
for direction in [2,3,1,0]:  # down,left,right,up consistent with validated sprite orientation
    for frame in range(3):
        src=(A/f'player4_{direction}_{frame}.bin').read_bytes()
        assert len(src)==24*32
        full=bytearray(32*32)
        for row in range(32):
            full[row*32+4:row*32+28]=src[row*24:(row+1)*24]
        for by in range(4):
            for bx in range(4):
                obj.append(b''.join(full[(by*8+j)*32+bx*8:(by*8+j)*32+bx*8+8] for j in range(8)))
assert len(obj)==192
# Debug marker: thin border around original event tile, index from actual palette.
# This is not displayed in ordinary gameplay.
ui_color_src=(A/'mode4_colors.h').read_text()
import re
color_index=int(re.search(r'#define UI_HINT (\d+)',ui_color_src).group(1))
marker=bytearray(16*16)
for y in range(16):
    for x in range(16):
        if y in (0,15) or x in (0,15):marker[y*16+x]=color_index
for by in range(2):
    for bx in range(2):
        obj.append(b''.join(marker[(by*8+j)*16+bx*8:(by*8+j)*16+bx*8+8] for j in range(8)))
(A/'hardware_obj_tiles.bin').write_bytes(b''.join(obj))

# UI: BG0 4bpp, palette bank 14. Input font is supplied 8x16 BMP.
# Every glyph generates TWO hardware 8x8 tiles; the space glyph does not exist.
font=(A/'rm2k_font_mono.bin').read_bytes()
assert len(font)==228*16
UI_FONT_BASE=8
ui_tiles=[]
def solid(color):
    return bytes([color | (color<<4)])*32
ui_tiles.append(solid(0)) # 0 transparent
ui_tiles.append(solid(1)) # 1 frame outer
ui_tiles.append(solid(2)) # 2 frame inner
ui_tiles.append(solid(3)) # 3 blue background (synthetic space)
for _ in range(4,UI_FONT_BASE): ui_tiles.append(solid(0))
for glyph in range(228):
    for half in range(2):
        bits=font[glyph*16+half*8:glyph*16+(half+1)*8]
        assert len(bits)==8
        # Font ink index 4 over an OPAQUE blue glyph background index 3.
        pixels=[4 if bits[y]&(0x80>>x) else 3 for y in range(8) for x in range(8)]
        ui_tiles.append(bytes(pixels[2*i] | (pixels[2*i+1]<<4) for i in range(32)))
assert len(ui_tiles)==UI_FONT_BASE+228*2

# Classic bordered dialogue window used in this sample. Pre-render its border
# once on PC as deduplicated GBA 4bpp tiles. Outside the frame stays transparent
# (BG0 palette entry 0), allowing real BG1/BG2 map to remain visible. Dialogue
# interior is opaque blue so text never shows the map through glyph whitespace.
# 240x160 hardware screen, 8px grid; dialogue occupies x=5..234 and y=112..157.
UI_WINDOW_FIRST_ROW=14
UI_WINDOW_ROWS=6
frame_tiles=[]
ui_tile_to_id={tile:i for i,tile in enumerate(ui_tiles)}
for ty in range(UI_WINDOW_ROWS):
    for tx in range(30):
        pixels=[]
        for iy in range(8):
            y=(UI_WINDOW_FIRST_ROW+ty)*8+iy
            for ix in range(8):
                x=tx*8+ix
                if x<5 or x>234 or y<112 or y>157:
                    color=0 # transparent outside classic window
                elif x in (5,234) or y in (112,157):
                    color=1 # outer light border
                elif x in (6,233) or y in (113,156):
                    color=2 # dark inner border
                else:
                    color=3 # solid dark-blue interior
                pixels.append(color)
        tile=bytes(pixels[k]|(pixels[k+1]<<4) for k in range(0,64,2))
        if tile not in ui_tile_to_id:
            ui_tile_to_id[tile]=len(ui_tiles)
            ui_tiles.append(tile)
        frame_tiles.append(ui_tile_to_id[tile])
assert len(frame_tiles)==30*UI_WINDOW_ROWS
(A/'hardware_ui_window_map.bin').write_bytes(struct.pack('<%dH'%len(frame_tiles),*frame_tiles))
# Nine reusable 8x8 tiles for framed full-screen pause-menu windows.
# This is compiled on the PC; no per-pixel drawing occurs on the GBA.
panel_ids=[]
for py in range(3):
    for px in range(3):
        pixels=[]
        for y in range(8):
            for x in range(8):
                gx=px*8+x; gy=py*8+y
                if gx in (0,23) or gy in (0,23): color=1
                elif gx in (1,22) or gy in (1,22): color=2
                else: color=3
                pixels.append(color)
        tile=bytes(pixels[i] | pixels[i+1]<<4 for i in range(0,64,2))
        if tile not in ui_tile_to_id:
            ui_tile_to_id[tile]=len(ui_tiles)
            ui_tiles.append(tile)
        panel_ids.append(ui_tile_to_id[tile])
(A/'hardware_ui_panel_ids.h').write_text(
    '#pragma once\nstatic const unsigned short ui_panel_tiles[9] = {' +
    ','.join(map(str,panel_ids)) + '};\n')
# Dedicated menu selection arrow for consistent UI across fonts.
cursor_tile=len(ui_tiles)
cursor_pattern=[
    '........',
    '.##.....',
    '.####...',
    '.######.',
    '.####...',
    '.##.....',
    '........',
    '........',
]
cursor_pixels=[4 if c=='#' else 3 for row in cursor_pattern for c in row]
ui_tiles.append(bytes(cursor_pixels[i] | cursor_pixels[i+1]<<4 for i in range(0,64,2)))
assert len(ui_tiles)<=512, ('BG0 charblock 2 overflow',len(ui_tiles))
(A/'hardware_ui_tiles.bin').write_bytes(b''.join(ui_tiles))
(A/'hardware_ui_defs.h').write_text(
    '#pragma once\n#define UI_FONT_BASE 8\n#define UI_PALETTE_BANK 14\n'
    '#define UI_TILE_COUNT %d\n#define UI_CURSOR_TILE %d\n#define UI_WINDOW_FIRST_ROW %d\n'
    '#define UI_WINDOW_ROWS %d\n#define BG_TILE_COUNT %d\n'
    '#define OBJ_TILE_BYTES %d\n' %
    (len(ui_tiles),cursor_tile,UI_WINDOW_FIRST_ROW,UI_WINDOW_ROWS,len(tiles),sum(len(x) for x in obj)))

print('Hardware GBA tiles: %d unique, %d B BG; 12 OBJ frames, %d B; UI %d tiles' % (len(tiles),len(tiles)*64, sum(len(x) for x in obj),len(ui_tiles)))
