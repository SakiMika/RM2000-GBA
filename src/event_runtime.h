#pragma once
/* Small, deterministic event interpreter for the sample's original LCF commands.
 * It never parses XML or invents messages; all commands are compiled on the PC.
 * Supported: ShowMessage 10110, ShowMessage_2 20110, Action Button trigger.
 */
#include "../assets/native_events.h"

typedef struct {
  int active_event; /* index in original_events, or -1 */
  unsigned pc;      /* next command offset in original_commands */
  unsigned line_count;
  const char* lines[4];
} EventVM;

static void eventvm_reset(EventVM* vm) {
  vm->active_event=-1;
  vm->pc=0;
  vm->line_count=0;
  for(int i=0;i<4;i++) vm->lines[i]=0;
}

/* Return original event index only when the player is FACING the event's tile. */
static int eventvm_find_action(int target_x,int target_y) {
  for(int i=0;i<ORIGINAL_EVENT_COUNT;i++) {
    const OriginalEvent* ev=&original_events[i];
    if(ev->trigger==0 && ev->layer==1 && ev->x==target_x && ev->y==target_y)
      return i;
  }
  return -1;
}

/* Same-layer map events block player movement even without a graphic.
 * The sample page has no Through/flight rule and does not move. */
static int eventvm_blocks_tile(int target_x,int target_y) {
  for(int i=0;i<ORIGINAL_EVENT_COUNT;i++) {
    const OriginalEvent* ev=&original_events[i];
    if(ev->layer==1 && ev->x==target_x && ev->y==target_y) return 1;
  }
  return 0;
}

/* Load next message group. Return 1 if a dialogue is ready, 0 if event ended.
 * One 10110 ShowMessage plus its following 20110 continuations = one window.
 */
static int eventvm_next(EventVM* vm) {
  vm->line_count=0;
  if(vm->active_event<0) return 0;
  const OriginalEvent* ev=&original_events[vm->active_event];
  const unsigned end=(unsigned)ev->command_start+ev->command_count;
  if(vm->pc>=end) {eventvm_reset(vm);return 0;}
  const OriginalCommand* command=&original_commands[vm->pc];
  if(command->code!=10110) {eventvm_reset(vm);return 0;}
  vm->lines[vm->line_count++]=command->text;
  vm->pc++;
  while(vm->pc<end && original_commands[vm->pc].code==20110) {
    if(vm->line_count<4) vm->lines[vm->line_count++]=original_commands[vm->pc].text;
    vm->pc++;
  }
  return 1;
}

static int eventvm_begin(EventVM* vm,int event_index) {
  if(event_index<0 || event_index>=ORIGINAL_EVENT_COUNT) return 0;
  vm->active_event=event_index;
  vm->pc=original_events[event_index].command_start;
  return eventvm_next(vm);
}

/* True only when the player faces the original Action Button event.
 * Coordinates refer to the player's current, committed tile, not the animated
 * world pixel position while crossing a tile boundary. */
static int eventvm_try_action(EventVM* vm,int tx,int ty,int direction) {
  int dx=(direction==2)-(direction==1);
  int dy=(direction==0)-(direction==3);
  int event_index=eventvm_find_action(tx+dx,ty+dy);
  return event_index>=0 && eventvm_begin(vm,event_index);
}
