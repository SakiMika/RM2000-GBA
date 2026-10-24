// RPG Maker 2000 sample native GBA — supplied 8x16 font, clean pause menu
// Smooth movement (16 px over 9 VBlanks) using hardware BG scroll
// and OAM sprites. No full-screen framebuffer redraw or DMA during gameplay.
// Real LCF assets/events are compiled on PC, using validated gameplay.
#include <stdint.h>
#include "event_runtime.h"
#include "save_sram.h"
#include "../assets/mode4_colors.h"
#include "../assets/hardware_ui_defs.h"
#include "../assets/hardware_ui_panel_ids.h"
#include "../assets/rm2k_font_meta.h"

#define REG16(a) (*(volatile uint16_t*)(a))
#define REG_DISPCNT REG16(0x04000000)
#define REG_VCOUNT REG16(0x04000006)
#define REG_KEYINPUT REG16(0x04000130)
#define REG_IME REG16(0x04000208)
#define REG_BG0CNT REG16(0x04000008)
#define REG_BG1CNT REG16(0x0400000A)
#define REG_BG2CNT REG16(0x0400000C)
#define REG_BG0HOFS REG16(0x04000010)
#define REG_BG0VOFS REG16(0x04000012)
#define REG_BG1HOFS REG16(0x04000014)
#define REG_BG1VOFS REG16(0x04000016)
#define REG_BG2HOFS REG16(0x04000018)
#define REG_BG2VOFS REG16(0x0400001A)

#define VRAM_BG ((volatile uint16_t*)0x06000000)
#define VRAM_UI_CHARS ((volatile uint16_t*)0x06008000)
#define VRAM_BG2_MAP ((volatile uint16_t*)0x0600C000) // SB24+25
#define VRAM_BG1_MAP ((volatile uint16_t*)0x0600D000) // SB26+27
#define VRAM_UI_MAP ((volatile uint16_t*)0x0600E000)  // SB28
#define VRAM_OBJ ((volatile uint16_t*)0x06010000)
#define PALETTE_BG ((volatile uint16_t*)0x05000000)
#define PALETTE_OBJ ((volatile uint16_t*)0x05000200)
#define OAM ((volatile uint16_t*)0x07000000)

#define K_A 1
#define K_B 2
#define K_SELECT 4
#define K_START 8
#define K_RIGHT 16
#define K_LEFT 32
#define K_UP 64
#define K_DOWN 128
#define MOVE_FRAMES 9  // 16/9 px/frame.
#define PAUSE_PALETTE_BANK 12
#define DISPCNT_GAME 0x1740
#define DISPCNT_PAUSE 0x0100

extern const uint8_t rm2k_font_raw[];
extern const uint8_t title_bitmap[];
extern const uint16_t title_palette[];
extern const uint8_t hardware_bg_tiles[];
extern const uint8_t hardware_bg2_map[];
extern const uint8_t hardware_bg1_map[];
extern const uint8_t hardware_obj_tiles[];
extern const uint8_t hardware_ui_tiles[];
extern const uint16_t hardware_ui_window_map[];
extern const uint16_t palette4[];
extern const uint8_t tile_walk[];

// Copy at startup only. BIOS DMA is not necessary for these small resource sets.
static void copy_halfwords(volatile uint16_t* target,const uint16_t* source,unsigned count){
  for(unsigned n=0;n<count;n++)target[n]=source[n];
}

static void wait_vblank(void) {
  // Wait for the beginning of *next* VBlank, not just any time in VBlank.
  while(REG_VCOUNT>=160u){}
  while(REG_VCOUNT<160u){}
}

