.arch armv8-a
.arch_extension cssc
.arch_extension memtag
.arch_extension aes
.arch_extension pauth
.arch_extension flagm
.arch_extension sha3
.arch_extension bf16
.arch_extension lse
.arch_extension mops
.arch_extension crc
.arch_extension fp16
.text
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
CPYFP [x0]!, [x1]!, x2!
CPYFM [x0]!, [x1]!, x2!
CPYFE [x0]!, [x1]!, x2!
CPYFPN [x0]!, [x1]!, x2!
CPYFMN [x0]!, [x1]!, x2!
CPYFEN [x0]!, [x1]!, x2!
CPYFPRN [x0]!, [x1]!, x2!
CPYFMRN [x0]!, [x1]!, x2!
CPYFERN [x0]!, [x1]!, x2!
CPYFPRT [x0]!, [x1]!, x2!
CPYFMRT [x0]!, [x1]!, x2!
CPYFERT [x0]!, [x1]!, x2!
CPYFPRTN [x0]!, [x1]!, x2!
CPYFMRTN [x0]!, [x1]!, x2!
CPYFERTN [x0]!, [x1]!, x2!
CPYFPRTRN [x0]!, [x1]!, x2!
CPYFMRTRN [x0]!, [x1]!, x2!
CPYFERTRN [x0]!, [x1]!, x2!
CPYFPRTWN [x0]!, [x1]!, x2!
CPYFMRTWN [x0]!, [x1]!, x2!
CPYFERTWN [x0]!, [x1]!, x2!
CPYFPT [x0]!, [x1]!, x2!
CPYFMT [x0]!, [x1]!, x2!
CPYFET [x0]!, [x1]!, x2!
CPYFPTN [x0]!, [x1]!, x2!
CPYFMTN [x0]!, [x1]!, x2!
CPYFETN [x0]!, [x1]!, x2!
CPYFPTRN [x0]!, [x1]!, x2!
CPYFMTRN [x0]!, [x1]!, x2!
CPYFETRN [x0]!, [x1]!, x2!
CPYFPTWN [x0]!, [x1]!, x2!
CPYFMTWN [x0]!, [x1]!, x2!
CPYFETWN [x0]!, [x1]!, x2!
CPYFPWN [x0]!, [x1]!, x2!
CPYFMWN [x0]!, [x1]!, x2!
CPYFEWN [x0]!, [x1]!, x2!
CPYFPWT [x0]!, [x1]!, x2!
CPYFMWT [x0]!, [x1]!, x2!
CPYFEWT [x0]!, [x1]!, x2!
CPYFPWTN [x0]!, [x1]!, x2!
CPYFMWTN [x0]!, [x1]!, x2!
CPYFEWTN [x0]!, [x1]!, x2!
CPYFPWTRN [x0]!, [x1]!, x2!
CPYFMWTRN [x0]!, [x1]!, x2!
CPYFEWTRN [x0]!, [x1]!, x2!
CPYFPWTWN [x0]!, [x1]!, x2!
CPYFMWTWN [x0]!, [x1]!, x2!
CPYFEWTWN [x0]!, [x1]!, x2!
CPYP [x0]!, [x1]!, x2!
CPYM [x0]!, [x1]!, x2!
CPYE [x0]!, [x1]!, x2!
CPYPN [x0]!, [x1]!, x2!
CPYMN [x0]!, [x1]!, x2!
CPYEN [x0]!, [x1]!, x2!
CPYPRN [x0]!, [x1]!, x2!
CPYMRN [x0]!, [x1]!, x2!
CPYERN [x0]!, [x1]!, x2!
CPYPRT [x0]!, [x1]!, x2!
CPYMRT [x0]!, [x1]!, x2!
CPYERT [x0]!, [x1]!, x2!
CPYPRTN [x0]!, [x1]!, x2!
CPYMRTN [x0]!, [x1]!, x2!
CPYERTN [x0]!, [x1]!, x2!
CPYPRTRN [x0]!, [x1]!, x2!
CPYMRTRN [x0]!, [x1]!, x2!
CPYERTRN [x0]!, [x1]!, x2!
CPYPRTWN [x0]!, [x1]!, x2!
CPYMRTWN [x0]!, [x1]!, x2!
CPYERTWN [x0]!, [x1]!, x2!
CPYPT [x0]!, [x1]!, x2!
CPYMT [x0]!, [x1]!, x2!
CPYET [x0]!, [x1]!, x2!
CPYPTN [x0]!, [x1]!, x2!
CPYMTN [x0]!, [x1]!, x2!
CPYETN [x0]!, [x1]!, x2!
CPYPTRN [x0]!, [x1]!, x2!
CPYMTRN [x0]!, [x1]!, x2!
CPYETRN [x0]!, [x1]!, x2!
CPYPTWN [x0]!, [x1]!, x2!
CPYMTWN [x0]!, [x1]!, x2!
CPYETWN [x0]!, [x1]!, x2!
CPYPWN [x0]!, [x1]!, x2!
CPYMWN [x0]!, [x1]!, x2!
CPYEWN [x0]!, [x1]!, x2!
CPYPWT [x0]!, [x1]!, x2!
CPYMWT [x0]!, [x1]!, x2!
CPYEWT [x0]!, [x1]!, x2!
CPYPWTN [x0]!, [x1]!, x2!
CPYMWTN [x0]!, [x1]!, x2!
CPYEWTN [x0]!, [x1]!, x2!
CPYPWTRN [x0]!, [x1]!, x2!
CPYMWTRN [x0]!, [x1]!, x2!
CPYEWTRN [x0]!, [x1]!, x2!
CPYPWTWN [x0]!, [x1]!, x2!
CPYMWTWN [x0]!, [x1]!, x2!
CPYEWTWN [x0]!, [x1]!, x2!
CRC32B w0, w1, w2
CRC32H w0, w1, w2
CRC32W w0, w1, w2
CRC32X w0, w1, x2
CRC32CB w0, w1, w2
CRC32CH w0, w1, w2
CRC32CW w0, w1, w2
CRC32CX w0, w1, x2
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
ERETAA
ERETAB
ESB
EXT v0.4s, v2.4s, v4.4s, #0
EXTR w0, w1, w2, #0
EXTR x0, x1, x2, #0
F1CVTL0 v1.8H, v2.4s
F2CVTL0 v1.8H, v2.4s
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
.Lmicroprobe_catalog_target:
nop
