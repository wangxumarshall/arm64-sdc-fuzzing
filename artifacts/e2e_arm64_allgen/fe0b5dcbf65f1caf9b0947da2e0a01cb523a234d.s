.arch armv8-a
.arch_extension fp16
.arch_extension fhm
.arch_extension memtag
.arch_extension lse
.text
FCSEL d0, d1, d2, eq
FCVT s0, h1
FCVT d0, h1
FCVT h0, s1
FCVT d0, s1
FCVT h0, d1
FCVT s0, d1
FCVTAS h0, h1
FCVTAS 00, 00
FCVTAS v0.8h, v2.8h
FCVTAS v0.4s, v2.4s
FCVTAS w0, h1
FCVTAS x0, h1
FCVTAS w0, s1
FCVTAS x0, s1
FCVTAS w0, d1
FCVTAS x0, d1
FCVTAS s0, h1
FCVTAS d0, h1
FCVTAS d0, s1
FCVTAS s0, d1
FCVTAU h0, h1
FCVTAU 00, 00
FCVTAU v0.8h, v2.8h
FCVTAU v0.4s, v2.4s
FCVTAU w0, h1
FCVTAU x0, h1
FCVTAU w0, s1
FCVTAU x0, s1
FCVTAU w0, d1
FCVTAU x0, d1
FCVTAU s0, h1
FCVTAU d0, h1
FCVTAU d0, s1
FCVTAU s0, d1
FCVTL0 v1.4s, v3.4s
FCVTMS h0, h1
FCVTMS 00, 00
FCVTMS v0.8h, v2.8h
FCVTMS v0.4s, v2.4s
FCVTMS w0, h1
FCVTMS x0, h1
FCVTMS w0, s1
FCVTMS x0, s1
FCVTMS w0, d1
FCVTMS x0, d1
FCVTMS s0, h1
FCVTMS d0, h1
FCVTMS d0, s1
FCVTMS s0, d1
FCVTMU h0, h1
FCVTMU 00, 00
FCVTMU v0.8h, v2.8h
FCVTMU v0.4s, v2.4s
FCVTMU w0, h1
FCVTMU x0, h1
FCVTMU w0, s1
FCVTMU x0, s1
FCVTMU w0, d1
FCVTMU x0, d1
FCVTMU s0, h1
FCVTMU d0, h1
FCVTMU d0, s1
FCVTMU s0, d1
FCVTN0 v1.4s, v3.4s
FCVTN v0.4s, v2.4s, v4.4s
FCVTN0 v1.4s, v3.4S, v4.4S
FCVTNS h0, h1
FCVTNS 00, 00
FCVTNS v0.8h, v2.8h
FCVTNS v0.4s, v2.4s
FCVTNS w0, h1
FCVTNS x0, h1
FCVTNS w0, s1
FCVTNS x0, s1
FCVTNS w0, d1
FCVTNS x0, d1
FCVTNS s0, h1
FCVTNS d0, h1
FCVTNS d0, s1
FCVTNS s0, d1
FCVTNU h0, h1
FCVTNU 00, 00
FCVTNU v0.8h, v2.8h
FCVTNU v0.4s, v2.4s
FCVTNU w0, h1
FCVTNU x0, h1
FCVTNU w0, s1
FCVTNU x0, s1
FCVTNU w0, d1
FCVTNU x0, d1
FCVTNU s0, h1
FCVTNU d0, h1
FCVTNU d0, s1
FCVTNU s0, d1
FCVTPS h0, h1
FCVTPS 00, 00
FCVTPS v0.8h, v2.8h
FCVTPS v0.4s, v2.4s
FCVTPS w0, h1
FCVTPS x0, h1
FCVTPS w0, s1
FCVTPS x0, s1
FCVTPS w0, d1
FCVTPS x0, d1
FCVTPS s0, h1
FCVTPS d0, h1
FCVTPS d0, s1
FCVTPS s0, d1
FCVTPU h0, h1
FCVTPU 00, 00
FCVTPU v0.8h, v2.8h
FCVTPU v0.4s, v2.4s
FCVTPU w0, h1
FCVTPU x0, h1
FCVTPU w0, s1
FCVTPU x0, s1
FCVTPU w0, d1
FCVTPU x0, d1
FCVTPU s0, h1
FCVTPU d0, h1
FCVTPU d0, s1
FCVTPU s0, d1
FCVTXN S0, D0
FCVTXN0 v1.4s, v3.2D
FCVTZS 00, 00, #0
FCVTZS v0.4s, v2.4s, #0
FCVTZS h0, h1
FCVTZS 00, 00
FCVTZS v0.8h, v2.8h
FCVTZS v0.4s, v2.4s
FCVTZS w0, h1, #0
FCVTZS x0, h1, #0
FCVTZS w0, s1, #0
FCVTZS x0, s1, #0
FCVTZS w0, d1, #0
FCVTZS x0, d1, #0
FCVTZS w0, h1
FCVTZS x0, h1
FCVTZS w0, s1
FCVTZS x0, s1
FCVTZS w0, d1
FCVTZS x0, d1
FCVTZS s0, h1
FCVTZS d0, h1
FCVTZS d0, s1
FCVTZS s0, d1
FCVTZU 00, 00, #0
FCVTZU v0.4s, v2.4s, #0
FCVTZU h0, h1
FCVTZU 00, 00
FCVTZU v0.8h, v2.8h
FCVTZU v0.4s, v2.4s
FCVTZU w0, h1, #0
FCVTZU x0, h1, #0
FCVTZU w0, s1, #0
FCVTZU x0, s1, #0
FCVTZU w0, d1, #0
FCVTZU x0, d1, #0
FCVTZU w0, h1
FCVTZU x0, h1
FCVTZU w0, s1
FCVTZU x0, s1
FCVTZU w0, d1
FCVTZU x0, d1
FCVTZU s0, h1
FCVTZU d0, h1
FCVTZU d0, s1
FCVTZU s0, d1
FDIV v0.8h, v2.8h, v4.8h
FDIV v0.4s, v2.4s, v4.4s
FDIV h0, h1, h2
FDIV s0, s1, s2
FDIV d0, d1, d2
FDOT v0.4s, v2.4s, v4.2B[0]
FDOT v0.4s, v2.4s, v4.4s
FDOT v0.4s, v2.4s, v4.4B[0]
FDOT v0.4s, v2.4s, v4.4s
FDOT v0.4s, v2.4s, v4.2H[0]
FDOT v0.4s, v2.4s, v4.4s
FJCVTZS w0, d1
FMADD h0, h1, h2, h3
FMADD s0, s1, s2, 0
FMADD d0, d1, d2, 0
FMAX v0.8h, v2.8h, v4.8h
FMAX v0.4s, v2.4s, v4.4s
FMAX h0, h1, h2
FMAX s0, s1, s2
FMAX d0, d1, d2
FMAXNM v0.8h, v2.8h, v4.8h
FMAXNM v0.4s, v2.4s, v4.4s
FMAXNM h0, h1, h2
FMAXNM s0, s1, s2
FMAXNM d0, d1, d2
FMAXNMP H0, v1.2H
FMAXNMP 00, v2.4s
FMAXNMP v0.8h, v2.8h, v4.8h
FMAXNMP v0.4s, v2.4s, v4.4s
FMAXNMV 00, v2.8h
FMAXNMV S0, v1.4S
FMAXP H0, v1.2H
FMAXP 00, v2.4s
FMAXP v0.8h, v2.8h, v4.8h
FMAXP v0.4s, v2.4s, v4.4s
FMAXV 00, v2.8h
FMAXV S0, v1.4S
FMIN v0.8h, v2.8h, v4.8h
FMIN v0.4s, v2.4s, v4.4s
FMIN h0, h1, h2
FMIN s0, s1, s2
FMIN d0, d1, d2
FMINNM v0.8h, v2.8h, v4.8h
FMINNM v0.4s, v2.4s, v4.4s
FMINNM h0, h1, h2
FMINNM s0, s1, s2
FMINNM d0, d1, d2
FMINNMP H0, v1.2H
FMINNMP 00, v2.4s
FMINNMP v0.8h, v2.8h, v4.8h
FMINNMP v0.4s, v2.4s, v4.4s
FMINNMV 00, v2.8h
FMINNMV S0, v1.4S
FMINP H0, v1.2H
FMINP 00, v2.4s
FMINP v0.8h, v2.8h, v4.8h
FMINP v0.4s, v2.4s, v4.4s
FMINV 00, v2.8h
FMINV S0, v1.4S
FMLA h0, h1, v2.H[0]
FMLA 00, 00, v4.0[0]
FMLA v0.8h, v2.8h, v4.H[0]
FMLA v0.4s, v2.4s, v4.0[0]
FMLA v0.8h, v2.8h, v4.8h
FMLA v0.4s, v2.4s, v4.4s
FMLAL v0.4s, v2.4s, v4.H[0]
FMLAL2 v0.4s, v2.4s, v4.H[0]
FMLAL v0.4s, v2.4s, v4.4s
FMLAL2 v0.4s, v2.4s, v4.4s
FMLALB v0.8H, v1.16B, v2.B[0]
FMLALT v0.8H, v1.16B, v2.B[0]
FMLALB v0.8H, v1.16B, v2.16B
FMLALT v0.8H, v1.16B, v2.16B
FMLALLBB v0.4S, v1.16B, v2.B[0]
FMLALLBT v0.4S, v1.16B, v2.B[0]
FMLALLTB v0.4S, v1.16B, v2.B[0]
FMLALLTT v0.4S, v1.16B, v2.B[0]
FMLALLBB v0.4S, v1.16B, v2.16B
FMLALLBT v0.4S, v1.16B, v2.16B
FMLALLTB v0.4S, v1.16B, v2.16B
FMLALLTT v0.4S, v1.16B, v2.16B
FMLS h0, h1, v2.H[0]
FMLS 00, 00, v4.0[0]
FMLS v0.8h, v2.8h, v4.H[0]
FMLS v0.4s, v2.4s, v4.0[0]
FMLS v0.8h, v2.8h, v4.8h
FMLS v0.4s, v2.4s, v4.4s
FMLSL v0.4s, v2.4s, v4.H[0]
FMLSL2 v0.4s, v2.4s, v4.H[0]
FMLSL v0.4s, v2.4s, v4.4s
FMLSL2 v0.4s, v2.4s, v4.4s
FMMLA v0.8H, v1.8H, v2.8H
FMMLA v0.4S, v1.8H, v2.8H
FMMLA v0.8H, v1.16B, v2.16B
FMMLA v0.4S, v1.16B, v2.16B
FMOV v0.8h, #0
FMOV v0.4s, #0
FMOV v0.2D, #0
FMOV h0, h1
FMOV s0, s1
FMOV d0, d1
FMOV w0, h1
FMOV x0, h1
FMOV h0, w1
FMOV s0, w1
FMOV w0, s1
FMOV h0, x1
FMOV d0, x1
FMOV v0.D[1], x1
FMOV x0, d1
FMOV x0, v1.D[1]
FMOV h0, #0
FMOV s0, #0
FMOV d0, #0
FMSUB h0, h1, h2, h3
FMSUB s0, s1, s2, 0
FMSUB d0, d1, d2, 0
FMUL h0, h1, v2.H[0]
FMUL 00, 00, v4.0[0]
FMUL v0.8h, v2.8h, v4.H[0]
FMUL v0.4s, v2.4s, v4.0[0]
FMUL v0.8h, v2.8h, v4.8h
FMUL v0.4s, v2.4s, v4.4s
FMUL h0, h1, h2
FMUL s0, s1, s2
FMUL d0, d1, d2
FMULX h0, h1, v2.H[0]
FMULX 00, 00, v4.0[0]
FMULX v0.8h, v2.8h, v4.H[0]
FMULX v0.4s, v2.4s, v4.0[0]
FMULX h0, h1, h2
FMULX 00, 00, 00
FMULX v0.8h, v2.8h, v4.8h
FMULX v0.4s, v2.4s, v4.4s
FNEG v0.8h, v2.8h
FNEG v0.4s, v2.4s
FNEG h0, h1
FNEG s0, s1
FNEG d0, d1
FNMADD h0, h1, h2, h3
FNMADD s0, s1, s2, 0
FNMADD d0, d1, d2, 0
FNMSUB h0, h1, h2, h3
FNMSUB s0, s1, s2, 0
FNMSUB d0, d1, d2, 0
FNMUL h0, h1, h2
FNMUL s0, s1, s2
FNMUL d0, d1, d2
FRECPE h0, h1
FRECPE 00, 00
FRECPE v0.8h, v2.8h
FRECPE v0.4s, v2.4s
FRECPS h0, h1, h2
FRECPS 00, 00, 00
FRECPS v0.8h, v2.8h, v4.8h
FRECPS v0.4s, v2.4s, v4.4s
FRECPX h0, h1
FRECPX 00, 00
FRINT32X v0.4s, v2.4s
FRINT32X s0, s1
FRINT32X d0, d1
FRINT32Z v0.4s, v2.4s
FRINT32Z s0, s1
FRINT32Z d0, d1
FRINT64X v0.4s, v2.4s
FRINT64X s0, s1
FRINT64X d0, d1
FRINT64Z v0.4s, v2.4s
FRINT64Z s0, s1
FRINT64Z d0, d1
FRINTA v0.8h, v2.8h
FRINTA v0.4s, v2.4s
FRINTA h0, h1
FRINTA s0, s1
FRINTA d0, d1
FRINTI v0.8h, v2.8h
FRINTI v0.4s, v2.4s
FRINTI h0, h1
FRINTI s0, s1
FRINTI d0, d1
FRINTM v0.8h, v2.8h
FRINTM v0.4s, v2.4s
FRINTM h0, h1
FRINTM s0, s1
FRINTM d0, d1
FRINTN v0.8h, v2.8h
FRINTN v0.4s, v2.4s
FRINTN h0, h1
FRINTN s0, s1
FRINTN d0, d1
FRINTP v0.8h, v2.8h
FRINTP v0.4s, v2.4s
FRINTP h0, h1
FRINTP s0, s1
FRINTP d0, d1
FRINTX v0.8h, v2.8h
FRINTX v0.4s, v2.4s
FRINTX h0, h1
FRINTX s0, s1
FRINTX d0, d1
FRINTZ v0.8h, v2.8h
FRINTZ v0.4s, v2.4s
FRINTZ h0, h1
FRINTZ s0, s1
FRINTZ d0, d1
FRSQRTE h0, h1
FRSQRTE 00, 00
FRSQRTE v0.8h, v2.8h
FRSQRTE v0.4s, v2.4s
FRSQRTS h0, h1, h2
FRSQRTS 00, 00, 00
FRSQRTS v0.8h, v2.8h, v4.8h
FRSQRTS v0.4s, v2.4s, v4.4s
FSCALE v0.8h, v2.8h, v4.8h
FSCALE v0.4s, v2.4s, v4.4s
FSQRT v0.8h, v2.8h
FSQRT v0.4s, v2.4s
FSQRT h0, h1
FSQRT s0, s1
FSQRT d0, d1
FSUB v0.8h, v2.8h, v4.8h
FSUB v0.4s, v2.4s, v4.4s
FSUB h0, h1, h2
FSUB s0, s1, s2
FSUB d0, d1, d2
GCSB DSYNC
GCSPOPCX
GCSPOPM x0
GCSPOPX
GCSPUSHM x0
GCSPUSHX
GCSSS1 x0
GCSSS2 x0
GCSSTR x0, [sp]
GCSSTTR x0, [sp]
GIC 0, x1
GICR x0, 0
GMI x0, sp, x2
GSB 0
HINT #0
HLT #0
HVC #0
IC 0, x1
INS v0.0[0], v3.0[0]
INS v0.0[0], 00
IRG sp, sp, x2
ISB sy|#0
LD1 v0.4s, [sp]
LD1 v0.4s, v2.4s, [sp]
LD1 v0.4s, v2.4s, v4.4s, [sp]
LD1 v0.4s, v2.4s, v4.4s, v5.4s, [sp]
LD1 v0.4s, [sp], 0
LD1 v0.4s, [sp], x3
LD1 v0.4s, v2.4s, [sp], 0
LD1 v0.4s, v2.4s, [sp], x5
LD1 v0.4s, v2.4s, v4.4s, [sp], 0
LD1 v0.4s, v2.4s, v4.4s, [sp], x5
LD1 v0.4s, v2.4s, v4.4s, v5.4s, [sp], 0
LD1 v0.4s, v2.4s, v4.4s, v5.4s, [sp], x5
LD1 v0.B [0], [sp]
LD1 v0.H [0], [sp]
LD1 v0.S [0], [sp]
LD1 v0.D [0], [sp]
LD1 v0.B [0], [sp], #1
LD1 v0.B [0], [sp], x3
LD1 v0.D [0], [sp], #8
LD1 v0.D [0], [sp], x3
LD1 v0.H [0], [sp], #2
LD1 v0.H [0], [sp], x3
LD1 v0.S [0], [sp], #4
LD1 v0.S [0], [sp], x3
LD1R v0.4s, [sp]
LD1R v0.4s, [sp], 0
LD1R v0.4s, [sp], x3
LD2 v0.4s, v2.4s, [sp]
LD2 v0.4s, v2.4s, [sp], 0
LD2 v0.4s, v2.4s, [sp], x5
LD2 v0.B, v1.B [0], [sp]
LD2 v0.H, v1.H [0], [sp]
LD2 v0.S, v1.S [0], [sp]
LD2 v0.D, v1.D [0], [sp]
LD2 v0.B, v1.B [0], [sp], #2
LD2 v0.B, v1.B [0], [sp], x4
LD2 v0.H, v1.H [0], [sp], #4
LD2 v0.H, v1.H [0], [sp], x4
LD2 v0.S, v1.S [0], [sp], #8
LD2 v0.S, v1.S [0], [sp], x4
LD2 v0.D, v1.D [0], [sp], #16
LD2 v0.D, v1.D [0], [sp], x4
LD2R v0.4s, v2.4s, [sp]
LD2R v0.4s, v2.4s, [sp], 0
LD2R v0.4s, v2.4s, [sp], x5
LD3 v0.4s, v2.4s, v4.4s, [sp]
LD3 v0.4s, v2.4s, v4.4s, [sp], 0
LD3 v0.4s, v2.4s, v4.4s, [sp], x5
LD3 v0.B, v1.B, v2.B [0], [sp]
LD3 v0.H, v1.H, v2.H [0], [sp]
LD3 v0.S, v1.S, v2.S [0], [sp]
LD3 v0.D, v1.D, v2.D [0], [sp]
LD3 v0.B, v1.B, v2.B [0], [sp], #3
LD3 v0.B, v1.B, v2.B [0], [sp], x5
LD3 v0.H, v1.H, v2.H [0], [sp], #6
LD3 v0.H, v1.H, v2.H [0], [sp], x5
LD3 v0.S, v1.S, v2.S [0], [sp], #12
LD3 v0.S, v1.S, v2.S [0], [sp], x5
LD3 v0.D, v1.D, v2.D [0], [sp], #24
LD3 v0.D, v1.D, v2.D [0], [sp], x5
LD3R v0.4s, v2.4s, v4.4s, [sp]
LD3R v0.4s, v2.4s, v4.4s, [sp], 0
LD3R v0.4s, v2.4s, v4.4s, [sp], x5
LD4 v0.4s, v2.4s, v4.4s, v5.4s, [sp]
LD4 v0.4s, v2.4s, v4.4s, v5.4s, [sp], 0
LD4 v0.4s, v2.4s, v4.4s, v5.4s, [sp], x5
LD4 v0.B, v1.B, v2.B, v3.B [0], [sp]
LD4 v0.H, v1.H, v2.H, v3.H [0], [sp]
LD4 v0.S, v1.S, v2.S, v3.S [0], [sp]
LD4 v0.D, v1.D, v2.D, v3.D [0], [sp]
LD4 v0.B, v1.B, v2.B, v3.B [0], [sp], #4
LD4 v0.B, v1.B, v2.B, v3.B [0], [sp], x5
LD4 v0.H, v1.H, v2.H, v3.H [0], [sp], #8
LD4 v0.H, v1.H, v2.H, v3.H [0], [sp], x5
LD4 v0.S, v1.S, v2.S, v3.S [0], [sp], #16
LD4 v0.S, v1.S, v2.S, v3.S [0], [sp], x5
LD4 v0.D, v1.D, v2.D, v3.D [0], [sp], #32
LD4 v0.D, v1.D, v2.D, v3.D [0], [sp], x5
LD4R v0.4s, v2.4s, v4.4s, v5.4s, [sp]
LD4R v0.4s, v2.4s, v4.4s, v5.4s, [sp], 0
LD4R v0.4s, v2.4s, v4.4s, v5.4s, [sp], x5
LD64B x0, [sp, #0]
LDADD w0, w1, [sp]
LDADDA w0, w1, [sp]
LDADDAL w0, w1, [sp]
LDADDL w0, w1, [sp]
LDADD x0, x1, [sp]
LDADDA x0, x1, [sp]
LDADDAL x0, x1, [sp]
LDADDL x0, x1, [sp]
LDADDB w0, w1, [sp]
LDADDAB w0, w1, [sp]
LDADDALB w0, w1, [sp]
LDADDLB w0, w1, [sp]
LDADDH w0, w1, [sp]
LDADDAH w0, w1, [sp]