// Title rendering in Mode4. Buttons/cursor are dynamic: Continue only becomes
// selectable when at least one CRC-checked SRAM save exists.
static void title_pixel(int x,int y,uint8_t color) {
  if((unsigned)x>=240u||(unsigned)y>=160u)return;
  unsigned offset=(unsigned)y*120u+(unsigned)x/2u;
  volatile uint16_t* vram=(volatile uint16_t*)0x06000000u;
  uint16_t old=vram[offset];
  if(x&1)vram[offset]=(uint16_t)((old&0x00FFu)|((uint16_t)color<<8));
  else vram[offset]=(uint16_t)((old&0xFF00u)|color);
}
// Supplied font: 228 visible glyphs (!..~ and Vietnamese extensions).
// There is NO U+0020 glyph. Space advances without indexing the bitmap.
static uint32_t font_next_codepoint(const char** text){
  const unsigned char* p=(const unsigned char*)*text;
  if(!p[0])return 0;
  uint32_t c=p[0];
  if(c<128){*text=(const char*)(p+1);return c;}
  if((c&0xE0)==0xC0 && (p[1]&0xC0)==0x80){
    *text=(const char*)(p+2);
    return ((c&0x1Fu)<<6)|(p[1]&0x3Fu);
  }
  if((c&0xF0)==0xE0 && (p[1]&0xC0)==0x80 && (p[2]&0xC0)==0x80){
    *text=(const char*)(p+3);
    return ((c&0x0Fu)<<12)|((p[1]&0x3Fu)<<6)|(p[2]&0x3Fu);
  }
  *text=(const char*)(p+1);
  return '?';
}
static int font_index(uint32_t c){
  if(c==' ')return -1; // synthetic 5-pixel space; not a font atlas entry
  if(c>=33 && c<=126)return (int)c-33;
  for(int i=0;i<RM2K_FONT_EXTRA_COUNT;i++)
    if(c==rm2k_font_extra[i])return 94+i;
  return '?' - 33;
}
static int font_advance(int index){
  return index<0 ? rm2k_font_widths[0] : rm2k_font_widths[index+1]+1;
}
static void title_text(int x,int y,const char* str,uint8_t color){
  while(*str){
    uint32_t cp=font_next_codepoint(&str);
    int idx=font_index(cp);
    if(idx>=0){
      const uint8_t* g=rm2k_font_raw+(unsigned)idx*16u;
      for(int row=0;row<16;row++){
        uint8_t bits=g[row];
        for(int col=0;col<8;col++)
          if(bits&(0x80u>>col))title_pixel(x+col,y+row,color);
      }
    }
    x+=font_advance(idx);
  }
}
static void title_cursor(int x,int y){
  static const uint8_t bits[8]={0x00,0x40,0x70,0x7C,0x70,0x40,0,0};
  for(int row=0;row<8;row++)for(int col=0;col<8;col++)
    if(bits[row]&(0x80u>>col))title_pixel(x+col,y+row,242);
}
static void title_box(int left,int top,int right,int bottom){
  for(int y=top;y<=bottom;y++)for(int x=left;x<=right;x++) {
    int edge=(x==left||x==right||y==top||y==bottom);
    int inset=(x==left+1||x==right-1||y==top+1||y==bottom-1);
    title_pixel(x,y,(uint8_t)(edge?240:(inset?241:243)));
  }
}
static void title_draw_main(int choice,int can_continue){
  REG_DISPCNT=0x0080;
  copy_halfwords((volatile uint16_t*)0x06000000,
                 (const uint16_t*)title_bitmap,240u*160u/2u);
  title_text(78,96,"NEW GAME",240);
  title_text(78,116,"CONTINUE",can_continue?240:241);
  title_cursor(63,choice?120:100);
  REG_DISPCNT=0x0404;
}
static void title_draw_slots(int selected){
  REG_DISPCNT=0x0080;
  copy_halfwords((volatile uint16_t*)0x06000000,
                 (const uint16_t*)title_bitmap,240u*160u/2u);
  title_box(30,49,209,152);
  title_text(62,55,"CONTINUE",240);
  for(int i=0;i<SAVE_SLOT_COUNT;i++){
    SaveState state;
    int valid=save_slot_read(i,&state);
    int row=75+i*18;
    char label[24]="SLOT 1  EMPTY";
    label[5]=(char)('1'+i);
    if(valid){
      label[8]='M';label[9]='0';label[10]='1';label[11]=' ';
      label[12]=(char)('0'+state.x/10);label[13]=(char)('0'+state.x%10);
      label[14]=',';label[15]=(char)('0'+state.y/10);
      label[16]=(char)('0'+state.y%10);label[17]=0;
    }
    title_text(51,row,label,valid?240:241);
    if(selected==i)title_cursor(38,row+3);
  }
  REG_DISPCNT=0x0404;
}
// Returns -1 for New Game, otherwise slot index 0..3 for Continue.
static int title_screen(void){
  REG_DISPCNT=0x0080;
  for(int n=0;n<256;n++)PALETTE_BG[n]=title_palette[n];
  // Index 243 = opaque blue used only for slot-select popup.
  PALETTE_BG[243]=(uint16_t)((32>>3)|((41>>3)<<5)|((86>>3)<<10));
  REG_BG2HOFS=REG_BG2VOFS=0;
  int choice=0,choosing_slot=0,slot=0;
  int can_continue=save_slot_has_any();
  title_draw_main(choice,can_continue);
  int previous=(~REG_KEYINPUT)&0x03ff;
  for(;;){
    wait_vblank();
    int keys=(~REG_KEYINPUT)&0x03ff;
    int pressed=keys&~previous;
    previous=keys;
    if(choosing_slot){
      if(pressed&K_B){choosing_slot=0;title_draw_main(choice,can_continue);continue;}
      if(pressed&K_UP){slot=(slot+SAVE_SLOT_COUNT-1)%SAVE_SLOT_COUNT;title_draw_slots(slot);}
      else if(pressed&K_DOWN){slot=(slot+1)%SAVE_SLOT_COUNT;title_draw_slots(slot);}
      else if(pressed&K_A){
        if(save_slot_read(slot,0)) {REG_DISPCNT=0x0080;return slot;}
      }
    } else {
      if(can_continue && (pressed&(K_UP|K_DOWN))){choice^=1;title_draw_main(choice,can_continue);}
      if(pressed&(K_A|K_START)){
        if(choice==0){REG_DISPCNT=0x0080;return -1;}
        if(can_continue){choosing_slot=1;slot=0;
          // Prefer the first valid slot in the list.
          while(slot<SAVE_SLOT_COUNT-1 && !save_slot_read(slot,0))slot++;
          title_draw_slots(slot);
        }
      }
    }
  }
}

