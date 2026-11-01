.set noreorder
.set noat
.text
.globl os_five
.ent os_five
os_five:
 lw $t0,16($sp)
 lw $t1,20($sp)
 addiu $sp,$sp,-24
 sw $t1,16($sp)
 move $v0,$a0
 move $a0,$a1
 move $a1,$a2
 move $a2,$a3
 move $a3,$t0
 syscall
 beq $a3,$zero,1f
 nop
 subu $v0,$zero,$v0
1: jr $ra
 addiu $sp,$sp,24
.end os_five
