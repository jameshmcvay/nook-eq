.set noreorder
.set noat
.text
.globl os_at
.ent os_at
os_at:
 /* NetBSD/MIPS __syscall is required for 64-bit argument slots.
    __syscall(0:nr, fd, buffer, size, padding, offset_hi:offset_lo). */
 lw $t0,16($sp)
 addiu $sp,$sp,-40
 sw $a3,16($sp)
 sw $zero,20($sp)
 sw $zero,24($sp)
 sw $t0,28($sp)
 move $a3,$a2
 move $a2,$a1
 move $a1,$a0
 move $a0,$zero
 ori $v0,$zero,198
 syscall
 beq $a3,$zero,1f
 nop
 subu $v0,$zero,$v0
1: jr $ra
 addiu $sp,$sp,40
.end os_at