// BG0 transparent tile 0; text and dialogue are tiny 8x8 4bpp tiles.
static void ui_clear(void) {
  for(int i=0;i<32*32;i++)VRAM_UI_MAP[i]=0;
}
static void ui_put_bank(int x,int y,int tile,int bank) {
  if((unsigned)x<30u&&(unsigned)y<20u)
    VRAM_UI_MAP[y*32+x]=(uint16_t)(tile | (bank<<12));
}
static void ui_put(int x,int y,int tile) {
  ui_put_bank(x,y,tile,UI_PALETTE_BANK);
}
static void ui_fill(int x,int y,int w,int h,int tile){
  for(int j=0;j<h;j++)for(int i=0;i<w;i++)ui_put(x+i,y+j,tile);
}
static void ui_fill_bank(int x,int y,int w,int h,int tile,int bank){
  for(int j=0;j<h;j++)for(int i=0;i<w;i++)ui_put_bank(x+i,y+j,tile,bank);
}
// BG0 is a grid of 8x8 4bpp tiles. A supplied 8x16 glyph uses two
// consecutive tiles. The engine reserves 8px per character on BG0 (fixed
// grid); the separate title renderer honors variable character widths.
static void ui_text_bank(int x,int y,const char* str,int bank){
  while(*str && x<30){
    int index=font_index(font_next_codepoint(&str));
    int top=index<0 ? 3 : UI_FONT_BASE+index*2;
    int bottom=index<0 ? 3 : top+1;
    ui_put_bank(x,y,top,bank);
    ui_put_bank(x,y+1,bottom,bank);
    x++;
  }
}
static void ui_text(int x,int y,const char* str){
  ui_text_bank(x,y,str,UI_PALETTE_BANK);
}
static void ui_text_disabled(int x,int y,const char* str){
  ui_text_bank(x,y,str,13);
}

