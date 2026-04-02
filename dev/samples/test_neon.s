.text
.global _start
.type _start, %function
_start:
    # Simple integer operations only
    mov x0, #1
    mov x1, #2
    mov x2, #3
    mov x3, #4
    mov x4, #5
    mov x5, #6
    mov x6, #7
    mov x7, #8

    add x8, x0, x1
    add x9, x8, x2
    sub x10, x9, x3
    and x11, x10, x4

    # Store result
    adr x0, result
    str x11, [x0]

    # Exit
    mov x0, #0
    ret

result:
    .word 0