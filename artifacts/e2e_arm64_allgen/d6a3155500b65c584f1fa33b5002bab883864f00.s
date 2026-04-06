.arch armv8-a
.arch_extension pauth
.arch_extension flagm
.arch_extension fp16
.arch_extension dotprod
.arch_extension mops
.arch_extension memtag
.arch_extension sha2
.arch_extension sha3
.arch_extension sm4
.arch_extension cssc
.arch_extension i8mm
.arch_extension rdm
.arch_extension lse
.arch_extension rcpc3
.arch_extension rcpc
.text
RCWSCLRPAL x0, x1, [sp]
RCWSCLRPL x0, x1, [sp]
RCWSET x0, x1, [sp]
RCWSETA x0, x1, [sp]
RCWSETAL x0, x1, [sp]
RCWSETL x0, x1, [sp]
RCWSETP x0, x1, [sp]
RCWSETPA x0, x1, [sp]
RCWSETPAL x0, x1, [sp]
RCWSETPL x0, x1, [sp]
RCWSSET x0, x1, [sp]
RCWSSETA x0, x1, [sp]
RCWSSETAL x0, x1, [sp]
RCWSSETL x0, x1, [sp]
RCWSSETP x0, x1, [sp]
RCWSSETPA x0, x1, [sp]
RCWSSETPAL x0, x1, [sp]
RCWSSETPL x0, x1, [sp]
RCWSSWP x0, x1, [sp]
RCWSSWPA x0, x1, [sp]
RCWSSWPAL x0, x1, [sp]
RCWSSWPL x0, x1, [sp]
RCWSSWPP x0, x1, [sp]
RCWSSWPPA x0, x1, [sp]
RCWSSWPPAL x0, x1, [sp]
RCWSSWPPL x0, x1, [sp]
RCWSWP x0, x1, [sp]
RCWSWPA x0, x1, [sp]
RCWSWPAL x0, x1, [sp]
RCWSWPL x0, x1, [sp]
RCWSWPP x0, x1, [sp]
RCWSWPPA x0, x1, [sp]
RCWSWPPAL x0, x1, [sp]
RCWSWPPL x0, x1, [sp]
RET x0
RETAA
RETAB
RETAASPPC .Lmicroprobe_catalog_target
RETABSPPC .Lmicroprobe_catalog_target
RETAASPPCR x0
RETABSPPCR x0
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
SETF8 w0
SETF16 w0
SETGP [x0]!, x1!, x2
SETGM [x0]!, x1!, x2
SETGE [x0]!, x1!, x2
SETGPN [x0]!, x1!, x2
SETGMN [x0]!, x1!, x2
SETGEN [x0]!, x1!, x2
SETGPT [x0]!, x1!, x2
SETGMT [x0]!, x1!, x2
SETGET [x0]!, x1!, x2
SETGPTN [x0]!, x1!, x2
SETGMTN [x0]!, x1!, x2
SETGETN [x0]!, x1!, x2
SETP [x0]!, x1!, x2
SETM [x0]!, x1!, x2
SETE [x0]!, x1!, x2
SETPN [x0]!, x1!, x2
SETMN [x0]!, x1!, x2
SETEN [x0]!, x1!, x2
SETPT [x0]!, x1!, x2
SETMT [x0]!, x1!, x2
SETET [x0]!, x1!, x2
SETPTN [x0]!, x1!, x2
SETMTN [x0]!, x1!, x2
SETETN [x0]!, x1!, x2
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
STADD w0, [sp]
STADDL w0, [sp]
STADD x0, [sp]
STADDL x0, [sp]
STADDB w0, [sp]
STADDLB w0, [sp]
STADDH w0, [sp]
STADDLH w0, [sp]
STBFADD h0, [sp]
STBFADDL h0, [sp]
STBFMAX h0, [sp]
STBFMAXL h0, [sp]
STBFMAXNM h0, [sp]
STBFMAXNML h0, [sp]
STBFMIN h0, [sp]
STBFMINL h0, [sp]
STBFMINNM h0, [sp]
STBFMINNML h0, [sp]
STCLR w0, [sp]
STCLRL w0, [sp]
STCLR x0, [sp]
STCLRL x0, [sp]
STCLRB w0, [sp]
STCLRLB w0, [sp]
STCLRH w0, [sp]
STCLRLH w0, [sp]
STCPH
STEOR w0, [sp]
STEORL w0, [sp]
STEOR x0, [sp]
STEORL x0, [sp]
STEORB w0, [sp]
STEORLB w0, [sp]
STEORH w0, [sp]
STEORLH w0, [sp]
STFADD h0, [sp]
STFADDL h0, [sp]
STFADD 0, [sp]
STFADDL 0, [sp]
STFADD 0, [sp]
STFADDL 0, [sp]
STFMAX h0, [sp]
STFMAXL h0, [sp]
STFMAX 0, [sp]
STFMAXL 0, [sp]
STFMAX 0, [sp]
STFMAXL 0, [sp]
STFMAXNM h0, [sp]
STFMAXNML h0, [sp]
STFMAXNM 0, [sp]
STFMAXNML 0, [sp]
STFMAXNM 0, [sp]
STFMAXNML 0, [sp]
STFMIN h0, [sp]
STFMINL h0, [sp]
STFMIN 0, [sp]
STFMINL 0, [sp]
STFMIN 0, [sp]
STFMINL 0, [sp]
STFMINNM h0, [sp]
STFMINNML h0, [sp]
STFMINNM 0, [sp]
STFMINNML 0, [sp]
STFMINNM 0, [sp]
STFMINNML 0, [sp]
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
STSET w0, [sp]
STSETL w0, [sp]
STSET x0, [sp]
STSETL x0, [sp]
STSETB w0, [sp]
STSETLB w0, [sp]
STSETH w0, [sp]
STSETLH w0, [sp]
STSHH 0
STSMAX w0, [sp]
STSMAXL w0, [sp]
STSMAX x0, [sp]
STSMAXL x0, [sp]
STSMAXB w0, [sp]
STSMAXLB w0, [sp]
STSMAXH w0, [sp]
STSMAXLH w0, [sp]
STSMIN w0, [sp]
STSMINL w0, [sp]
STSMIN x0, [sp]
STSMINL x0, [sp]
STSMINB w0, [sp]
STSMINLB w0, [sp]
STSMINH w0, [sp]
STSMINLH w0, [sp]
STTADD w0, [sp]
STTADDL w0, [sp]
STTADD x0, [sp]
STTADDL x0, [sp]
STTCLR w0, [sp]
STTCLRL w0, [sp]
STTCLR x0, [sp]
STTCLRL x0, [sp]
STTNP x0, x1, [sp, #0]
STTP x0, x1, [sp], #0
STTP x0, x1, [sp, #0]!
STTP x0, x1, [sp, #0]
STTR w0, [sp, #0]
STTR x0, [sp, #0]
STTRB w0, [sp, #0]
.Lmicroprobe_catalog_target:
nop