// 8-bit screen-space UI: reusable precompiled 1px frame/inner-frame tiles.
// Draws only the 8x8 tilemap, not a pixel framebuffer.
static void ui_panel(int x,int y,int w,int h){
  for(int j=0;j<h;j++)for(int i=0;i<w;i++){
    int tile_x=(i==0)?0:((i==w-1)?2:1);
    int tile_y=(j==0)?0:((j==h-1)?2:1);
    ui_put(x+i,y+j,ui_panel_tiles[tile_y*3+tile_x]);
  }
}
static void ui_panel_bank(int x,int y,int w,int h,int bank){
  for(int j=0;j<h;j++)for(int i=0;i<w;i++){
    int tile_x=(i==0)?0:((i==w-1)?2:1);
    int tile_y=(j==0)?0:((j==h-1)?2:1);
    ui_put_bank(x+i,y+j,ui_panel_tiles[tile_y*3+tile_x],bank);
  }
}

static void num2(char* p,int v);

static const char* const menu_labels[7]={
  "RESUME", "ITEM", "SKILL", "EQUIP", "STATUS", "SAVE", "TITLE"
};
// UI glyphs are 8x16 (two 8px BG rows). A cursor must use the same
// two-row text renderer or it will sit too high against its selected label.
// The command panel ends at row 15. The 4-row gold panel starts at row 16:
// border 16, text 17+18, border 19 (never clips the baseline).
static void ui_draw_menu_frame(int selection){
  ui_panel_bank(0,0,30,20,PAUSE_PALETTE_BANK); // Opaque 240x160 backdrop
  ui_panel_bank(0,0,9,16,PAUSE_PALETTE_BANK);
  ui_panel_bank(9,0,21,16,PAUSE_PALETTE_BANK);
  ui_panel_bank(0,16,9,4,PAUSE_PALETTE_BANK);
  ui_panel_bank(9,16,21,4,PAUSE_PALETTE_BANK);
  for(int i=0;i<7;i++){
    int row=1+i*2;                         // 8px top/bottom margin
    if(i==selection)ui_text_bank(1,row,">",PAUSE_PALETTE_BANK);
    if(i==0||i==5||i==6)ui_text_bank(2,row,menu_labels[i],PAUSE_PALETTE_BANK);
    else ui_text_bank(2,row,menu_labels[i],13);
  }
  ui_text_bank(1,17,"0 GP",PAUSE_PALETTE_BANK);
}

static void ui_draw_pause(int menu_choice,int confirmation,int yes,int tx,int ty){
  (void)tx;(void)ty;
  ui_draw_menu_frame(confirmation ? -1 : menu_choice);
  if(confirmation){
    ui_panel_bank(6,6,18,7,PAUSE_PALETTE_BANK);
    ui_text_bank(8,7,"RETURN TITLE?",PAUSE_PALETTE_BANK);
    ui_text_bank(9,10,"NO",PAUSE_PALETTE_BANK);
    ui_text_bank(16,10,"YES",PAUSE_PALETTE_BANK);
    ui_text_bank(yes?15:8,10,">",PAUSE_PALETTE_BANK);
  }
}

static void ui_draw_save_slots(int slot,int result,int tx,int ty){
  ui_draw_menu_frame(5);
  ui_text_bank(11,1,"SAVE",PAUSE_PALETTE_BANK);
  for(int i=0;i<SAVE_SLOT_COUNT;i++){
    SaveState existing;
    int valid=save_slot_read(i,&existing);
    char label[]="SLOT 1  EMPTY       ";
    label[5]=(char)('1'+i);
    if(valid){
      const char filled[]="SLOT 1  M01 00,00";
      for(unsigned c=0;c<sizeof(filled);c++)label[c]=filled[c];
      label[5]=(char)('1'+i);
      num2(label+12,existing.x); num2(label+15,existing.y);
    }
    int row=4+i*3;
    if(slot==i)ui_text_bank(11,row,">",PAUSE_PALETTE_BANK);
    ui_text_bank(13,row,label,valid?PAUSE_PALETTE_BANK:13);
  }
  if(result==1)ui_text_bank(11,17,"SAVED",PAUSE_PALETTE_BANK);
  else if(result==2)ui_text_bank(11,17,"SAVE FAILED",PAUSE_PALETTE_BANK);
  else {
    char pos[]="X:00 Y:00";
    num2(pos+2,tx);num2(pos+7,ty);
    ui_text_bank(11,17,pos,PAUSE_PALETTE_BANK);
  }
}

