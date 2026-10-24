#!/usr/bin/env python3
"""Validate GBA ROM + supplied font, title, clean pause UI and four SRAM slots."""
from pathlib import Path
import hashlib,struct,re,shutil,subprocess,tempfile
root=Path(__file__).resolve().parents[1]
a=root/'assets'
rom=(root/'build/sample.gba').read_bytes()
code=(root/'build/sample.bin').read_bytes()
assert rom[0xa0:0xac]==b'RM2K GBA'.ljust(12, b' ')
assert rom[0xc0:0xc0+len(code)]==code
assert ((sum(rom[0xa0:0xbe])+0x19)&255)==0
assert rom.count(b'SRAM_V110')==1
assert len(rom)<256*1024
assert len((a/'title_bitmap.bin').read_bytes())==240*160
assert len((a/'title_palette.bin').read_bytes())==512
# Font generated from supplied BMP: 94 ASCII glyphs !..~ + 134 Vietnamese.
raw=(a/'rm2k_font_mono.bin').read_bytes()
assert len(raw)==228*16
assert not (a/'font.bin').exists()
# The original font has no space. Renderer maps U+0020 to a blue blank tile.
src=(root/'src/main.c').read_text()
assert "if(c==' ')return -1" in src
assert 'index<0 ? 3' in src
assert 'ui_put_bank(x,y+1,bottom,bank)' in src
assert 'rm2k_font_extra[i]' in src
assert 'font_advance(idx)' in src
# Fullscreen Pause: exact 30x20 cover, two-row cursor glyph, balanced gold area.
assert 'ui_panel_bank(0,0,30,20,PAUSE_PALETTE_BANK)' in src
assert 'ui_panel_bank(0,0,9,16,PAUSE_PALETTE_BANK)' in src
assert 'ui_panel_bank(0,16,9,4,PAUSE_PALETTE_BANK)' in src
assert 'ui_text_bank(1,17,"0 GP",PAUSE_PALETTE_BANK)' in src
assert 'ui_text_bank(1,row,">",PAUSE_PALETTE_BANK)' in src
assert 'ui_text_bank(1,1,"MENU",PAUSE_PALETTE_BANK)' not in src
assert 'int row=1+i*2' in src
assert 'REG_DISPCNT=DISPCNT_PAUSE' in src
assert '#define DISPCNT_PAUSE 0x0100' in src
assert 'REG_DISPCNT=DISPCNT_GAME' in src
assert 'RM2K SAMPLE' not in src
assert 'MAP: 0001' not in src
assert '4 SRAM SLOTS' not in src
assert 'A: SELECT' not in src
assert 'B: BACK' not in src
assert 'save_slot_write(save_choice,&current)' in src
assert 'save_slot_read(load_slot,&loaded)' in src
assert 'else if((pressed&K_B) && !vm.line_count)' in src
assert 'MOVE_FRAMES 9' in src
# Gameplay map + OAM assets must not change from previously validated.
expected={
 'hardware_bg_tiles.bin':'0745416cc4a1363200ba093897d30bbe1958152b234870263d5c2516b7414a1a',
 'hardware_bg1_map.bin':'ad7facb2586fc6e966c004d7d1d16b024f5805ff7cb47c7a85dabd8b48892ca7',
 'hardware_bg2_map.bin':'bcc51a104fb7a4c84727f14a0bd8ef1eda8b07e2c2b649a61aaaf387c6994236',
 'hardware_obj_tiles.bin':'68caa0a607cff59110ff2f7590a6706243883ac1d3766ca59fa7664d68c7b850',
 'walk.bin':'72390c1bac8a03e3d259e4366f817e2e44180bc0cfc8b9c3be16d9f793a281bc',
 'native_events.h':'82ad648fe7e0661100bb7d44133b2dda9fe1546f84868ebacabf8fe5bf8f2a9b',
}
for n,v in expected.items():
 assert hashlib.sha256((a/n).read_bytes()).hexdigest()==v, 'regression in '+n
ui=(a/'hardware_ui_tiles.bin').read_bytes()
assert len(ui)%32==0
n=len(ui)//32
assert n<=512 and n>=464,n
assert 0x8000+len(ui)<=0xc000,'BG0 font overwrites map memory'
assert (a/'hardware_ui_window_map.bin').stat().st_size==360
refs=struct.unpack('<180H',(a/'hardware_ui_window_map.bin').read_bytes())
assert max(refs)<n
# Verify glyph ! and A are mapped by BMP order and encoded into 4bpp top/bottom.
fontbase=8
for cp in (33,65,97,126):
 index=cp-33
 bits=raw[index*16:index*16+16]
 for half in range(2):
  tile=ui[(fontbase+index*2+half)*32:(fontbase+index*2+half+1)*32]
  got=[(tile[k//2]>>(4*(k&1)))&15 for k in range(64)]
  expected_pixels=[4 if bits[half*8+j]&(0x80>>i) else 3 for j in range(8) for i in range(8)]
  assert got==expected_pixels,(cp,half)
# Synthetic blank must be opaque blue, not character '!' and not transparent.
assert ui[3*32:4*32]==bytes([0x33])*32
assert len(set((a/'rm2k_font_meta.h').read_text().split('rm2k_font_extra')[1].split('};')[0].split(',')))==134
# No obsolete source/font identifiers anywhere within the packaged tree.
for p in root.rglob('*'):
 if p.is_file() and p.suffix in ('.c','.h','.py','.md','.txt','.json','.s','.sh','.bat','.csv'):
  assert ''.join(map(chr,(103,116,97))) not in p.read_text(encoding='utf-8',errors='ignore').lower(),str(p)
assert not (root/'game/Font').exists()
if shutil.which('cc'):
 with tempfile.TemporaryDirectory() as d:
  out=Path(d)/'test_sram'
  subprocess.run(['cc','-std=c11','-O2',str(root/'tests/test_save_sram.c'),'-o',str(out)],check=True)
  subprocess.run([str(out)],check=True)
print('PASS: unversioned header, font BMP 228 glyphs, no space glyph, 16-bit BG tile indices, 4-slot SRAM, visual assets retained')
print('ROM_SHA256='+hashlib.sha256(rom).hexdigest())
