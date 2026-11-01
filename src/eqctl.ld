ENTRY(__start)
/* NetBSD 4's ELF loader supports at most two PT_LOAD segments. */
PHDRS {
 text PT_LOAD FILEHDR PHDRS FLAGS(5);
 data PT_LOAD FLAGS(6);
 note PT_NOTE FLAGS(4);
}
SECTIONS {
 . = 0x00400140;
 .text : { KEEP(*(.text.start)) *(.text .text.*) } :text
 .rodata ALIGN(16) : { *(.rodata .rodata.*) } :text
 .note.netbsd.ident ALIGN(4) : { KEEP(*(.note.netbsd.ident)) } :text :note
 .MIPS.abiflags ALIGN(8) : { *(.MIPS.abiflags) } :text
 .reginfo ALIGN(4) : { *(.reginfo) } :text
 .data ALIGN(4096) : { *(.data .data.*) *(.sdata .sdata.*) *(.got .got.*) } :data
 .bss ALIGN(16) : { *(.bss .bss.*) *(.sbss .sbss.*) } :data
 /DISCARD/ : { *(.comment) *(.eh_frame*) *(.pdr) *(.mdebug*) *(.gnu.attributes) }
}