static void num2(char* p,int v) {
  if(v<0)v=0;
  *p=(char)('0'+(v/10)%10);
  *(p+1)=(char)('0'+v%10);
}

static void ui_draw_dialogue(const EventVM* vm){
  // Use the classic framed dialogue box, now entirely on hardware
  // BG0 so it retains smooth Mode0 map scrolling and OAM sprites.
  // Border, two inset edges and opaque interior were precompiled to 4bpp.
  for(int row=0;row<UI_WINDOW_ROWS;row++) {
    for(int col=0;col<30;col++) {
      ui_put(col,UI_WINDOW_FIRST_ROW+row,
             hardware_ui_window_map[row*30+col]);
    }
  }
  // The 8x16 font fits two lines at y=120 and y=136 inside the classic box.
  // Four-line RM2K messages require paging in the event interpreter later.
  for(int i=0;i<(int)vm->line_count && i<2;i++)
    ui_text(2,15+i*2,vm->lines[i]);
}
static void ui_draw_debug(int tx,int ty,int direction) {
  int face_x=tx+(direction==2)-(direction==1);
  int face_y=ty+(direction==0)-(direction==3);
  const OriginalEvent* ev=&original_events[0];
  char line[]="P:00,00 E:00,00 A:WAIT ";
  num2(line+2,tx);num2(line+5,ty);
  num2(line+10,ev->x);num2(line+13,ev->y);
  if(eventvm_find_action(face_x,face_y)>=0) {
    // Avoid overrunning the fixed string buffer (READY has 5 chars).
    line[18]='R';line[19]='E';line[20]='A';line[21]='D';line[22]='Y';
  }
  ui_fill(0,0,30,2,1);
  ui_fill(0,0,30,1,3);
  ui_text(1,0,line);
}
static void refresh_ui(const EventVM* vm,int tx,int ty,int direction,int debug){
  ui_clear();
  if(vm->line_count)ui_draw_dialogue(vm);
  if(debug)ui_draw_debug(tx,ty,direction);
}

// GBA OBJ attribute settings: square, 8bpp, 32x32, 1D mapping.
static void oam_hide_all(void) {
  for(int n=0;n<128;n++){
    OAM[n*4]=0x0200; // OBJ disabled
    OAM[n*4+1]=0;
    OAM[n*4+2]=0;
    OAM[n*4+3]=0;
  }
}
static void draw_player(int world_x,int world_y,int cam_x,int cam_y,int dir,int frame){
  int sx=world_x-8-cam_x;
  int sy=world_y-16-cam_y;
  if(sx<=-32||sx>=240||sy<=-32||sy>=160){OAM[0]=0x0200;return;}
  OAM[0]=(uint16_t)((sy&255)|0x2000); // 8bpp
  OAM[1]=(uint16_t)((sx&511)|0x8000); // square size=2 = 32x32
  OAM[2]=(uint16_t)(2*16*(dir*3+frame) | (2<<10)); // priority 2
}
static void draw_debug_marker(int cam_x,int cam_y,int debug){
  const OriginalEvent* ev=&original_events[0];
  int sx=ev->x*16-cam_x;
  int sy=ev->y*16-cam_y;
  if(!debug || sx<=-16||sx>=240||sy<=-16||sy>=160){OAM[4]=0x0200;return;}
  OAM[4]=(uint16_t)((sy&255)|0x2000);
  OAM[5]=(uint16_t)((sx&511)|0x4000); // 16x16 8bpp
  OAM[6]=(uint16_t)(12*32 | (1<<10)); // priority 1 (above player)
}

