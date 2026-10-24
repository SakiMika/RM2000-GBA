#!/usr/bin/env python3
"""Sample-specific offline RPG Maker 2000 converter: LCF to native GBA.
Reads LCF without XML, exporting graphics, map layers, passability,
walk frames and native event-command tables for the minimal ARM runtime.
"""
from pathlib import Path
from PIL import Image
import struct, json
ROOT=Path(__file__).resolve().parents[1]
GAME=ROOT/'game'
OUT=ROOT/'assets'; OUT.mkdir(exist_ok=True)

def num(buf,pos):
 v=0
 while True:
  c=buf[pos];pos+=1;v=(v<<7)|(c&127)
  if c<128:return v,pos

def fields(buf, pos=0):
 while pos<len(buf):
  fid,pos=num(buf,pos)
  if fid==0:break
  n,pos=num(buf,pos)
  if pos+n>len(buf):raise RuntimeError('Truncated LCF field')
  yield fid,buf[pos:pos+n]
  pos+=n

def lcf_fields(fp, header):
 b=fp.read_bytes();n,off=num(b,0)
 assert b[off:off+n]==header,(fp,b[off:off+n])
 return dict(fields(b[off+n:]))

def array(buf):
 n,pos=num(buf,0);return n,pos

def rgbs(idx):
 a=idx & 31;return a

def to555(rgb):
 r,g,b=rgb[:3]
 return 0x8000|((b>>3)<<10)|((g>>3)<<5)|(r>>3)

# The following quarter-tile recipe tables are transcribed from the layout
# documented by EasyRPG's TilemapLayer; implemented independently in Python.
# D-variants are (TL,TR,BL,BR) and each coordinate is within a 3x4 half-tile block.
D=[
 ((1,2),(1,2),(1,2),(1,2)),
 ((2,0),(1,2),(1,2),(1,2)),
 ((1,2),(2,0),(1,2),(1,2)),
 ((2,0),(2,0),(1,2),(1,2)),
 ((1,2),(1,2),(1,2),(2,0)),
 ((2,0),(1,2),(1,2),(2,0)),
 ((1,2),(2,0),(1,2),(2,0)),
 ((2,0),(2,0),(1,2),(2,0)),
 ((1,2),(1,2),(2,0),(1,2)),
 ((2,0),(1,2),(2,0),(1,2)),
 ((1,2),(2,0),(2,0),(1,2)),
 ((2,0),(2,0),(2,0),(1,2)),
 ((1,2),(1,2),(2,0),(2,0)),
 ((2,0),(1,2),(2,0),(2,0)),
 ((1,2),(2,0),(2,0),(2,0)),
 ((2,0),(2,0),(2,0),(2,0)),
 ((0,2),(0,2),(0,2),(0,2)),
 ((0,2),(2,0),(0,2),(0,2)),
 ((0,2),(0,2),(0,2),(2,0)),
 ((0,2),(2,0),(0,2),(2,0)),
 ((1,1),(1,1),(1,1),(1,1)),
 ((1,1),(1,1),(1,1),(2,0)),
 ((1,1),(1,1),(2,0),(1,1)),
 ((1,1),(1,1),(2,0),(2,0)),
 ((2,2),(2,2),(2,2),(2,2)),
 ((2,2),(2,2),(2,0),(2,2)),
 ((2,0),(2,2),(2,2),(2,2)),
 ((2,0),(2,2),(2,0),(2,2)),
 ((1,3),(1,3),(1,3),(1,3)),
 ((2,0),(1,3),(1,3),(1,3)),
 ((1,3),(2,0),(1,3),(1,3)),
 ((2,0),(2,0),(1,3),(1,3)),
 ((0,2),(2,2),(0,2),(2,2)),
 ((1,1),(1,1),(1,3),(1,3)),
 ((0,1),(0,1),(0,1),(0,1)),
 ((0,1),(0,1),(0,1),(2,0)),
 ((2,1),(2,1),(2,1),(2,1)),
 ((2,1),(2,1),(2,0),(2,1)),
 ((2,3),(2,3),(2,3),(2,3)),
 ((2,0),(2,3),(2,3),(2,3)),
 ((0,3),(0,3),(0,3),(0,3)),
 ((0,3),(2,0),(0,3),(0,3)),
 ((0,1),(2,1),(0,1),(2,1)),
 ((0,1),(0,1),(0,3),(0,3)),
 ((0,3),(2,3),(0,3),(2,3)),
 ((2,1),(2,1),(2,3),(2,3)),
 ((0,1),(2,1),(0,3),(2,3)),
 ((1,2),(1,2),(1,2),(1,2)),
 ((1,2),(1,2),(1,2),(1,2)),
 ((0,0),(0,0),(0,0),(0,0)),
]
# A recipes: each quadrant's A subtile value, -1 means draw B coastline.
A=[
 (-1,-1,-1,-1),
 (3,-1,-1,-1),(-1,3,-1,-1),(3,3,-1,-1),
 (-1,-1,-1,3),(3,-1,-1,3),(-1,3,-1,3),(3,3,-1,3),
 (-1,-1,3,-1),(3,-1,3,-1),(-1,3,3,-1),(3,3,3,-1),
 (-1,-1,3,3),(3,-1,3,3),(-1,3,3,3),(3,3,3,3),
 (1,-1,1,-1),(1,3,1,-1),(1,-1,1,3),(1,3,1,3),
 (2,2,-1,-1),(2,2,-1,3),(2,2,3,-1),(2,2,3,3),
 (-1,1,-1,1),(-1,1,3,1),(3,1,-1,1),(3,1,3,1),
 (-1,-1,2,2),(3,-1,2,2),(-1,3,2,2),(3,3,2,2),
 (1,1,1,1),(2,2,2,2),
 (0,2,1,-1),(0,2,1,3),(2,0,-1,1),(2,0,3,1),
 (-1,1,2,0),(3,1,2,0),(1,-1,0,2),(1,3,0,2),
 (0,0,1,1),(0,2,0,2),(1,1,0,0),(2,0,2,0),(0,0,0,0)
]

