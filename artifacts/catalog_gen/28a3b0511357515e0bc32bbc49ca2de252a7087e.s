.arch armv8-a
.text
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
AUTIA171615
AUTIASPPC .Lmicroprobe_catalog_target
AUTIASPPCR x0
AUTIB171615
AUTIBSPPC .Lmicroprobe_catalog_target
AUTIBSPPCR x0
AXFLAG
B.eq .Lmicroprobe_catalog_target
B .Lmicroprobe_catalog_target
BC.eq .Lmicroprobe_catalog_target
BCAX v0.16B, v1.16B, v2.16B, v3.16B
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
BR x0
BRB b0
BRK #0
BSL v0.4s, v2.4s, v4.4s
BTI 0
CBBLE w0, w1, .Lmicroprobe_catalog_target
CBBLO w0, w1, .Lmicroprobe_catalog_target
CBBLS w0, w1, .Lmicroprobe_catalog_target
CBBLT w0, w1, .Lmicroprobe_catalog_target
CBGE w0, #1, .Lmicroprobe_catalog_target
CBGE x0, #1, .Lmicroprobe_catalog_target
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
CMP sp, 00, uxtx #0
CMP sp, #0, lsl
CMP sp, #0, lsl
CMP w0, w1, lsl #0
CMP x0, x1, lsl #0
CMPP sp, sp
CMTST D0, D0, D0
CMTST v0.4s, v2.4s, v4.4s
CNEG w0, w1, 0
CNEG x0, x1, 0
CNT w0, w1
CNT x0, x1
CNT v0.4s, v2.4s
COSP RCTX, x0
CPP RCTX, x0
CSDB
CSEL w0, w1, w2, eq
CSEL x0, x1, x2, eq
CSET w0, 0
CSET x0, 0
CSETM w0, 0
CSETM x0, 0
CSINC w0, w1, w2, eq
CSINC x0, x1, x2, eq
CSINV w0, w1, w2, eq
CSINV x0, x1, x2, eq
CSNEG w0, w1, w2, eq
CSNEG x0, x1, x2, eq
CTZ w0, w1
CTZ x0, x1
DC 0, x1
DCPS1 #0
DCPS2 #0
DCPS3 #0
DGH
DMB sy
DRPS
DSB sy
DSB synXS
DUP 00, v2.4s[0]
DUP v0.4s, v2.0[0]
DUP v0.4s, 00
DVP RCTX, x0
EON w0, w1, w2, lsl #0
EON x0, x1, x2, lsl #0
EOR3 v0.16B, v1.16B, v2.16B, v3.16B
EOR v0.4s, v2.4s, v4.4s
EOR sp, w1, #0
EOR sp, x1, #0
EOR w0, w1, w2, lsl #0
EOR x0, x1, x2, lsl #0
ERET
ESB
EXT v0.4s, v2.4s, v4.4s, #0
EXTR w0, w1, w2, #0
EXTR x0, x1, x2, #0
FABD h0, h1, h2
FABD 00, 00, 00
FABD v0.8h, v2.8h, v4.8h
FABD v0.4s, v2.4s, v4.4s
FABS v0.8h, v2.8h
FABS v0.4s, v2.4s
FABS h0, h1
FABS s0, s1
FABS d0, d1
FACGE h0, h1, h2
FACGE 00, 00, 00
FACGE v0.8h, v2.8h, v4.8h
FACGE v0.4s, v2.4s, v4.4s
FACGT h0, h1, h2
FACGT 00, 00, 00
FACGT v0.8h, v2.8h, v4.8h
FACGT v0.4s, v2.4s, v4.4s
FADD v0.8h, v2.8h, v4.8h
FADD v0.4s, v2.4s, v4.4s
FADD h0, h1, h2
FADD s0, s1, s2
FADD d0, d1, d2
FADDP H0, v1.2H
FADDP 00, v2.4s
FADDP v0.8h, v2.8h, v4.8h
FADDP v0.4s, v2.4s, v4.4s
FAMAX v0.8h, v2.8h, v4.8h
FAMAX v0.4s, v2.4s, v4.4s
FAMIN v0.8h, v2.8h, v4.8h
FAMIN v0.4s, v2.4s, v4.4s
FCADD v0.4s, v2.4s, v4.4s, #0
FCCMP h0, h1, #0, eq
FCCMP s0, s1, #0, eq
FCCMP d0, d1, #0, eq
FCCMPE h0, h1, #0, eq
FCCMPE s0, s1, #0, eq
FCCMPE d0, d1, #0, eq
FCMEQ h0, h1, h2
FCMEQ 00, 00, 00
FCMEQ v0.8h, v2.8h, v4.8h
FCMEQ v0.4s, v2.4s, v4.4s
FCMEQ h0, h1, #0.0
FCMEQ 00, 00, #0.0
FCMEQ v0.8h, v2.8h, #0.0
FCMEQ v0.4s, v2.4s, #0.0
FCMGE h0, h1, h2
FCMGE 00, 00, 00
FCMGE v0.8h, v2.8h, v4.8h
FCMGE v0.4s, v2.4s, v4.4s
FCMGE h0, h1, #0.0
FCMGE 00, 00, #0.0
FCMGE v0.8h, v2.8h, #0.0
FCMGE v0.4s, v2.4s, #0.0
FCMGT h0, h1, h2
FCMGT 00, 00, 00
FCMGT v0.8h, v2.8h, v4.8h
FCMGT v0.4s, v2.4s, v4.4s
FCMGT h0, h1, #0.0
FCMGT 00, 00, #0.0
FCMGT v0.8h, v2.8h, #0.0
FCMGT v0.4s, v2.4s, #0.0
FCMLA v0.4s, v2.4s, v4.0[0], #0
FCMLA v0.4s, v2.4s, v4.4s, #0
FCMLE h0, h1, #0.0
FCMLE 00, 00, #0.0
FCMLE v0.8h, v2.8h, #0.0
FCMLE v0.4s, v2.4s, #0.0
FCMLT h0, h1, #0.0
FCMLT 00, 00, #0.0
FCMLT v0.8h, v2.8h, #0.0
FCMLT v0.4s, v2.4s, #0.0
FCMP h0, h1
FCMP h0, #0.0
FCMP s0, s1
FCMP s0, #0.0
FCMP d0, d1
FCMP d0, #0.0
FCMPE h0, h1
FCMPE h0, #0.0
FCMPE s0, s1
FCMPE s0, #0.0
FCMPE d0, d1
FCMPE d0, #0.0
FCSEL h0, h1, h2, eq
FCSEL s0, s1, s2, eq
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
.Lmicroprobe_catalog_target:
nop