// LDB passability: down=1,left=2,right=4,up=8. Same LCF passability semantics.
static int can_step(int tx,int ty,int dx,int dy){
  int nx=tx+dx,ny=ty+dy;
  if((unsigned)nx>=MAP_WIDTH||(unsigned)ny>=MAP_HEIGHT)return 0;
  if(eventvm_blocks_tile(nx,ny))return 0;
  uint8_t from=tile_walk[ty*MAP_WIDTH+tx];
  uint8_t to=tile_walk[ny*MAP_WIDTH+nx];
  int exit_bit=0,enter_bit=0;
  if(dy>0){exit_bit=1;enter_bit=8;}
  if(dy<0){exit_bit=8;enter_bit=1;}
  if(dx>0){exit_bit=4;enter_bit=2;}
  if(dx<0){exit_bit=2;enter_bit=4;}
  return (from&exit_bit)&&(to&enter_bit);
}
static int clamp(int x,int lo,int hi) {return x<lo?lo:(x>hi?hi:x);}

static void game_session(int load_slot) {
  REG_DISPCNT=0x0080; // forced blank while loading video memory
  // Mode4's RGB555 palette reused for BG2 and the OBJ sprite palette.
  for(int i=0;i<SAMPLE_PALETTE_COUNT;i++){
    PALETTE_BG[i]=palette4[i];
    PALETTE_OBJ[i]=palette4[i];
  }
  // UI uses an independent 4bpp BG palette bank, never collides with map colors.
  PALETTE_BG[UI_PALETTE_BANK*16+0]=0;
  PALETTE_BG[UI_PALETTE_BANK*16+1]=palette4[UI_OUTER];
  PALETTE_BG[UI_PALETTE_BANK*16+2]=palette4[UI_INNER];
  PALETTE_BG[UI_PALETTE_BANK*16+3]=palette4[UI_BG];
  PALETTE_BG[UI_PALETTE_BANK*16+4]=palette4[UI_TEXT];
  PALETTE_BG[UI_PALETTE_BANK*16+5]=palette4[UI_HINT];
  // Flat green pause-menu palette (no gradient), keeping the same frame tiles.
  // Bank 13 is the disabled-text variant: same green background, muted gray text.
  uint16_t muted=0;
  uint16_t green_fill=(8u)|((18u)<<5)|((8u)<<10);
  uint16_t bright_border=(31u)|((31u)<<5)|((31u)<<10);
  uint16_t inner_border=(22u)|((28u)<<5)|((22u)<<10);
  uint16_t bright_text=(29u)|((31u)<<5)|((29u)<<10);
  for(int shift=0;shift<=10;shift+=5){
    int b=(green_fill>>shift)&31, f=(bright_text>>shift)&31;
    muted|=(uint16_t)((b*2+f)/3)<<shift;
  }
  PALETTE_BG[PAUSE_PALETTE_BANK*16+0]=0;
  PALETTE_BG[PAUSE_PALETTE_BANK*16+1]=bright_border;
  PALETTE_BG[PAUSE_PALETTE_BANK*16+2]=inner_border;
  PALETTE_BG[PAUSE_PALETTE_BANK*16+3]=green_fill;
  PALETTE_BG[PAUSE_PALETTE_BANK*16+4]=bright_text;
  PALETTE_BG[PAUSE_PALETTE_BANK*16+5]=(24u)|((28u)<<5)|((24u)<<10);       // hint/cursor
  PALETTE_BG[13*16+0]=0;
  PALETTE_BG[13*16+1]=bright_border;
  PALETTE_BG[13*16+2]=inner_border;
  PALETTE_BG[13*16+3]=green_fill;
  PALETTE_BG[13*16+4]=muted;
  PALETTE_BG[13*16+5]=(24u)|((28u)<<5)|((24u)<<10);

  copy_halfwords(VRAM_BG,(const uint16_t*)hardware_bg_tiles,BG_TILE_COUNT*64/2);
  copy_halfwords(VRAM_BG2_MAP,(const uint16_t*)hardware_bg2_map,2048);
  copy_halfwords(VRAM_BG1_MAP,(const uint16_t*)hardware_bg1_map,2048);
  copy_halfwords(VRAM_UI_CHARS,(const uint16_t*)hardware_ui_tiles,UI_TILE_COUNT*32/2);
  copy_halfwords(VRAM_OBJ,(const uint16_t*)hardware_obj_tiles,OBJ_TILE_BYTES/2);
  oam_hide_all();
  ui_clear();

  // BG0 4bpp charblock 2, screenblock 28, fixed screen-space text.
  REG_BG0CNT=(uint16_t)((2<<2)|(28<<8)|0);
  // BG1 8bpp charblock 0, screenblock 26, 64x32, above-player layer.
  REG_BG1CNT=(uint16_t)(1 | (26<<8) | 0x0080 | 0x4000);
  // BG2 8bpp charblock 0, screenblock 24, 64x32, background layer.
  REG_BG2CNT=(uint16_t)(3 | (24<<8) | 0x0080 | 0x4000);
  REG_BG0HOFS=REG_BG0VOFS=0;
  REG_DISPCNT=DISPCNT_GAME; // Mode0, BG0/1/2, sprites, 1D OBJ mapping

  int tx=11,ty=8,direction=0;
  SaveState loaded;
  if(load_slot>=0 && save_slot_read(load_slot,&loaded) && loaded.map_id==1){
    tx=loaded.x;ty=loaded.y;direction=loaded.direction;
  }
  int world_x=tx*16,world_y=ty*16;
  int frame=1,previous=(~REG_KEYINPUT)&0x03ff;
  int move_dx=0,move_dy=0,remaining=0,pending_action=0,debug=0;
  int move_progress=0,move_origin_x=world_x,move_origin_y=world_y;
  // B opens the pause menu, including mid-step. Saving mid-step persists the
  // last completed tile; loading always starts from that exact tile position.
  int paused=0,menu_choice=0,menu_confirm=0,menu_yes=0;
  int save_menu=0,save_choice=0,save_result=0;
  EventVM vm;eventvm_reset(&vm);
  refresh_ui(&vm,tx,ty,direction,debug);

  // Every game tick is aligned to a GBA VBlank. BG scroll and OAM position
  // changes take only a few register writes, even during pixel scrolling.
  for(;;){
    wait_vblank();
    int keys=(~REG_KEYINPUT)&0x03ff;
    int pressed=keys&~previous;
    previous=keys;
    int redraw_ui=0;
    if(paused){
      if(pressed&K_B){
        if(menu_confirm){menu_confirm=0;}
        else if(save_menu){save_menu=0;menu_choice=5;save_result=0;}
        else {paused=0; REG_DISPCNT=DISPCNT_GAME;}
        redraw_ui=1;
      } else if(save_menu){
        if(pressed&K_UP){save_choice=(save_choice+3)%4;save_result=0;redraw_ui=1;}
        else if(pressed&K_DOWN){save_choice=(save_choice+1)%4;save_result=0;redraw_ui=1;}
        if(pressed&K_A){
          SaveState current;
          current.map_id=1;current.x=(uint8_t)tx;current.y=(uint8_t)ty;
          current.direction=(uint8_t)direction;current.sequence=0;
          save_result=save_slot_write(save_choice,&current)?1:2;
          redraw_ui=1;
        }
      } else if(menu_confirm){
        if(pressed&(K_LEFT|K_RIGHT|K_UP|K_DOWN)){menu_yes^=1;redraw_ui=1;}
        if(pressed&K_A){
          if(menu_yes){REG_DISPCNT=0x0080;return;}
          menu_confirm=0;redraw_ui=1;
        }
      } else {
        // Selectable: RESUME (0), SAVE (5), TITLE (6).
        if(pressed&K_UP){menu_choice=(menu_choice==0)?6:((menu_choice==6)?5:0);redraw_ui=1;}
        else if(pressed&K_DOWN){menu_choice=(menu_choice==0)?5:((menu_choice==5)?6:0);redraw_ui=1;}
        if(pressed&K_A){
          if(menu_choice==0){paused=0; REG_DISPCNT=DISPCNT_GAME; redraw_ui=1;}
          else if(menu_choice==5){save_menu=1;save_choice=0;save_result=0;redraw_ui=1;}
          else if(menu_choice==6){menu_confirm=1;menu_yes=0;redraw_ui=1;}
        }
      }
    } else if((pressed&K_B) && !vm.line_count){
      paused=1; REG_DISPCNT=DISPCNT_PAUSE; menu_choice=0;menu_confirm=0;menu_yes=0;save_menu=0;
      redraw_ui=1;
    } else if(pressed&K_SELECT){debug^=1;redraw_ui=1;
    } else if(vm.line_count) {
      if(pressed&(K_A|K_B)){eventvm_next(&vm);redraw_ui=1;}
    } else if(remaining) {
      if(pressed&K_A)pending_action=1;
      // Absolute sub-tile interpolation: each of the 9 frames advances 1-2px.
      // No zero-motion padding frames, avoiding the periodic "hitch" of
      // slowing an 8-frame walk by inserting idle VBlanks.
      move_progress++;
      int offset=(16*move_progress+MOVE_FRAMES/2)/MOVE_FRAMES;
      world_x=move_origin_x+move_dx*offset;
      world_y=move_origin_y+move_dy*offset;
      remaining--;
      static const uint8_t sequence[MOVE_FRAMES]={1,0,0,0,1,2,2,2,1};
      frame=remaining?sequence[move_progress-1]:1;
      if(!remaining){
        tx+=move_dx;ty+=move_dy;
        if(pending_action){
          pending_action=0;
          if(eventvm_try_action(&vm,tx,ty,direction))redraw_ui=1;
        }
      }
      if(debug)redraw_ui=1;
    } else {
      if(pressed&K_A) {
        if(eventvm_try_action(&vm,tx,ty,direction))redraw_ui=1;
      } else {
        int newdir=direction,dx=0,dy=0;
        if(keys&K_DOWN){newdir=0;dy=1;}
        else if(keys&K_LEFT){newdir=1;dx=-1;}
        else if(keys&K_RIGHT){newdir=2;dx=1;}
        else if(keys&K_UP){newdir=3;dy=-1;}
        if(newdir!=direction){direction=newdir;frame=1;redraw_ui=1;}
        if((dx||dy)&&can_step(tx,ty,dx,dy)){
          move_dx=dx;move_dy=dy;
          move_origin_x=world_x;move_origin_y=world_y;
          move_progress=1;
          remaining=MOVE_FRAMES-1;
          const int offset=(16*move_progress+MOVE_FRAMES/2)/MOVE_FRAMES;
          world_x=move_origin_x+dx*offset;
          world_y=move_origin_y+dy*offset;
          frame=1;
        }
      }
    }
    int camera_x=clamp(world_x-112,0,MAP_WIDTH*16-240);
    int camera_y=clamp(world_y-72,0,MAP_HEIGHT*16-160);
    REG_BG2HOFS=REG_BG1HOFS=(uint16_t)camera_x;
    REG_BG2VOFS=REG_BG1VOFS=(uint16_t)camera_y;
    draw_player(world_x,world_y,camera_x,camera_y,direction,frame);
    draw_debug_marker(camera_x,camera_y,debug);
    if(redraw_ui){
      if(paused){
        ui_clear();
        if(save_menu)ui_draw_save_slots(save_choice,save_result,tx,ty);
        else ui_draw_pause(menu_choice,menu_confirm,menu_yes,tx,ty);
      }
      else refresh_ui(&vm,tx,ty,direction,debug);
    }
  }
}

// Title/New Game/Continue all rebuild VRAM, BG palettes and OAM cleanly.
// SRAM stores four independently selectable slot records, with dual bank+CRC.
__attribute__((noreturn)) void main(void){
  REG_IME=0;
  for(;;){
    int loaded_slot=title_screen();
    game_session(loaded_slot);
  }
}
