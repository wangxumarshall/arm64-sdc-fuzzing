.arch armv8-a
.fpu neon
.text
.global _start
.type _start, %function
_start:
    fmov s0, s1
    fmov s2, s3
    mov x0, #0
    ret