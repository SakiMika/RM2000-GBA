.syntax unified
.cpu arm7tdmi
.arm
.section .text.start,"ax",%progbits
.global _start
.type _start,%function
_start:
    ldr sp, =0x03007F00
    @ Copy initialized .data from ROM LMA into EWRAM before C code executes.
    ldr r0, =__data_load
    ldr r1, =__data_start
    ldr r3, =__data_end
copy_data:
    cmp r1, r3
    bhs copy_done
    ldr r2, [r0], #4
    str r2, [r1], #4
    b copy_data
copy_done:
    ldr r0, =__bss_start
    ldr r1, =__bss_end
    mov r2, #0
zero_bss:
    cmp r0, r1
    bhs bss_done
    str r2, [r0], #4
    b zero_bss
bss_done:
    bl main
loop: b loop
