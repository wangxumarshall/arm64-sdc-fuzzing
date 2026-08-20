.arch armv8-a
.text
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
FMLS h0, h1, v2.H[0]
FMLS 00, 00, v4.0[0]
FMLS v0.8h, v2.8h, v4.H[0]
FMLS v0.4s, v2.4s, v4.0[0]
FMLS v0.8h, v2.8h, v4.8h
FMLS v0.4s, v2.4s, v4.4s
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
LDAP1 v0.D [0], [sp]
LDAP x0, x1, [sp, #0]
LDAPP x0, x1, [sp, #0]
LDAPR w0, [sp], #4
LDAPR x0, [sp], #8
LDAPR w0, [sp, #0]
LDAPR x0, [sp, #0]
LDAPRB w0, [sp, #0]
LDAPRH w0, [sp, #0]
LDAPUR w0, [sp, #0]
LDAPUR x0, [sp, #0]
LDAPURB w0, [sp, #0]
LDAPURH w0, [sp, #0]
LDAPURSB w0, [sp, #0]
LDAPURSB x0, [sp, #0]
LDAPURSH w0, [sp, #0]
LDAPURSH x0, [sp, #0]
LDAPURSW x0, [sp, #0]
LDAR w0, [sp, #0]
LDAR x0, [sp, #0]
LDARB w0, [sp, #0]
LDARH w0, [sp, #0]
LDATXR w0, [sp, #0]
LDATXR x0, [sp, #0]
LDAXP w0, w1, [sp, #0]
LDAXP x0, x1, [sp, #0]
LDAXR w0, [sp, #0]
LDAXR x0, [sp, #0]
LDAXRB w0, [sp, #0]
LDAXRH w0, [sp, #0]
LDG x0, [sp, #0]
LDGM x0, [sp]
LDIAPP w0, w1, [sp], #8
LDIAPP w0, w1, [sp]
LDIAPP x0, x1, [sp], #16
LDIAPP x0, x1, [sp]
LDLAR w0, [sp, #0]
LDLAR x0, [sp, #0]
LDLARB w0, [sp, #0]
LDLARH w0, [sp, #0]
LDNP w0, w1, [sp, #0]
LDNP x0, x1, [sp, #0]
LDP w0, w1, [sp], #0
LDP x0, x1, [sp], #0
LDP w0, w1, [sp, #0]!
LDP x0, x1, [sp, #0]!
LDP w0, w1, [sp, #0]
LDP x0, x1, [sp, #0]
LDPSW x0, x1, [sp], #0
LDPSW x0, x1, [sp, #0]!
LDPSW x0, x1, [sp, #0]
LDR w0, [sp], #0
LDR x0, [sp], #0
LDR w0, [sp, #0]!
LDR x0, [sp, #0]!
LDR w0, [sp, #0]
LDR x0, [sp, #0]
LDR w0, .Lmicroprobe_catalog_target
LDR x0, .Lmicroprobe_catalog_target
LDR w0, [sp, w2, uxtx 0]
LDR x0, [sp, w2, uxtx 0]
LDRB w0, [sp], #0
LDRB w0, [sp, #0]!
LDRB w0, [sp, #0]
LDRB w0, [sp, w2, uxtx 0]
LDRB w0, [sp, x2, LSL 0]
LDRH w0, [sp], #0
LDRH w0, [sp, #0]!
LDRH w0, [sp, #0]
LDRH w0, [sp, w2, uxtx 0]
LDRSB w0, [sp], #0
LDRSB x0, [sp], #0
LDRSB w0, [sp, #0]!
LDRSB x0, [sp, #0]!
LDRSB w0, [sp, #0]
LDRSB x0, [sp, #0]
LDRSB w0, [sp, w2, uxtx 0]
LDRSB w0, [sp, x2, LSL 0]
LDRSB x0, [sp, w2, uxtx 0]
LDRSB x0, [sp, x2, LSL 0]
LDRSH w0, [sp], #0
LDRSH x0, [sp], #0
LDRSH w0, [sp, #0]!
LDRSH x0, [sp, #0]!
LDRSH w0, [sp, #0]
LDRSH x0, [sp, #0]
LDRSH w0, [sp, w2, uxtx 0]
LDRSH x0, [sp, w2, uxtx 0]
LDRSW x0, [sp], #0
LDRSW x0, [sp, #0]!
LDRSW x0, [sp, #0]
LDRSW x0, .Lmicroprobe_catalog_target
LDRSW x0, [sp, w2, uxtx 0]
LDTNP x0, x1, [sp, #0]
LDTP x0, x1, [sp], #0
LDTP x0, x1, [sp, #0]!
LDTP x0, x1, [sp, #0]
LDTR w0, [sp, #0]
LDTR x0, [sp, #0]
LDTRB w0, [sp, #0]
LDTRH w0, [sp, #0]
LDTRSB w0, [sp, #0]
LDTRSB x0, [sp, #0]
LDTRSH w0, [sp, #0]
LDTRSH x0, [sp, #0]
LDTRSW x0, [sp, #0]
LDTXR w0, [sp, #0]
LDTXR x0, [sp, #0]
LDUR w0, [sp, #0]
LDUR x0, [sp, #0]
LDURB w0, [sp, #0]
LDURH w0, [sp, #0]
LDURSB w0, [sp, #0]
LDURSB x0, [sp, #0]
LDURSH w0, [sp, #0]
LDURSH x0, [sp, #0]
LDURSW x0, [sp, #0]
LDXP w0, w1, [sp, #0]
LDXP x0, x1, [sp, #0]
LDXR w0, [sp, #0]
LDXR x0, [sp, #0]
LDXRB w0, [sp, #0]
LDXRH w0, [sp, #0]
LSL w0, w1, w2
LSL x0, x1, x2
LSL w0, w1, #lsl
LSL x0, x1, #lsl
LSLV w0, w1, w2
LSLV x0, x1, x2
LSR w0, w1, w2
LSR x0, x1, x2
LSR w0, w1, #lsl
LSR x0, x1, #lsl
LSRV w0, w1, w2
LSRV x0, x1, x2
LUTI2 v0.16B, v1.16B, v2[0]
LUTI2 v0.8H, v1.8H, v2[0]
LUTI4 v0.16B, v1.16B, v2[0]
LUTI4 v0.8H, v1.8H, v2.8H, v3[0]
MADD w0, w1, w2, w3
MADD x0, x1, x2, x3
MADDPT x0, x1, x2, x3
MLA v0.4s, v2.4s, V0.0[0]
MLA v0.4s, v2.4s, v4.4s
MLBI 0, x1
MLS v0.4s, v2.4s, V0.0[0]
MLS v0.4s, v2.4s, v4.4s
MNEG w0, w1, w2
MNEG x0, x1, x2
MOV sp, sp
MOV sp, sp
MOV 00, v2.4s[0]
MOV v0.0[0], v3.0[0]
MOV v0.0[0], 00
MOV w0, #0
MOV x0, #0
MOV w0, #0
MOV x0, #0
MOV v0.4s, v2.4s
MOV sp, #0
MOV sp, #0
MOV w0, w1
MOV x0, x1
MOV w0, v1.S[0]
MOV x0, v1.D[0]
MOVI v0.4s, #0, LSL #0
MOVI v0.4s, #0, LSL #0
MOVI v0.4s, #0, LSL #0
MOVI v0.4s, #0, MSL #0
MOVI d0, #0
MOVI v0.2D, #0
MOVK w0, #0, LSL #lsl
MOVK x0, #0, LSL #lsl
MOVN w0, #0, LSL #lsl
MOVN x0, #0, LSL #lsl
MOVZ w0, #0, LSL #lsl
MOVZ x0, #0, LSL #lsl
MRRS x0, x1, nzcv
MRS x0, nzcv
MSR s0, #0
MSR nzcv, x5
MSRR nzcv, x5, x5
MSUB w0, w1, w2, w3
MSUB x0, x1, x2, x3
MSUBPT x0, x1, x2, x3
MUL v0.4s, v2.4s, V0.0[0]
MUL v0.4s, v2.4s, v4.4s
MUL w0, w1, w2
MUL x0, x1, x2
MVN v0.4s, v2.4s
MVN w0, w1, lsl #0
MVN x0, x1, lsl #0
MVNI v0.4s, #0, LSL #0
MVNI v0.4s, #0, LSL #0
MVNI v0.4s, #0, MSL #0
NEG D0, D0
NEG v0.4s, v2.4s
NEG w0, w1, lsl #0
NEG x0, x1, lsl #0
NEGS w0, w1, lsl #0
NEGS x0, x1, lsl #0
NGC w0, w1
NGC x0, x1
NGCS w0, w1
NGCS x0, x1
NOP
NOT v0.4s, v2.4s
ORN v0.4s, v2.4s, v4.4s
ORN w0, w1, w2, lsl #0
ORN x0, x1, x2, lsl #0
ORR v0.4s, #0, LSL #0
ORR v0.4s, #0, LSL #0
ORR v0.4s, v2.4s, v4.4s
ORR sp, w1, #0
ORR sp, x1, #0
ORR w0, w1, w2, lsl #0
ORR x0, x1, x2, lsl #0
PACGA x0, x1, sp
PACIA171615
PACIASPPC
PACIB171615
PACIBSPPC
PACM
PACNBIASPPC
PACNBIBSPPC
PMUL v0.4s, v2.4s, v4.4s
PMULL0 v1.4s, v3.4s, v5.4s
PRFM pldl1keep, [sp, #0]
PRFM pldl1keep, .Lmicroprobe_catalog_target
PRFM pldl1keep, [sp, w3, uxtx 0]
PRFUM pldl1keep, [sp, #0]
PSB CSYNC
PSSBB
RADDHN0 v1.4s, v3.4s, v5.4s
.Lmicroprobe_catalog_target:
nop
