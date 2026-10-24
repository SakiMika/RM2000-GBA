ENTRY(_start)
MEMORY {
  ROM (rx): ORIGIN = 0x080000C0, LENGTH = 32M - 0xC0
  EWRAM (rwx): ORIGIN = 0x02000000, LENGTH = 256K
}
SECTIONS {
  .text : { KEEP(*(.text.start)) *(.text*) *(.rodata*) } > ROM
  . = ALIGN(4);
  .data : { __data_start = .; *(.data*) __data_end = .; } > EWRAM AT>ROM
  __data_load = LOADADDR(.data);
  .bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON); . = ALIGN(4); __bss_end = .; } > EWRAM
  /DISCARD/ : { *(.comment) *(.note*) *(.ARM.attributes*) *(.ARM.exidx*) *(.eh_frame*) }
}
