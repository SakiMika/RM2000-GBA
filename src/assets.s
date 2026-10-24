.syntax unified
.section .rodata,"a",%progbits
.balign 4
.global hardware_bg_tiles
hardware_bg_tiles: .incbin "assets/hardware_bg_tiles.bin"
.balign 4
.global hardware_bg2_map
hardware_bg2_map: .incbin "assets/hardware_bg2_map.bin"
.balign 4
.global hardware_bg1_map
hardware_bg1_map: .incbin "assets/hardware_bg1_map.bin"
.balign 4
.global hardware_obj_tiles
hardware_obj_tiles: .incbin "assets/hardware_obj_tiles.bin"
.balign 4
.global hardware_ui_tiles
hardware_ui_tiles: .incbin "assets/hardware_ui_tiles.bin"
.balign 4
.global hardware_ui_window_map
hardware_ui_window_map: .incbin "assets/hardware_ui_window_map.bin"
.balign 4
.global palette4
palette4: .incbin "assets/palette4.bin"
.balign 4
.global tile_walk
tile_walk: .incbin "assets/walk.bin"

.balign 4
.global title_palette
title_palette: .incbin "assets/title_palette.bin"
.balign 4
.global title_bitmap
title_bitmap: .incbin "assets/title_bitmap.bin"

.balign 4
.global rm2k_font_raw
rm2k_font_raw: .incbin "assets/rm2k_font_mono.bin"

.balign 4
.global gba_sram_signature
gba_sram_signature: .asciz "SRAM_V110"
