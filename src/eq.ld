ENTRY(eq_uiomove)
SECTIONS {
 . = 0x803be368;
 .text : { KEEP(*(.text.entry)) *(.text .text.*) }
 .rodata ALIGN(16) : { *(.rodata .rodata.*) }
 .data ALIGN(16) : { *(.data .data.*) *(.sdata .sdata.*) }
 .bss ALIGN(16) : { *(.bss .bss.*) *(.sbss .sbss.*) *(COMMON) }
 .MIPS.abiflags ALIGN(8) : { *(.MIPS.abiflags) }
 .reginfo ALIGN(4) : { *(.reginfo) }
 /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) *(.pdr) *(.mdebug*) *(.gnu.attributes) }
 ASSERT(. <= 0x803cc640, "EQ exceeds verified reserved tail")
}