def compose(chip,id):
 dst=Image.new('RGB',(16,16),(0,0,0))
 if 4000<=id<4600:
  block=(id-4000)//50; v=(id-4000)%50
  if block<4: bx=(block%2)*3;by=8+(block//2)*4
  else: bx=6+(block%2)*3;by=((block-4)//2)*4
  for i,(sx,sy) in enumerate(D[v]):
   ox=(i%2)*8;oy=(i//2)*8
   dst.paste(chip.crop(((bx+sx)*16+ox,(by+sy)*16+oy,(bx+sx)*16+ox+8,(by+sy)*16+oy+8)),(ox,oy))
 elif id<3000:
  block=id//1000; sub=(id%1000)//50; av=id%50
  if av>=len(A):return dst
  for i,n in enumerate(A[av]):
   ox=(i%2)*8;oy=(i//2)*8
   if n<0:
    t=(sub>>i)&1
    if block==2:t^=3
    sx=0;sy=4+t
   else:sx=(3 if block==1 else 0);sy=n
   if sub and av:
    t=(sub>>i)&1
    if block==2:t*=2
    if t:sx=0;sy=4+t
   dst.paste(chip.crop(((sx*2+(i%2))*8,(sy*2+(i//2))*8,(sx*2+(i%2))*8+8,(sy*2+(i//2))*8+8)),(ox,oy))
 elif 3000<=id<4000:
  # C tile, first animation frame
  col=3+(id-3000)//50
  dst=chip.crop((col*16,4*16,col*16+16,5*16))
 elif 5000<=id<5200:
  v=id-5000
  if v<96:cx=12+v%6;cy=v//6
  else:cx=18+(v-96)%6;cy=(v-96)//6
  dst=chip.crop((cx*16,cy*16,cx*16+16,cy*16+16))
 return dst

f=lcf_fields(GAME/'Map0001.lmu',b'LcfMapUnit')
width=int.from_bytes(f.get(2,b'\x14'),'big');height=int.from_bytes(f.get(3,b'\x0f'),'big')
assert width*height*2==len(f[0x47]),(width,height,len(f[0x47]))
lower=struct.unpack('<'+str(width*height)+'H',f[0x47]);upper=struct.unpack('<'+str(width*height)+'H',f[0x48]);
chip_p=Image.open(GAME/'ChipSet/Outline.png')
chip=chip_p.convert('RGB')
assert chip.size==(480,256)

# Read the selected chipset passability from the original RPG_RT.ldb.
# LCF uses a chunked format: database chunk 0x14 is a DB array of chipsets,
# and subfields 0x04 and 0x05 contain 162 lower / 144 upper passability bytes.
def get_chipset_passability(chipset_id):
 db=lcf_fields(GAME/'RPG_RT.ldb',b'LcfDataBase')
 data=db[0x14]; count,at=num(data,0)
 for _ in range(count):
  cid,at=num(data,at)
  sub={}
  while True:
   tag,at=num(data,at)
   if tag==0: break
   n,at=num(data,at)
   sub[tag]=data[at:at+n];at+=n
  if cid==chipset_id:
   return sub[4],sub[5]
 raise ValueError(f'Chipset {chipset_id} missing from LDB')
chipset_id=num(f[1],0)[0]
pass_lower,pass_upper=get_chipset_passability(chipset_id)
assert len(pass_lower)==162 and len(pass_upper)==144

# Base layer remains separate. Upper-layer tiles are *not* baked into the base.
# An older palette-image mask conversion inadvertently erased the bridge.
base=Image.new('RGB',(width*16,height*16),(0,0,0))
tilecache={tile:compose(chip,tile) for tile in set(lower)}
for i,t in enumerate(lower):base.paste(tilecache[t],((i%width)*16,(i//width)*16))
px=list(base.get_flattened_data() if hasattr(base,'get_flattened_data') else base.getdata())
(OUT/'bg.bin').write_bytes(struct.pack('<%dH'%len(px),*(to555(p) for p in px)))

# Upper graphics: one 16x16 bitmap per distinct upper ID. In the RPG2k chipset
# transparency means *palette INDEX zero*, not RGB black and not the palette value 255.
upper_tiles=sorted({u for u in upper if u>=10000 and u!=10000})
upper_tiles_data=[]
for tile_id in upper_tiles:
 v=tile_id-10000
 assert 0 <= v < len(pass_upper), ('Upper layer tile ID out of range',tile_id)
 if v < 48: cx=18+v%6;cy=8+v//6
 else: cx=24+(v-48)%6;cy=(v-48)//6
 raw=chip_p.crop((cx*16,cy*16,cx*16+16,cy*16+16))
 raw_rgb=raw.convert('RGB')
 mask=Image.frombytes('L',raw.size,bytes(255 if index!=0 else 0 for index in raw.tobytes()))
 upper_tiles_data.extend(0 if raw.getpixel((x,y))==0 else to555(raw_rgb.getpixel((x,y)))
                         for y in range(16) for x in range(16))
(OUT/'upper_raw.bin').write_bytes(struct.pack('<%dH'%len(upper_tiles_data),*upper_tiles_data))
upper_index={v:i for i,v in enumerate(upper_tiles)}
placements=[]
for i,t in enumerate(upper):
 if t==10000:continue
 v=t-10000
 passbits=pass_upper[v]
 x,y=i%width,i//width
 placements.append((x,y,upper_index[t],1 if passbits&0x10 else 0,passbits))
with open(OUT/'upper_layout.h','w') as out:
 out.write('#pragma once\n#include <stdint.h>\n')
 out.write('typedef struct { uint8_t x, y, tile_index, above; } UpperPlacement;\n')
 out.write('static const UpperPlacement upper_placements[] = {\n')
 for x,y,idx,above,pbits in placements:
  out.write(f'  {{{x},{y},{idx},{above}}}, // passability 0x{pbits:02x}\n')
 out.write('};\n')
 out.write(f'#define UPPER_PLACEMENT_COUNT {len(placements)}\n')
 out.write(f'#define UPPER_TILE_COUNT {len(upper_tiles)}\n')

# Original 4x2 CharSet sheet: 3 animation columns × 4 directional rows
# per character. Maintain the verified orientation mapping:
# game down=row2, left=row3, right=row1, up=row0.
char=Image.open(GAME/'CharSet/Chara1.png')
char_rgb=char.convert('RGB')
transparent=char.getpixel((0,0))
for direction in range(4):
 for frame in range(3):
  x0=frame*24;y0=direction*32
  raw=[0 if char.getpixel((x,y))==transparent else to555(char_rgb.getpixel((x,y)))
       for y in range(y0,y0+32) for x in range(x0,x0+24)]
  (OUT/f'player_{direction}_{frame}.bin').write_bytes(struct.pack('<768H',*raw))

# Directional collision bits from LDB chipset; upper ordinary tiles override
# lower passability (e.g. the bridge is passable over otherwise impassable water).
# Upper tiles marked 'Above' leave movement to the lower tile.
walk=[]
for low,top in zip(lower,upper):
 if low>=10000: low_mask=0
 elif low>=5000: low_mask=pass_lower[18+low-5000] if 0<=low-5000<144 else 0
 elif low>=4000: low_mask=pass_lower[6+(low-4000)//50]
 elif low>=3000: low_mask=pass_lower[3+(low-3000)//50]
 else: low_mask=pass_lower[low//1000]
 low_mask &= 0x0f
 if 10000<top<10144 and not(pass_upper[top-10000]&0x10):
  mask=pass_upper[top-10000]&0x0f
 else: mask=low_mask
 walk.append(mask)
(OUT/'walk.bin').write_bytes(bytes(walk))
# Extract event's first page and its actual text strings; keep data-derived x,y.
evdata=f[0x51];total,off=num(evdata,0);events=[]
for _ in range(total):
 eid,off=num(evdata,off)
 # event record is zero terminated, use dedicated loop
 def take_record(buf,offset):
  d={}
  while True:
   k,offset=num(buf,offset)
   if k==0:break
   sz,offset=num(buf,offset);d[k]=buf[offset:offset+sz];offset+=sz
  return d,offset
 ed,off=take_record(evdata,off)
 event={'id':eid,'x':num(ed[2],0)[0],'y':num(ed[3],0)[0],'name':ed[1].decode('latin1')}
 pg=ed[5];cnt,q=num(pg,0);pages=[]
 for j in range(cnt):
  pid,q=num(pg,q);p,q=take_record(pg,q)
  cmdbytes=p.get(0x34,b'');cmdpos=0;commands=[]
  while cmdpos<len(cmdbytes):
   code,cmdpos=num(cmdbytes,cmdpos)
   if code==0:break
   indent,cmdpos=num(cmdbytes,cmdpos)
   length,cmdpos=num(cmdbytes,cmdpos)
   txt=cmdbytes[cmdpos:cmdpos+length];cmdpos+=length
   par_count,cmdpos=num(cmdbytes,cmdpos)
   params=[]
   for z in range(par_count):
    v,cmdpos=num(cmdbytes,cmdpos);params.append(v)
   commands.append({'code':code,'text':txt.decode('latin1'),'indent':indent,'params':params})
  condition,atcond=take_record(p.get(0x02,b'\x00'),0)
  flagraw=condition.get(1,b'\x00')
  pageflags=num(flagraw,0)[0] if flagraw else 0
  pages.append({'id':pid,'trigger':num(p.get(0x21,b'\x00'),0)[0],
                'layer':num(p.get(0x22,b'\x01'),0)[0],
                'character_name':p.get(0x15,b'').decode('latin1'),
                'conditions_flags':pageflags,'commands':commands})
 event['pages']=pages;events.append(event)
assert events and all(x['text'] for x in events[0]['pages'][0]['commands'][:2])
# Optional native event-visual overrides. The original LMU event at (12,3) has
# an empty character_name, so a tree stump cannot appear by merely executing
# the original event commands. We deliberately bind a visual from the same
# project's original ChipSet. This file is opt-in, never treated as LCF data.
visual_overrides=json.loads((ROOT/'tools/event_visual_overrides.json').read_text(encoding='utf-8'))['overrides']
event_by_id={e['id']:e for e in events}
event_visual_records=[]
visual_data=[]
for spec in visual_overrides:
 if spec['map_id']!=1:raise ValueError('This sample supports only Map0001')
 eid=spec['event_id']
 if eid not in event_by_id:raise ValueError(f'Visual override for missing LCF event {eid}')
 ev=event_by_id[eid]
 if len(ev['pages'])!=1 or ev['pages'][0]['character_name']:
  raise ValueError(f'Event {eid} has a native character graphic or multiple pages; override must be reviewed')
 if spec['width']!=16 or spec['height']!=16:
  raise ValueError('Renderer supports only 16x16 event-visual tiles')
 source=(GAME/spec['source']).resolve()
 if not source.is_relative_to(GAME.resolve()):raise ValueError('Visual asset path must be inside game')
 art=Image.open(source)
 if art.mode!='P':raise ValueError('Expected palette-indexed original ChipSet image')
 col,row=spec['tile_col'],spec['tile_row']
 rect=(col*16,row*16,(col+1)*16,(row+1)*16)
 if rect[2]>art.width or rect[3]>art.height:raise ValueError('Visual source outside image')
 crop=art.crop(rect)
 rgb=crop.convert('RGB')
 pixels=[]
 for y in range(16):
  for x in range(16):
   pixels.append(0 if crop.getpixel((x,y))==0 else to555(rgb.getpixel((x,y))))
 if sum(v!=0 for v in pixels)<20:raise ValueError('Tree stump sprite appears empty')
 vi=len(event_visual_records)
 visual_data.extend(pixels)
 event_visual_records.append({'id':eid,'x':ev['x'],'y':ev['y'],'sprite_index':vi,'source':spec['source'],'tile_col':col,'tile_row':row,'opaque_pixels':sum(v!=0 for v in pixels),'note':spec['note']})
(OUT/'event_visual_raw.bin').write_bytes(struct.pack('<%dH'%len(visual_data),*visual_data))
with open(OUT/'event_visual_layout.h','w') as out:
 out.write('#pragma once\n#include <stdint.h>\n')
 out.write('typedef struct { uint16_t event_id; uint8_t x,y,sprite_index; } EventVisualPlacement;\n')
 out.write('static const EventVisualPlacement event_visuals[] = {\n')
 for v in event_visual_records:
  out.write(f"  {{{v['id']},{v['x']},{v['y']},{v['sprite_index']}}},\n")
 out.write('};\n')
 out.write(f'#define EVENT_VISUAL_COUNT {len(event_visual_records)}\n')
messages=[x['text'] for x in events[0]['pages'][0]['commands'] if x['code'] in (10110,20110)]
# Emit native event tables from the ORIGINAL LCF event stream. No XML intermediate.
# This is intentionally scoped to unconditional Action Button pages and Show Message
# (10110) with continuation (20110). Reject other opcodes instead of silently
# converting them into incorrect behavior.
SUPPORTED_CODES = {10110, 20110}
def c_string(s):
 # Literal original byte values; octal escape avoids greedy hexadecimal escapes.
 return '"' + ''.join(chr(b) if 32<=b<127 and b not in (34,92)
                      else ('\\\\' if b==92 else ('\\\"' if b==34 else f'\\{b:03o}'))
                      for b in s.encode('latin1')) + '"'

original_commands=[]
native_events=[]
for event in events:
 if len(event['pages']) != 1:
  raise NotImplementedError('Multiple event pages require page-condition logic; refusing to silently change behavior')
 page=event['pages'][0]
 if page['trigger'] != 0:
  raise NotImplementedError('Only original Action Button trigger is implemented')
 if page['layer'] != 1:
  raise NotImplementedError('Only original same-as-character event layer is implemented')
 if page['conditions_flags'] != 0:
  raise NotImplementedError('Conditional event pages are not implemented yet')
 if page['character_name']:
  raise NotImplementedError('An event character graphic requires sprite handling')
 begin=len(original_commands)
 for command in page['commands']:
  if command['code'] not in SUPPORTED_CODES:
   raise NotImplementedError(f"Unsupported original event command {command['code']}, event ID {event['id']}")
  if command['indent'] or command['params']:
   raise NotImplementedError('Indented or parameterized commands not supported in this sample')
  if command['code']==20110 and (len(original_commands)==begin or original_commands[-1]['code'] not in (10110,20110)):
   raise ValueError('ShowMessage continuation without previous ShowMessage')
  original_commands.append(command)
 native_events.append((event['id'],event['x'],event['y'],page['trigger'],page['layer'],begin,len(original_commands)-begin))

with open(OUT/'native_events.h','w') as out:
 out.write('#pragma once\n#include <stdint.h>\n')
 out.write('typedef struct { uint16_t code; uint8_t indent; const char *text; } OriginalCommand;\n')
 out.write('typedef struct { uint16_t id; uint8_t x,y,trigger,layer; uint16_t command_start,command_count; } OriginalEvent;\n')
 out.write('static const OriginalCommand original_commands[] = {\n')
 for cmd in original_commands:
  out.write(f"  {{{cmd['code']},{cmd['indent']},{c_string(cmd['text'])}}},\n")
 out.write('};\nstatic const OriginalEvent original_events[] = {\n')
 for eid,x,y,trigger,layer,start,count in native_events:
  out.write(f'  {{{eid},{x},{y},{trigger},{layer},{start},{count}}},\n')
 out.write(f'}};\nenum {{ ORIGINAL_EVENT_COUNT = {len(native_events)}, ORIGINAL_COMMAND_COUNT = {len(original_commands)} }};\n')
 out.write(f'enum {{ MAP_WIDTH={width}, MAP_HEIGHT={height} }};\n')
print('Prepared',width,height,'map pixels',len(px),'event',events,'graphics overrides:',len(event_visual_records))
