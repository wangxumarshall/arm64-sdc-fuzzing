.arch armv8-a
.arch_extension lse
.arch_extension memtag
.arch_extension i8mm
.arch_extension fp16
.arch_extension dotprod
.arch_extension cssc
.arch_extension flagm
.arch_extension sha3
.arch_extension pauth
.arch_extension aes
.arch_extension bf16
.text
STTRH w0, [sp, #0]
STTSET w0, [sp]
STTSETL w0, [sp]
STTSET x0, [sp]
STTSETL x0, [sp]
STTXR w0, w1, [sp, #0]
STTXR w0, x1, [sp, #0]
STUMAX w0, [sp]
STUMAXL w0, [sp]
STUMAX x0, [sp]
STUMAXL x0, [sp]
STUMAXB w0, [sp]
STUMAXLB w0, [sp]
STUMAXH w0, [sp]
STUMAXLH w0, [sp]
STUMIN w0, [sp]
STUMINL w0, [sp]
STUMIN x0, [sp]
STUMINL x0, [sp]
STUMINB w0, [sp]
STUMINLB w0, [sp]
STUMINH w0, [sp]
STUMINLH w0, [sp]
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
SWP w0, w1, [sp]
SWPA w0, w1, [sp]
SWPAL w0, w1, [sp]
SWPL w0, w1, [sp]
SWP x0, x1, [sp]
SWPA x0, x1, [sp]
SWPAL x0, x1, [sp]
SWPL x0, x1, [sp]
SWPB w0, w1, [sp]
SWPAB w0, w1, [sp]
SWPALB w0, w1, [sp]
SWPLB w0, w1, [sp]
SWPH w0, w1, [sp]
SWPAH w0, w1, [sp]
SWPALH w0, w1, [sp]
SWPLH w0, w1, [sp]
SWPP x0, x1, [sp]
SWPPA x0, x1, [sp]
SWPPAL x0, x1, [sp]
SWPPL x0, x1, [sp]
SWPT w0, w1, [sp]
SWPTA w0, w1, [sp]
SWPTAL w0, w1, [sp]
SWPTL w0, w1, [sp]
SWPT x0, x1, [sp]
SWPTA x0, x1, [sp]
SWPTAL x0, x1, [sp]
SWPTL x0, x1, [sp]
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
UQXTN 00, v20
UQXTN0 v1.4s, v3.4s
URECPE v0.4s, v2.4s
URHADD v0.4s, v2.4s, v4.4s
URSHL D0, D0, D0
URSHL v0.4s, v2.4s, v4.4s
URSHR D0, D0, #lsl
URSHR v0.4s, v2.4s, #lsl
URSQRTE v0.4s, v2.4s
URSRA D0, D0, #lsl
URSRA v0.4s, v2.4s, #lsl
USDOT v0.4s, v2.4s, v4.4B[0]
USDOT v0.4s, v2.4s, v4.4s
USHL D0, D0, D0
USHL v0.4s, v2.4s, v4.4s
USHLL0 v1.4s, v3.4s, #lsl
USHR D0, D0, #lsl
USHR v0.4s, v2.4s, #lsl
USMMLA v0.4S, v1.16B, v2.16B
USQADD 00, 00
USQADD v0.4s, v2.4s
USRA D0, D0, #lsl
USRA v0.4s, v2.4s, #lsl
USUBL0 v1.4s, v3.4s, v5.4s
USUBW0 v1.4s, v3.4s, v5.4s
UXTB w0, w1
UXTH w0, w1
UXTL0 v1.4s, v3.4s
UZP1 v0.4s, v2.4s, v4.4s
UZP2 v0.4s, v2.4s, v4.4s
WFE
WFET x0
WFI
WFIT x0
XAFLAG
XAR v0.2D, v1.2D, v2.2D, #0
XPACD x0
XPACI x0
XPACLRI
XTN0 v1.4s, v3.4s
YIELD
ZIP1 v0.4s, v2.4s, v4.4s
ZIP2 v0.4s, v2.4s, v4.4s
ABS w0, w1
ABS x0, x1
ABS D0, D0
ABS v0.4s, v2.4s
ADC w0, w1, w2
ADC x0, x1, x2
ADCS w0, w1, w2
ADCS x0, x1, x2
ADD sp, sp, w2, uxtx #0
ADD sp, sp, 00, uxtx #0
ADD sp, sp, #0, lsl
ADD sp, sp, #0, lsl
ADD w0, w1, w2, lsl #0
ADD x0, x1, x2, lsl #0
ADD D0, D0, D0
ADD v0.4s, v2.4s, v4.4s
ADDG sp, sp, #0, #0
ADDHN0 v1.4s, v3.4s, v5.4s
ADDP D0, v1.2D
ADDP v0.4s, v2.4s, v4.4s
ADDPT sp, sp, x2, LSL #0
ADDS w0, sp, w2, uxtx #0
ADDS x0, sp, 00, uxtx #0
ADDS w0, sp, #0, lsl
ADDS x0, sp, #0, lsl
ADDS w0, w1, w2, lsl #0
ADDS x0, x1, x2, lsl #0
ADDV 00, v2.4s
ADR x0, .Lmicroprobe_catalog_target
ADRP x0, .Lmicroprobe_catalog_target
AESD v0.16B, v1.16B
AESE v0.16B, v1.16B
AESIMC v0.16B, v1.16B
AESMC v0.16B, v1.16B
AND v0.4s, v2.4s, v4.4s
AND sp, w1, #0
AND sp, x1, #0
AND w0, w1, w2, lsl #0
AND x0, x1, x2, lsl #0
ANDS w0, w1, #0
ANDS x0, x1, #0
ANDS w0, w1, w2, lsl #0
ANDS x0, x1, x2, lsl #0
APAS x0
ASR w0, w1, w2
ASR x0, x1, x2
ASR w0, w1, #lsl
ASR x0, x1, #lsl
ASRV w0, w1, w2
ASRV x0, x1, x2
AT 0, x1
AUTDA x0, sp
AUTDZA x0
AUTDB x0, sp
AUTDZB x0
AUTIA x0, sp
AUTIZA x0
AUTIA1716
AUTIASP
AUTIAZ
AUTIA171615
AUTIASPPC .Lmicroprobe_catalog_target
AUTIASPPCR x0
AUTIB x0, sp
AUTIZB x0
AUTIB1716
AUTIBSP
AUTIBZ
AUTIB171615
AUTIBSPPC .Lmicroprobe_catalog_target
AUTIBSPPCR x0
AXFLAG
B.eq .Lmicroprobe_catalog_target
B .Lmicroprobe_catalog_target
BC.eq .Lmicroprobe_catalog_target
BCAX v0.16B, v1.16B, v2.16B, v3.16B
BF1CVTL0 v1.8H, v2.4s
BF2CVTL0 v1.8H, v2.4s
BFC w0, #0, #0
BFC x0, #0, #0
BFCVT h0, s1
BFCVTN0 v1.4s, v3.4S
BFDOT v0.4s, v2.4s, v4.2H[0]
BFDOT v0.4s, v2.4s, v4.4s
BFI w0, w1, #0, #0
BFI x0, x1, #0, #0
BFM w0, w1, #0, #0
BFM x0, x1, #0, #0
BFMLALb0 v1.4S, v2.8H, v3.H[0]
BFMLALb0 v1.4S, v2.8H, v3.8H
BFMMLA v0.4S, v1.8H, v2.8H
BFXIL w0, w1, #0, #0
BFXIL x0, x1, #0, #0
BIC v0.4s, #0, LSL #0
BIC v0.4s, #0, LSL #0
BIC v0.4s, v2.4s, v4.4s
BIC w0, w1, w2, lsl #0
BIC x0, x1, x2, lsl #0
BICS w0, w1, w2, lsl #0
BICS x0, x1, x2, lsl #0
BIF v0.4s, v2.4s, v4.4s
BIT v0.4s, v2.4s, v4.4s
BL .Lmicroprobe_catalog_target
BLR x0
BLRAA x0, sp
BLRAAZ x0
BLRAB x0, sp
BLRABZ x0
BR x0
BRAA x0, sp
BRAAZ x0
BRAB x0, sp
BRABZ x0
BRB b0
BRK #0
BSL v0.4s, v2.4s, v4.4s
BTI 0
CAS w0, w1, [sp, #0]
CASA w0, w1, [sp, #0]
CASAL w0, w1, [sp, #0]
CASL w0, w1, [sp, #0]
CAS x0, x1, [sp, #0]
CASA x0, x1, [sp, #0]
CASAL x0, x1, [sp, #0]
CASL x0, x1, [sp, #0]
CASB w0, w1, [sp, #0]
CASAB w0, w1, [sp, #0]
CASALB w0, w1, [sp, #0]
CASLB w0, w1, [sp, #0]
CASH w0, w1, [sp, #0]
CASAH w0, w1, [sp, #0]
CASALH w0, w1, [sp, #0]
CASLH w0, w1, [sp, #0]
CASP w0, 0, w2, 0, [sp, #0]
CASPA w0, 0, w2, 0, [sp, #0]
CASPAL w0, 0, w2, 0, [sp, #0]
CASPL w0, 0, w2, 0, [sp, #0]
CASP x0, 0, x2, 0, [sp, #0]
CASPA x0, 0, x2, 0, [sp, #0]
CASPAL x0, 0, x2, 0, [sp, #0]
CASPL x0, 0, x2, 0, [sp, #0]
CASPT x0, 0, x2, 0, [sp, #0]
CASPAT x0, 0, x2, 0, [sp, #0]
CASPALT x0, 0, x2, 0, [sp, #0]
CASPLT x0, 0, x2, 0, [sp, #0]
CAST x0, x1, [sp, #0]
CASAT x0, x1, [sp, #0]
CASALT x0, x1, [sp, #0]
CASLT x0, x1, [sp, #0]
CBBGT w0, w1, .Lmicroprobe_catalog_target
CBBGE w0, w1, .Lmicroprobe_catalog_target
CBBHI w0, w1, .Lmicroprobe_catalog_target
CBBHS w0, w1, .Lmicroprobe_catalog_target
CBBEQ w0, w1, .Lmicroprobe_catalog_target
CBBNE w0, w1, .Lmicroprobe_catalog_target
CBBLE w0, w1, .Lmicroprobe_catalog_target
CBBLO w0, w1, .Lmicroprobe_catalog_target
CBBLS w0, w1, .Lmicroprobe_catalog_target
CBBLT w0, w1, .Lmicroprobe_catalog_target
CBGT w0, #0, .Lmicroprobe_catalog_target
CBLT w0, #0, .Lmicroprobe_catalog_target
CBHI w0, #0, .Lmicroprobe_catalog_target
CBLO w0, #0, .Lmicroprobe_catalog_target
CBEQ w0, #0, .Lmicroprobe_catalog_target
CBNE w0, #0, .Lmicroprobe_catalog_target
CBGT x0, #0, .Lmicroprobe_catalog_target
CBLT x0, #0, .Lmicroprobe_catalog_target
CBHI x0, #0, .Lmicroprobe_catalog_target
CBLO x0, #0, .Lmicroprobe_catalog_target
CBEQ x0, #0, .Lmicroprobe_catalog_target
CBNE x0, #0, .Lmicroprobe_catalog_target
CBGT w0, w1, .Lmicroprobe_catalog_target
CBGE w0, w1, .Lmicroprobe_catalog_target
CBHI w0, w1, .Lmicroprobe_catalog_target
CBHS w0, w1, .Lmicroprobe_catalog_target
CBEQ w0, w1, .Lmicroprobe_catalog_target
CBNE w0, w1, .Lmicroprobe_catalog_target
CBGT x0, x1, .Lmicroprobe_catalog_target
CBGE x0, x1, .Lmicroprobe_catalog_target
CBHI x0, x1, .Lmicroprobe_catalog_target
CBHS x0, x1, .Lmicroprobe_catalog_target
CBEQ x0, x1, .Lmicroprobe_catalog_target
CBNE x0, x1, .Lmicroprobe_catalog_target
CBGE w0, #1, .Lmicroprobe_catalog_target
CBGE x0, #1, .Lmicroprobe_catalog_target
CBHGT w0, w1, .Lmicroprobe_catalog_target
CBHGE w0, w1, .Lmicroprobe_catalog_target
CBHHI w0, w1, .Lmicroprobe_catalog_target
CBHHS w0, w1, .Lmicroprobe_catalog_target
CBHEQ w0, w1, .Lmicroprobe_catalog_target
CBHNE w0, w1, .Lmicroprobe_catalog_target
CBHLE w0, w1, .Lmicroprobe_catalog_target
CBHLO w0, w1, .Lmicroprobe_catalog_target
CBHLS w0, w1, .Lmicroprobe_catalog_target
CBHLT w0, w1, .Lmicroprobe_catalog_target
CBHS w0, #1, .Lmicroprobe_catalog_target
CBHS x0, #1, .Lmicroprobe_catalog_target
CBLE w0, #0, .Lmicroprobe_catalog_target
CBLE x0, #0, .Lmicroprobe_catalog_target
CBLE w0, w1, .Lmicroprobe_catalog_target
CBLE x0, x1, .Lmicroprobe_catalog_target
CBLO w0, w1, .Lmicroprobe_catalog_target
CBLO x0, x1, .Lmicroprobe_catalog_target
CBLS w0, #0, .Lmicroprobe_catalog_target
CBLS x0, #0, .Lmicroprobe_catalog_target
CBLS w0, w1, .Lmicroprobe_catalog_target
CBLS x0, x1, .Lmicroprobe_catalog_target
CBLT w0, w1, .Lmicroprobe_catalog_target
CBLT x0, x1, .Lmicroprobe_catalog_target
CBNZ w0, .Lmicroprobe_catalog_target
CBNZ x0, .Lmicroprobe_catalog_target
CBZ w0, .Lmicroprobe_catalog_target
CBZ x0, .Lmicroprobe_catalog_target
CCMN w0, #0, #0, eq
CCMN x0, #0, #0, eq
CCMN w0, w1, #0, eq
CCMN x0, x1, #0, eq
CCMP w0, #0, #0, eq
CCMP x0, #0, #0, eq
CCMP w0, w1, #0, eq
CCMP x0, x1, #0, eq
CFINV
CFP RCTX, x0
CHKFEAT X16
CINC w0, w1, 0
CINC x0, x1, 0
CINV w0, w1, 0
CINV x0, x1, 0
CLRBHB
CLREX #0
CLS v0.4s, v2.4s
CLS w0, w1
CLS x0, x1
CLZ v0.4s, v2.4s
CLZ w0, w1
CLZ x0, x1
CMEQ D0, D0, D0
CMEQ v0.4s, v2.4s, v4.4s
CMEQ D0, D0, #0
CMEQ v0.4s, v2.4s, #0
CMGE D0, D0, D0
CMGE v0.4s, v2.4s, v4.4s
CMGE D0, D0, #0
CMGE v0.4s, v2.4s, #0
CMGT D0, D0, D0
CMGT v0.4s, v2.4s, v4.4s
CMGT D0, D0, #0
CMGT v0.4s, v2.4s, #0
CMHI D0, D0, D0
CMHI v0.4s, v2.4s, v4.4s
CMHS D0, D0, D0
CMHS v0.4s, v2.4s, v4.4s
CMLE D0, D0, #0
CMLE v0.4s, v2.4s, #0
CMLT D0, D0, #0
CMLT v0.4s, v2.4s, #0
CMN sp, w1, uxtx #0
CMN sp, 00, uxtx #0
CMN sp, #0, lsl
CMN sp, #0, lsl
CMN w0, w1, lsl #0
CMN x0, x1, lsl #0
CMP sp, w1, uxtx #0
.Lmicroprobe_catalog_target:
nop
