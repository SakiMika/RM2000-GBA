#include <stdio.h>
#include <assert.h>
#include <string.h>
#include <stdint.h>
#define MAP_WIDTH 20
#define MAP_HEIGHT 16
static volatile uint8_t mock_sram[32768];
#define SRAM_PTR (mock_sram)
#include "../src/save_sram.h"

int main(void){
  memset((void*)mock_sram,0xff,sizeof(mock_sram));
  assert(!save_slot_has_any());
  SaveState original={1,11,8,0,0};
  SaveState actual={0};
  for(int i=0;i<4;i++) assert(!save_slot_read(i,&actual));
  for(int i=0;i<4;i++){
    original.x=11+i;
    assert(save_slot_write(i,&original));
    assert(save_slot_read(i,&actual) && actual.x==11+i && actual.y==8);
  }
  assert(save_slot_has_any());
  // Four slots remain independent.
  original.x=19;original.y=15;original.direction=3;
  assert(save_slot_write(1,&original));
  assert(save_slot_read(1,&actual) && actual.x==19 && actual.y==15 && actual.direction==3 && actual.sequence==2);
  assert(save_slot_read(0,&actual) && actual.x==11);
  // Corrupt most recent replica: recover from previous valid replica.
  mock_sram[save_offset(1,1)+7]^=0x03;
  assert(save_slot_read(1,&actual) && actual.x==12 && actual.sequence==1);
  // A torn update never replaces the remaining valid copy.
  original.x=18;original.y=12;
  assert(save_slot_write(1,&original));
  assert(save_slot_read(1,&actual) && actual.x==18 && actual.sequence==2);
  // Invalidate commit bytes for both banks: slot 1 is empty.
  mock_sram[save_offset(1,0)+30]=0;
  mock_sram[save_offset(1,1)+30]=0;
  assert(!save_slot_read(1,&actual));
  assert(save_slot_read(2,&actual) && actual.x==13);
  original.x=20;
  assert(!save_slot_write(0,&original));
  printf("PASS: 4 SRAM slots; restart-style readback; CRC recovery; torn commit; independent slots; bounds\n");
}
