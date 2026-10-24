#pragma once
/* RM2K sample native GBA SRAM save backend.
 * Four user slots, two independent 32-byte records per slot (256B total).
 * Versioned records + CRC16 + two-byte commit marker; byte writes only.
 * No unimplemented switches/inventory: only map/position/direction are stored.
 * SRAM v1, not compatible with future engine-wide RPG Maker save formats.
 */
#include <stdint.h>

#define SAVE_SLOT_COUNT 4
#define SAVE_RECORD_SIZE 32
#define SAVE_BASE_OFFSET 256u
#define SAVE_VERSION 1
#ifndef SRAM_PTR
#define SRAM_PTR ((volatile uint8_t*)0x0E000000u)
#endif

typedef struct SaveState {
    uint8_t map_id;
    uint8_t x;
    uint8_t y;
    uint8_t direction;
    uint32_t sequence;
} SaveState;

static uint16_t save_crc16(const uint8_t* data, int count){
    uint16_t crc=0xFFFFu;
    for(int i=0;i<count;i++){
        crc^=(uint16_t)data[i]<<8;
        for(int bit=0;bit<8;bit++){
            crc=(crc&0x8000u)?(uint16_t)((crc<<1)^0x1021u):(uint16_t)(crc<<1);
        }
    }
    return crc;
}
static unsigned save_offset(int slot,int replica){
    return SAVE_BASE_OFFSET+(unsigned)(slot*2+replica)*SAVE_RECORD_SIZE;
}
static void save_read_raw(int slot,int replica,uint8_t* dst){
    volatile uint8_t* sram=SRAM_PTR;
    unsigned off=save_offset(slot,replica);
    for(int i=0;i<SAVE_RECORD_SIZE;i++)dst[i]=sram[off+(unsigned)i];
}
static int save_decode(const uint8_t* b,int slot,SaveState* state){
    if(b[0]!='R'||b[1]!='2'||b[2]!='S'||b[3]!='V'||b[4]!=SAVE_VERSION||b[5]!=slot||
       b[30]!=0xA5||b[31]!=0x5A)return 0;
    if(b[6]!=1 || b[7]>=MAP_WIDTH || b[8]>=MAP_HEIGHT || b[9]>3)return 0;
    uint16_t crc=save_crc16(b,28);
    if(b[28]!=(uint8_t)crc||b[29]!=(uint8_t)(crc>>8))return 0;
    if(state){
        state->map_id=b[6];state->x=b[7];state->y=b[8];state->direction=b[9];
        state->sequence=(uint32_t)b[12]|((uint32_t)b[13]<<8)|((uint32_t)b[14]<<16)|((uint32_t)b[15]<<24);
    }
    return 1;
}
static int save_slot_read(int slot,SaveState* state){
    if(slot<0||slot>=SAVE_SLOT_COUNT)return 0;
    uint8_t r0[SAVE_RECORD_SIZE],r1[SAVE_RECORD_SIZE];
    SaveState s0,s1;
    save_read_raw(slot,0,r0);save_read_raw(slot,1,r1);
    int v0=save_decode(r0,slot,&s0),v1=save_decode(r1,slot,&s1);
    if(!v0&&!v1)return 0;
    /* Signed subtraction compares recent serial numbers even over wraparound. */
    if(v1 && (!v0 || (int32_t)(s1.sequence-s0.sequence)>0)){
        if(state)*state=s1;
    }else if(state)*state=s0;
    return 1;
}
static int save_slot_has_any(void){
    for(int i=0;i<SAVE_SLOT_COUNT;i++)if(save_slot_read(i,0))return 1;
    return 0;
}
static int save_slot_write(int slot,const SaveState* state){
    if(slot<0||slot>=SAVE_SLOT_COUNT||!state||state->map_id!=1||
       state->x>=MAP_WIDTH||state->y>=MAP_HEIGHT||state->direction>3)return 0;
    uint8_t raw0[SAVE_RECORD_SIZE],raw1[SAVE_RECORD_SIZE],record[SAVE_RECORD_SIZE];
    SaveState old0,old1;
    save_read_raw(slot,0,raw0);save_read_raw(slot,1,raw1);
    int v0=save_decode(raw0,slot,&old0),v1=save_decode(raw1,slot,&old1);
    int latest=(v1&&(!v0||(int32_t)(old1.sequence-old0.sequence)>0))?1:0;
    int target=(v0||v1)?1-latest:0;
    uint32_t sequence=(v0||v1)?((latest?old1.sequence:old0.sequence)+1u):1u;
    for(int i=0;i<SAVE_RECORD_SIZE;i++)record[i]=0;
    record[0]='R';record[1]='2';record[2]='S';record[3]='V';
    record[4]=SAVE_VERSION;record[5]=(uint8_t)slot;
    record[6]=state->map_id;record[7]=state->x;record[8]=state->y;record[9]=state->direction;
    for(int i=0;i<4;i++)record[12+i]=(uint8_t)(sequence>>(i*8));
    uint16_t crc=save_crc16(record,28);
    record[28]=(uint8_t)crc;record[29]=(uint8_t)(crc>>8);
    record[30]=0xA5;record[31]=0x5A;
    volatile uint8_t* sram=SRAM_PTR;
    unsigned off=save_offset(slot,target);
    /* Invalidate only the chosen bank. Other bank remains valid while writing. */
    sram[off+30]=0; sram[off+31]=0;
    for(int i=0;i<30;i++)sram[off+(unsigned)i]=record[i];
    sram[off+30]=record[30];sram[off+31]=record[31];
    uint8_t check[SAVE_RECORD_SIZE];SaveState verified;
    save_read_raw(slot,target,check);
    return save_decode(check,slot,&verified)&&verified.sequence==sequence &&
           verified.x==state->x && verified.y==state->y && verified.direction==state->direction;
}
