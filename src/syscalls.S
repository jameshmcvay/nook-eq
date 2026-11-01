.set noreorder
.set noat
.section .text.start,"ax",@progbits
.globl __start
.ent __start
__start:
 /* NetBSD/MIPS native entry a0 points at argc, followed by argv pointers. */
 move $a1,$a0
 lw $a0,0($a1)
 addiu $a1,$a1,4
 addiu $sp,$sp,-32
 jal main
 nop
 move $a0,$v0
 ori $v0,$zero,1
 syscall
 break
.end __start
.section .text,"ax",@progbits
.globl os_call
.ent os_call
os_call:
 move $v0,$a0
 move $a0,$a1
 move $a1,$a2
 move $a2,$a3
 lw $a3,16($sp)
 syscall
 beq $a3,$zero,1f
 nop
 subu $v0,$zero,$v0
1: jr $ra
 nop
.end os_call
.section .note.netbsd.ident,"a",@note
.balign 4
.word 7,4,1
.asciz "NetBSD"
.balign 4
.word 400000000
