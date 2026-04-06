.arch armv8-a
.text
RAX1 v0.2D, v1.2D, v2.2D
RBIT v0.4s, v2.4s
RBIT w0, w1
RBIT x0, x1
RET x0
REV w0, w1
REV x0, x1
REV16 v0.4s, v2.4s
REV16 w0, w1
REV16 x0, x1
REV32 v0.4s, v2.4s
REV32 x0, x1
REV64 v0.4s, v2.4s
REV64 x0, x1
RMIF x0, #lsl, #0
ROR w0, w1, #lsl
ROR x0, x1, #lsl
ROR w0, w1, w2
ROR x0, x1, x2
RORV w0, w1, w2
RORV x0, x1, x2
RPRFM pldl1keep, x2, [sp]
RSHRN0 v1.4s, v3.4s, #lsl
RSUBHN0 v1.4s, v3.4s, v5.4s
SABA v0.4s, v2.4s, v4.4s
SABAL0 v1.4s, v3.4s, v5.4s
SABD v0.4s, v2.4s, v4.4s
SABDL0 v1.4s, v3.4s, v5.4s
SADALP v0.4s, v2.4s
SADDL0 v1.4s, v3.4s, v5.4s
SADDLP v0.4s, v2.4s
SADDLV 00, v2.4s
SADDW0 v1.4s, v3.4s, v5.4s
SB
SBC w0, w1, w2
SBC x0, x1, x2
SBCS w0, w1, w2
SBCS x0, x1, x2
SBFIZ w0, w1, #0, #0
SBFIZ x0, x1, #0, #0
SBFM w0, w1, #0, #0
SBFM x0, x1, #0, #0
SBFX w0, w1, #0, #0
SBFX x0, x1, #0, #0
SCVTF 00, 00, #0
SCVTF v0.4s, v2.4s, #0
SCVTF h0, h1
SCVTF 00, 00
SCVTF v0.8h, v2.8h
SCVTF v0.4s, v2.4s
SCVTF h0, w1, #0
SCVTF h0, x1, #0
SCVTF s0, w1, #0
SCVTF s0, x1, #0
SCVTF d0, w1, #0
SCVTF d0, x1, #0
SCVTF h0, w1
SCVTF s0, w1
SCVTF d0, w1
SCVTF h0, x1
SCVTF s0, x1
SCVTF d0, x1
SCVTF h0, s1
SCVTF d0, s1
SCVTF h0, d1
SCVTF s0, d1
SDIV w0, w1, w2
SDIV x0, x1, x2
SDOT v0.4s, v2.4s, v4.4B[0]
SDOT v0.4s, v2.4s, v4.4s
SEV
SEVL
SHA1C 0, s1, v2.4S
SHA1H s0, s1
SHA1M 0, s1, v2.4S
SHA1P 0, s1, v2.4S
SHA1SU0 v0.4S, v1.4S, v2.4S
SHA1SU1 v0.4S, v1.4S
SHA256H2 0, 0, v2.4S
SHA256H 0, 0, v2.4S
SHA256SU0 v0.4S, v1.4S
SHA256SU1 v0.4S, v1.4S, v2.4S
SHA512H2 0, 0, v2.2D
SHA512H 0, 0, v2.2D
SHA512SU0 v0.2D, v1.2D
SHA512SU1 v0.2D, v1.2D, v2.2D
SHADD v0.4s, v2.4s, v4.4s
SHL D0, D0, #lsl
SHL v0.4s, v2.4s, #lsl
SHLL0 v1.4s, v3.4s, #lsl
SHRN0 v1.4s, v3.4s, #lsl
SHSUB v0.4s, v2.4s, v4.4s
SHUH 0
SLI D0, D0, #lsl
SLI v0.4s, v2.4s, #lsl
SM3PARTW1 v0.4S, v1.4S, v2.4S
SM3PARTW2 v0.4S, v1.4S, v2.4S
SM3SS1 v0.4S, v1.4S, v2.4S, v3.4S
SM3TT1A v0.4S, v1.4S, v2.S[0]
SM3TT1B v0.4S, v1.4S, v2.S[0]
SM3TT2A v0.4S, v1.4S, v2.S[0]
SM3TT2B v0.4S, v1.4S, v2.S[0]
SM4E v0.4S, v1.4S
SM4EKEY v0.4S, v1.4S, v2.4S
SMADDL x0, w1, w2, x3
SMAX v0.4s, v2.4s, v4.4s
SMAX w0, w1, #0
SMAX x0, x1, #0
SMAX w0, w1, w2
SMAX x0, x1, x2
SMAXP v0.4s, v2.4s, v4.4s
SMAXV 00, v2.4s
SMC #0
SMIN v0.4s, v2.4s, v4.4s
SMIN w0, w1, #0
SMIN x0, x1, #0
SMIN w0, w1, w2
SMIN x0, x1, x2
SMINP v0.4s, v2.4s, v4.4s
SMINV 00, v2.4s
SMLAL0 v1.4s, v3.4s, V0.0[0]
SMLAL0 v1.4s, v3.4s, v5.4s
SMLSL0 v1.4s, v3.4s, V0.0[0]
SMLSL0 v1.4s, v3.4s, v5.4s
SMMLA v0.4S, v1.16B, v2.16B
SMNEGL x0, w1, w2
SMOV w0, v1.0[0]
SMOV x0, v1.0[0]
SMSTART 0
SMSTOP 0
SMSUBL x0, w1, w2, x3
SMULH x0, x1, x2
SMULL0 v1.4s, v3.4s, V0.0[0]
SMULL0 v1.4s, v3.4s, v5.4s
SMULL x0, w1, w2
SQABS 00, 00
SQABS v0.4s, v2.4s
SQADD 00, 00, 00
SQADD v0.4s, v2.4s, v4.4s
SQDMLAL v00, 00, V0.0[0]
SQDMLAL0 v1.4s, v3.4s, V0.0[0]
SQDMLAL v00, 00, 00
SQDMLAL0 v1.4s, v3.4s, v5.4s
SQDMLSL v00, 00, V0.0[0]
SQDMLSL0 v1.4s, v3.4s, V0.0[0]
SQDMLSL v00, 00, 00
SQDMLSL0 v1.4s, v3.4s, v5.4s
SQDMULH 00, 00, V0.0[0]
SQDMULH v0.4s, v2.4s, V0.0[0]
SQDMULH 00, 00, 00
SQDMULH v0.4s, v2.4s, v4.4s
SQDMULL0 v1.4s, v3.4s, V0.0[0]
SQDMULL v00, 00, V0.0[0]
SQDMULL v00, 00, 00
SQDMULL0 v1.4s, v3.4s, v5.4s
SQNEG 00, 00
SQNEG v0.4s, v2.4s
SQRDMLAH 00, 00, V0.0[0]
SQRDMLAH v0.4s, v2.4s, V0.0[0]
SQRDMLAH 00, 00, 00
SQRDMLAH v0.4s, v2.4s, v4.4s
SQRDMLSH 00, 00, V0.0[0]
SQRDMLSH v0.4s, v2.4s, V0.0[0]
SQRDMLSH 00, 00, 00
SQRDMLSH v0.4s, v2.4s, v4.4s
SQRDMULH 00, 00, V0.0[0]
SQRDMULH v0.4s, v2.4s, V0.0[0]
SQRDMULH 00, 00, 00
SQRDMULH v0.4s, v2.4s, v4.4s
SQRSHL 00, 00, 00
SQRSHL v0.4s, v2.4s, v4.4s
SQRSHRN 00, v20, #lsl
SQRSHRN0 v1.4s, v3.4s, #lsl
SQRSHRUN 00, v20, #lsl
SQRSHRUN0 v1.4s, v3.4s, #lsl
SQSHL 00, 00, #lsl
SQSHL v0.4s, v2.4s, #lsl
SQSHL 00, 00, 00
SQSHL v0.4s, v2.4s, v4.4s
SQSHLU 00, 00, #lsl
SQSHLU v0.4s, v2.4s, #lsl
SQSHRN 00, v20, #lsl
SQSHRN0 v1.4s, v3.4s, #lsl
SQSHRUN 00, v20, #lsl
SQSHRUN0 v1.4s, v3.4s, #lsl
SQSUB 00, 00, 00
SQSUB v0.4s, v2.4s, v4.4s
SQXTN 00, v20
SQXTN0 v1.4s, v3.4s
SQXTUN 00, v20
SQXTUN0 v1.4s, v3.4s
SRHADD v0.4s, v2.4s, v4.4s
SRI D0, D0, #lsl
SRI v0.4s, v2.4s, #lsl
SRSHL D0, D0, D0
SRSHL v0.4s, v2.4s, v4.4s
SRSHR D0, D0, #lsl
SRSHR v0.4s, v2.4s, #lsl
SRSRA D0, D0, #lsl
SRSRA v0.4s, v2.4s, #lsl
SSBB
SSHL D0, D0, D0
SSHL v0.4s, v2.4s, v4.4s
SSHLL0 v1.4s, v3.4s, #lsl
SSHR D0, D0, #lsl
SSHR v0.4s, v2.4s, #lsl
SSRA D0, D0, #lsl
SSRA v0.4s, v2.4s, #lsl
SSUBL0 v1.4s, v3.4s, v5.4s
SSUBW0 v1.4s, v3.4s, v5.4s
ST1 v0.4s, [sp]
ST1 v0.4s, v2.4s, [sp]
ST1 v0.4s, v2.4s, v4.4s, [sp]
ST1 v0.4s, v2.4s, v4.4s, v5.4s, [sp]
ST1 v0.4s, [sp], 0
ST1 v0.4s, [sp], x3
ST1 v0.4s, v2.4s, [sp], 0
ST1 v0.4s, v2.4s, [sp], x5
ST1 v0.4s, v2.4s, v4.4s, [sp], 0
ST1 v0.4s, v2.4s, v4.4s, [sp], x5
ST1 v0.4s, v2.4s, v4.4s, v5.4s, [sp], 0
ST1 v0.4s, v2.4s, v4.4s, v5.4s, [sp], x5
ST1 v0.B [0], [sp]
ST1 v0.H [0], [sp]
ST1 v0.S [0], [sp]
ST1 v0.D [0], [sp]
ST1 v0.B [0], [sp], #1
ST1 v0.B [0], [sp], x3
ST1 v0.H [0], [sp], #2
ST1 v0.H [0], [sp], x3
ST1 v0.S [0], [sp], #4
ST1 v0.S [0], [sp], x3
ST1 v0.D [0], [sp], #8
ST1 v0.D [0], [sp], x3
ST2 v0.4s, v2.4s, [sp]
ST2 v0.4s, v2.4s, [sp], 0
ST2 v0.4s, v2.4s, [sp], x5
ST2 v0.B, v1.B [0], [sp]
ST2 v0.H, v1.H [0], [sp]
ST2 v0.S, v1.S [0], [sp]
ST2 v0.D, v1.D [0], [sp]
ST2 v0.B, v1.B [0], [sp], #2
ST2 v0.B, v1.B [0], [sp], x4
ST2 v0.H, v1.H [0], [sp], #4
ST2 v0.H, v1.H [0], [sp], x4
ST2 v0.S, v1.S [0], [sp], #8
ST2 v0.S, v1.S [0], [sp], x4
ST2 v0.D, v1.D [0], [sp], #16
ST2 v0.D, v1.D [0], [sp], x4
ST2G sp, [sp], #0
ST2G sp, [sp, #0]!
ST2G sp, [sp, #0]
ST3 v0.4s, v2.4s, v4.4s, [sp]
ST3 v0.4s, v2.4s, v4.4s, [sp], 0
ST3 v0.4s, v2.4s, v4.4s, [sp], x5
ST3 v0.B, v1.B, v2.B [0], [sp]
ST3 v0.H, v1.H, v2.H [0], [sp]
ST3 v0.S, v1.S, v2.S [0], [sp]
ST3 v0.D, v1.D, v2.D [0], [sp]
ST3 v0.B, v1.B, v2.B [0], [sp], #3
ST3 v0.B, v1.B, v2.B [0], [sp], x5
ST3 v0.H, v1.H, v2.H [0], [sp], #6
ST3 v0.H, v1.H, v2.H [0], [sp], x5
ST3 v0.S, v1.S, v2.S [0], [sp], #12
ST3 v0.S, v1.S, v2.S [0], [sp], x5
ST3 v0.D, v1.D, v2.D [0], [sp], #24
ST3 v0.D, v1.D, v2.D [0], [sp], x5
ST4 v0.4s, v2.4s, v4.4s, v5.4s, [sp]
ST4 v0.4s, v2.4s, v4.4s, v5.4s, [sp], 0
ST4 v0.4s, v2.4s, v4.4s, v5.4s, [sp], x5
ST4 v0.B, v1.B, v2.B, v3.B [0], [sp]
ST4 v0.H, v1.H, v2.H, v3.H [0], [sp]
ST4 v0.S, v1.S, v2.S, v3.S [0], [sp]
ST4 v0.D, v1.D, v2.D, v3.D [0], [sp]
ST4 v0.B, v1.B, v2.B, v3.B [0], [sp], #4
ST4 v0.B, v1.B, v2.B, v3.B [0], [sp], x5
ST4 v0.H, v1.H, v2.H, v3.H [0], [sp], #8
ST4 v0.H, v1.H, v2.H, v3.H [0], [sp], x5
ST4 v0.S, v1.S, v2.S, v3.S [0], [sp], #16
ST4 v0.S, v1.S, v2.S, v3.S [0], [sp], x5
ST4 v0.D, v1.D, v2.D, v3.D [0], [sp], #32
ST4 v0.D, v1.D, v2.D, v3.D [0], [sp], x5
ST64B x0, [sp, #0]
ST64BV x0, x1, [sp]
ST64BV0 x0, x1, [sp]
STCPH
STG sp, [sp], #0
STG sp, [sp, #0]!
STG sp, [sp, #0]
STGM x0, [sp]
STGP x0, x1, [sp], #0
STGP x0, x1, [sp, #0]!
STGP x0, x1, [sp, #0]
STILP w0, w1, [sp, #-8]!
STILP w0, w1, [sp]
STILP x0, x1, [sp, #-16]!
STILP x0, x1, [sp]
STL1 v0.D [0], [sp]
STLLR w0, [sp, #0]
STLLR x0, [sp, #0]
STLLRB w0, [sp, #0]
STLLRH w0, [sp, #0]
STLP x0, x1, [sp, #0]
STLR w0, [sp, #0]
STLR x0, [sp, #0]
STLR w0, [sp, #-4]!
STLR x0, [sp, #-8]!
STLRB w0, [sp, #0]
STLRH w0, [sp, #0]
STLTXR w0, w1, [sp, #0]
STLTXR w0, x1, [sp, #0]
STLUR w0, [sp, #0]
STLUR x0, [sp, #0]
STLURB w0, [sp, #0]
STLURH w0, [sp, #0]
STLXP w0, w1, w2, [sp, #0]
STLXP w0, x1, x2, [sp, #0]
STLXR w0, w1, [sp, #0]
STLXR w0, x1, [sp, #0]
STLXRB w0, w1, [sp, #0]
STLXRH w0, w1, [sp, #0]
STNP w0, w1, [sp, #0]
STNP x0, x1, [sp, #0]
STP w0, w1, [sp], #0
STP x0, x1, [sp], #0
STP w0, w1, [sp, #0]!
STP x0, x1, [sp, #0]!
STP w0, w1, [sp, #0]
STP x0, x1, [sp, #0]
STR w0, [sp], #0
STR x0, [sp], #0
STR w0, [sp, #0]!
STR x0, [sp, #0]!
STR w0, [sp, #0]
STR x0, [sp, #0]
STR w0, [sp, w2, uxtx 0]
STR x0, [sp, w2, uxtx 0]
STRB w0, [sp], #0
STRB w0, [sp, #0]!
STRB w0, [sp, #0]
STRB w0, [sp, w2, uxtx 0]
STRB w0, [sp, x2, LSL 0]
STRH w0, [sp], #0
STRH w0, [sp, #0]!
STRH w0, [sp, #0]
STRH w0, [sp, w2, uxtx 0]
STSHH 0
STTNP x0, x1, [sp, #0]
STTP x0, x1, [sp], #0
STTP x0, x1, [sp, #0]!
STTP x0, x1, [sp, #0]
STTR w0, [sp, #0]
STTR x0, [sp, #0]
STTRB w0, [sp, #0]
STTRH w0, [sp, #0]
STTXR w0, w1, [sp, #0]
STTXR w0, x1, [sp, #0]
STUR w0, [sp, #0]
STUR x0, [sp, #0]
STURB w0, [sp, #0]
STURH w0, [sp, #0]
STXP w0, w1, w2, [sp, #0]
STXP w0, x1, x2, [sp, #0]
STXR w0, w1, [sp, #0]
STXR w0, x1, [sp, #0]
STXRB w0, w1, [sp, #0]
STXRH w0, w1, [sp, #0]
STZ2G sp, [sp], #0
STZ2G sp, [sp, #0]!
STZ2G sp, [sp, #0]
STZG sp, [sp], #0
STZG sp, [sp, #0]!
STZG sp, [sp, #0]
STZGM x0, [sp]
SUB sp, sp, w2, uxtx #0
SUB sp, sp, 00, uxtx #0
SUB sp, sp, #0, lsl
SUB sp, sp, #0, lsl
SUB w0, w1, w2, lsl #0
SUB x0, x1, x2, lsl #0
SUB D0, D0, D0
SUB v0.4s, v2.4s, v4.4s
SUBG sp, sp, #0, #0
SUBHN0 v1.4s, v3.4s, v5.4s
SUBP x0, sp, sp
SUBPS x0, sp, sp
SUBPT sp, sp, x2, LSL #0
SUBS w0, sp, w2, uxtx #0
SUBS x0, sp, 00, uxtx #0
SUBS w0, sp, #0, lsl
SUBS x0, sp, #0, lsl
SUBS w0, w1, w2, lsl #0
SUBS x0, x1, x2, lsl #0
SUDOT v0.4s, v2.4s, v4.4B[0]
SUQADD 00, 00
SUQADD v0.4s, v2.4s
SVC #0
SXTB w0, w1
SXTB x0, w1
SXTH w0, w1
SXTH x0, w1
SXTL0 v1.4s, v3.4s
SXTW x0, w1
SYS #0, c0, c0, #0, x4
SYSL x0, #0, c0, c0, #0
SYSP #0, c0, c0, #0, x4, x5
TBL v0.4s, v2.16B, v3.4s
TBL v0.4s, v2.16B, v3.16B, v4.4s
TBL v0.4s, v2.16B, v3.16B, v4.16B, v5.4s
TBL v0.4s, v2.16B, v3.16B, v4.16B, v5.16B, v5.4s
TBNZ 04s, #0, .Lmicroprobe_catalog_target
TBX v0.4s, v2.16B, v3.4s
TBX v0.4s, v2.16B, v3.16B, v4.4s
TBX v0.4s, v2.16B, v3.16B, v4.16B, v5.4s
TBX v0.4s, v2.16B, v3.16B, v4.16B, v5.16B, v5.4s
TBZ 04s, #0, .Lmicroprobe_catalog_target
TLBI 0, x1
TLBIP 0, x1, x2
TRCIT x0
TRN1 v0.4s, v2.4s, v4.4s
TRN2 v0.4s, v2.4s, v4.4s
TSB CSYNC
TST w0, #0
TST x0, #0
TST w0, w1, lsl #0
TST x0, x1, lsl #0
UABA v0.4s, v2.4s, v4.4s
UABAL0 v1.4s, v3.4s, v5.4s
UABD v0.4s, v2.4s, v4.4s
UABDL0 v1.4s, v3.4s, v5.4s
UADALP v0.4s, v2.4s
UADDL0 v1.4s, v3.4s, v5.4s
UADDLP v0.4s, v2.4s
UADDLV 00, v2.4s
UADDW0 v1.4s, v3.4s, v5.4s
UBFIZ w0, w1, #0, #0
UBFIZ x0, x1, #0, #0
UBFM w0, w1, #0, #0
UBFM x0, x1, #0, #0
UBFX w0, w1, #0, #0
UBFX x0, x1, #0, #0
UCVTF 00, 00, #0
UCVTF v0.4s, v2.4s, #0
UCVTF h0, h1
UCVTF 00, 00
UCVTF v0.8h, v2.8h
UCVTF v0.4s, v2.4s
UCVTF h0, w1, #0
UCVTF h0, x1, #0
UCVTF s0, w1, #0
UCVTF s0, x1, #0
UCVTF d0, w1, #0
UCVTF d0, x1, #0
UCVTF h0, w1
UCVTF s0, w1
UCVTF d0, w1
UCVTF h0, x1
UCVTF s0, x1
UCVTF d0, x1
UCVTF h0, s1
UCVTF d0, s1
UCVTF h0, d1
UCVTF s0, d1
UDF #0
UDIV w0, w1, w2
UDIV x0, x1, x2
UDOT v0.4s, v2.4s, v4.4B[0]
UDOT v0.4s, v2.4s, v4.4s
UHADD v0.4s, v2.4s, v4.4s
UHSUB v0.4s, v2.4s, v4.4s
UMADDL x0, w1, w2, x3
UMAX v0.4s, v2.4s, v4.4s
UMAX w0, w1, #0
UMAX x0, x1, #0
UMAX w0, w1, w2
UMAX x0, x1, x2
UMAXP v0.4s, v2.4s, v4.4s
UMAXV 00, v2.4s
UMIN v0.4s, v2.4s, v4.4s
UMIN w0, w1, #0
UMIN x0, x1, #0
UMIN w0, w1, w2
UMIN x0, x1, x2
UMINP v0.4s, v2.4s, v4.4s
UMINV 00, v2.4s
UMLAL0 v1.4s, v3.4s, V0.0[0]
UMLAL0 v1.4s, v3.4s, v5.4s
UMLSL0 v1.4s, v3.4s, V0.0[0]
UMLSL0 v1.4s, v3.4s, v5.4s
UMMLA v0.4S, v1.16B, v2.16B
UMNEGL x0, w1, w2
UMOV w0, v1.0[0]
UMOV x0, v1.D[0]
UMSUBL x0, w1, w2, x3
UMULH x0, x1, x2
UMULL0 v1.4s, v3.4s, V0.0[0]
UMULL0 v1.4s, v3.4s, v5.4s
UMULL x0, w1, w2
UQADD 00, 00, 00
UQADD v0.4s, v2.4s, v4.4s
UQRSHL 00, 00, 00
UQRSHL v0.4s, v2.4s, v4.4s
UQRSHRN 00, v20, #lsl
UQRSHRN0 v1.4s, v3.4s, #lsl
UQSHL 00, 00, #lsl
UQSHL v0.4s, v2.4s, #lsl
UQSHL 00, 00, 00
UQSHL v0.4s, v2.4s, v4.4s
UQSHRN 00, v20, #lsl
UQSHRN0 v1.4s, v3.4s, #lsl
UQSUB 00, 00, 00
UQSUB v0.4s, v2.4s, v4.4s
.Lmicroprobe_catalog_target:
nop
