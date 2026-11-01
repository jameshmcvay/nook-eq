.set noreorder
.set noat
.section .text.entry,"ax",@progbits
.globl eq_uiomove
.type eq_uiomove,@function
.ent eq_uiomove
eq_uiomove:
 addiu $sp,$sp,-32
 sw $ra,28($sp)
 sw $gp,24($sp)
 sw $a0,16($sp)
 sw $a1,20($sp)
 lui $t9,0x8015
 ori $t9,$t9,0xf2f0
 jalr $t9
 nop
 bne $v0,$zero,1f
 nop
 lw $a0,16($sp)
 lw $a1,20($sp)
 jal eq_filter
 nop
1:
 lw $gp,24($sp)
 lw $ra,28($sp)
 jr $ra
 addiu $sp,$sp,32
.end eq_uiomove
.size eq_uiomove,.-eq_uiomove

/* Wrap the one ath_i2s_init call in ath_i2s_open. */
.globl eq_dma_init
.type eq_dma_init,@function
.ent eq_dma_init
eq_dma_init:
 addiu $sp,$sp,-32
 sw $ra,28($sp)
 sw $gp,24($sp)
 sw $a0,20($sp)
 jal 0x801f3844
 nop
 move $a1,$v0
 lw $a0,20($sp)
 jal eq_stream_reset
 nop
 lw $gp,24($sp)
 lw $ra,28($sp)
 jr $ra
 addiu $sp,$sp,32
.end eq_dma_init
.size eq_dma_init,.-eq_dma_init

/* Record the requested nominal rate after stock clock programming. Drift
   corrections use another ioctl and never change this nominal rate. */
.macro rate_wrapper name, target, rate
.globl \name
.type \name,@function
.ent \name
\name:
 addiu $sp,$sp,-24
 sw $ra,20($sp)
 sw $gp,16($sp)
 jal \target
 nop
 lui $t0,%hi(eq_sample_rate)
 ori $t1,$zero,\rate
 sw $t1,%lo(eq_sample_rate)($t0)
 lw $gp,16($sp)
 lw $ra,20($sp)
 jr $ra
 addiu $sp,$sp,24
.end \name
.size \name,.-\name
.endm
rate_wrapper eq_clock40_44100, 0x801f1e98, 44100
rate_wrapper eq_clock40_48000, 0x801f1e98, 48000
rate_wrapper eq_clock25_44100, 0x801f20c4, 44100
rate_wrapper eq_clock25_48000, 0x801f20c4, 48000

/* Private control minor: no DMA allocation or hardware reset on open/close.
   All other minors tail-call the original driver with the original arguments. */
.macro control_check original
 lui $t0,0xfff0
 and $t0,$a0,$t0
 srl $t0,$t0,12
 andi $t1,$a0,255
 or $t0,$t0,$t1
 ori $t1,$zero,128
 beq $t0,$t1,1f
 nop
 j \original
 nop
1:
.endm
.globl eq_open
.type eq_open,@function
.ent eq_open
eq_open:
 control_check 0x801f3d18
 jr $ra
 move $v0,$zero
.end eq_open
.size eq_open,.-eq_open
.globl eq_close
.type eq_close,@function
.ent eq_close
eq_close:
 control_check 0x801f3e68
 jr $ra
 move $v0,$zero
.end eq_close
.size eq_close,.-eq_close
.globl eq_ioctl
.type eq_ioctl,@function
.ent eq_ioctl
eq_ioctl:
 control_check 0x801f2928
 addiu $sp,$sp,-24
 sw $ra,20($sp)
 sw $gp,16($sp)
 move $a0,$a1
 move $a1,$a2
 move $a2,$a3
 jal eq_control
 nop
 lw $gp,16($sp)
 lw $ra,20($sp)
 jr $ra
 addiu $sp,$sp,24
.end eq_ioctl
.size eq_ioctl,.-eq_ioctl
