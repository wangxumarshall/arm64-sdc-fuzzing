.arch armv8-a
.arch_extension lse
.arch_extension rcpc3
.arch_extension rcpc
.arch_extension memtag
.arch_extension pauth
.arch_extension sha3
.text
LDADDALH w0, w1, [sp]
LDADDLH w0, w1, [sp]
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
LDBFADD h0, h1, [sp]
LDBFADDA h0, h1, [sp]
LDBFADDAL h0, h1, [sp]
LDBFADDL h0, h1, [sp]
LDBFMAX h0, h1, [sp]
LDBFMAXA h0, h1, [sp]
LDBFMAXAL h0, h1, [sp]
LDBFMAXL h0, h1, [sp]
LDBFMAXNM h0, h1, [sp]
LDBFMAXNMA h0, h1, [sp]
LDBFMAXNMAL h0, h1, [sp]
LDBFMAXNML h0, h1, [sp]
LDBFMIN h0, h1, [sp]
LDBFMINA h0, h1, [sp]
LDBFMINAL h0, h1, [sp]
LDBFMINL h0, h1, [sp]
LDBFMINNM h0, h1, [sp]
LDBFMINNMA h0, h1, [sp]
LDBFMINNMAL h0, h1, [sp]
LDBFMINNML h0, h1, [sp]
LDCLR w0, w1, [sp]
LDCLRA w0, w1, [sp]
LDCLRAL w0, w1, [sp]
LDCLRL w0, w1, [sp]
LDCLR x0, x1, [sp]
LDCLRA x0, x1, [sp]
LDCLRAL x0, x1, [sp]
LDCLRL x0, x1, [sp]
LDCLRB w0, w1, [sp]
LDCLRAB w0, w1, [sp]
LDCLRALB w0, w1, [sp]
LDCLRLB w0, w1, [sp]
LDCLRH w0, w1, [sp]
LDCLRAH w0, w1, [sp]
LDCLRALH w0, w1, [sp]
LDCLRLH w0, w1, [sp]
LDCLRP x0, x1, [sp]
LDCLRPA x0, x1, [sp]
LDCLRPAL x0, x1, [sp]
LDCLRPL x0, x1, [sp]
LDEOR w0, w1, [sp]
LDEORA w0, w1, [sp]
LDEORAL w0, w1, [sp]
LDEORL w0, w1, [sp]
LDEOR x0, x1, [sp]
LDEORA x0, x1, [sp]
LDEORAL x0, x1, [sp]
LDEORL x0, x1, [sp]
LDEORB w0, w1, [sp]
LDEORAB w0, w1, [sp]
LDEORALB w0, w1, [sp]
LDEORLB w0, w1, [sp]
LDEORH w0, w1, [sp]
LDEORAH w0, w1, [sp]
LDEORALH w0, w1, [sp]
LDEORLH w0, w1, [sp]
LDFADD h0, h1, [sp]
LDFADDA h0, h1, [sp]
LDFADDAL h0, h1, [sp]
LDFADDL h0, h1, [sp]
LDFADD 0, s1, [sp]
LDFADDA 0, s1, [sp]
LDFADDAL 0, s1, [sp]
LDFADDL 0, s1, [sp]
LDFADD 0, d1, [sp]
LDFADDA 0, d1, [sp]
LDFADDAL 0, d1, [sp]
LDFADDL 0, d1, [sp]
LDFMAX h0, h1, [sp]
LDFMAXA h0, h1, [sp]
LDFMAXAL h0, h1, [sp]
LDFMAXL h0, h1, [sp]
LDFMAX 0, s1, [sp]
LDFMAXA 0, s1, [sp]
LDFMAXAL 0, s1, [sp]
LDFMAXL 0, s1, [sp]
LDFMAX 0, d1, [sp]
LDFMAXA 0, d1, [sp]
LDFMAXAL 0, d1, [sp]
LDFMAXL 0, d1, [sp]
LDFMAXNM h0, h1, [sp]
LDFMAXNMA h0, h1, [sp]
LDFMAXNMAL h0, h1, [sp]
LDFMAXNML h0, h1, [sp]
LDFMAXNM 0, s1, [sp]
LDFMAXNMA 0, s1, [sp]
LDFMAXNMAL 0, s1, [sp]
LDFMAXNML 0, s1, [sp]
LDFMAXNM 0, d1, [sp]
LDFMAXNMA 0, d1, [sp]
LDFMAXNMAL 0, d1, [sp]
LDFMAXNML 0, d1, [sp]
LDFMIN h0, h1, [sp]
LDFMINA h0, h1, [sp]
LDFMINAL h0, h1, [sp]
LDFMINL h0, h1, [sp]
LDFMIN 0, s1, [sp]
LDFMINA 0, s1, [sp]
LDFMINAL 0, s1, [sp]
LDFMINL 0, s1, [sp]
LDFMIN 0, d1, [sp]
LDFMINA 0, d1, [sp]
LDFMINAL 0, d1, [sp]
LDFMINL 0, d1, [sp]
LDFMINNM h0, h1, [sp]
LDFMINNMA h0, h1, [sp]
LDFMINNMAL h0, h1, [sp]
LDFMINNML h0, h1, [sp]
LDFMINNM 0, s1, [sp]
LDFMINNMA 0, s1, [sp]
LDFMINNMAL 0, s1, [sp]
LDFMINNML 0, s1, [sp]
LDFMINNM 0, d1, [sp]
LDFMINNMA 0, d1, [sp]
LDFMINNMAL 0, d1, [sp]
LDFMINNML 0, d1, [sp]
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
LDRAA x0, [sp, #0]
LDRAA x0, [sp, #0]!
LDRAB x0, [sp, #0]
LDRAB x0, [sp, #0]!
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
LDSET w0, w1, [sp]
LDSETA w0, w1, [sp]
LDSETAL w0, w1, [sp]
LDSETL w0, w1, [sp]
LDSET x0, x1, [sp]
LDSETA x0, x1, [sp]
LDSETAL x0, x1, [sp]
LDSETL x0, x1, [sp]
LDSETB w0, w1, [sp]
LDSETAB w0, w1, [sp]
LDSETALB w0, w1, [sp]
LDSETLB w0, w1, [sp]
LDSETH w0, w1, [sp]
LDSETAH w0, w1, [sp]
LDSETALH w0, w1, [sp]
LDSETLH w0, w1, [sp]
LDSETP x0, x1, [sp]
LDSETPA x0, x1, [sp]
LDSETPAL x0, x1, [sp]
LDSETPL x0, x1, [sp]
LDSMAX w0, w1, [sp]
LDSMAXA w0, w1, [sp]
LDSMAXAL w0, w1, [sp]
LDSMAXL w0, w1, [sp]
LDSMAX x0, x1, [sp]
LDSMAXA x0, x1, [sp]
LDSMAXAL x0, x1, [sp]
LDSMAXL x0, x1, [sp]
LDSMAXB w0, w1, [sp]
LDSMAXAB w0, w1, [sp]
LDSMAXALB w0, w1, [sp]
LDSMAXLB w0, w1, [sp]
LDSMAXH w0, w1, [sp]
LDSMAXAH w0, w1, [sp]
LDSMAXALH w0, w1, [sp]
LDSMAXLH w0, w1, [sp]
LDSMIN w0, w1, [sp]
LDSMINA w0, w1, [sp]
LDSMINAL w0, w1, [sp]
LDSMINL w0, w1, [sp]
LDSMIN x0, x1, [sp]
LDSMINA x0, x1, [sp]
LDSMINAL x0, x1, [sp]
LDSMINL x0, x1, [sp]
LDSMINB w0, w1, [sp]
LDSMINAB w0, w1, [sp]
LDSMINALB w0, w1, [sp]
LDSMINLB w0, w1, [sp]
LDSMINH w0, w1, [sp]
LDSMINAH w0, w1, [sp]
LDSMINALH w0, w1, [sp]
LDSMINLH w0, w1, [sp]
LDTADD w0, w1, [sp]
LDTADDA w0, w1, [sp]
LDTADDAL w0, w1, [sp]
LDTADDL w0, w1, [sp]
LDTADD x0, x1, [sp]
LDTADDA x0, x1, [sp]
LDTADDAL x0, x1, [sp]
LDTADDL x0, x1, [sp]
LDTCLR w0, w1, [sp]
LDTCLRA w0, w1, [sp]
LDTCLRAL w0, w1, [sp]
LDTCLRL w0, w1, [sp]
LDTCLR x0, x1, [sp]
LDTCLRA x0, x1, [sp]
LDTCLRAL x0, x1, [sp]
LDTCLRL x0, x1, [sp]
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
LDTSET w0, w1, [sp]
LDTSETA w0, w1, [sp]
LDTSETAL w0, w1, [sp]
LDTSETL w0, w1, [sp]
LDTSET x0, x1, [sp]
LDTSETA x0, x1, [sp]
LDTSETAL x0, x1, [sp]
LDTSETL x0, x1, [sp]
LDTXR w0, [sp, #0]
LDTXR x0, [sp, #0]
LDUMAX w0, w1, [sp]
LDUMAXA w0, w1, [sp]
LDUMAXAL w0, w1, [sp]
LDUMAXL w0, w1, [sp]
LDUMAX x0, x1, [sp]
LDUMAXA x0, x1, [sp]
LDUMAXAL x0, x1, [sp]
LDUMAXL x0, x1, [sp]
LDUMAXB w0, w1, [sp]
LDUMAXAB w0, w1, [sp]
LDUMAXALB w0, w1, [sp]
LDUMAXLB w0, w1, [sp]
LDUMAXH w0, w1, [sp]
LDUMAXAH w0, w1, [sp]
LDUMAXALH w0, w1, [sp]
LDUMAXLH w0, w1, [sp]
LDUMIN w0, w1, [sp]
LDUMINA w0, w1, [sp]
LDUMINAL w0, w1, [sp]
LDUMINL w0, w1, [sp]
LDUMIN x0, x1, [sp]
LDUMINA x0, x1, [sp]
LDUMINAL x0, x1, [sp]
LDUMINL x0, x1, [sp]
LDUMINB w0, w1, [sp]
LDUMINAB w0, w1, [sp]
LDUMINALB w0, w1, [sp]
LDUMINLB w0, w1, [sp]
LDUMINH w0, w1, [sp]
LDUMINAH w0, w1, [sp]
LDUMINALH w0, w1, [sp]
LDUMINLH w0, w1, [sp]
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
PACDA x0, sp
PACDZA x0
PACDB x0, sp
PACDZB x0
PACGA x0, x1, sp
PACIA x0, sp
PACIZA x0
PACIA1716
PACIASP
PACIAZ
PACIA171615
PACIASPPC
PACIB x0, sp
PACIZB x0
PACIB1716
PACIBSP
PACIBZ
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
RAX1 v0.2D, v1.2D, v2.2D
RBIT v0.4s, v2.4s
RBIT w0, w1
RBIT x0, x1
RCWCAS x0, x1, [sp]
RCWCASA x0, x1, [sp]
RCWCASAL x0, x1, [sp]
RCWCASL x0, x1, [sp]
RCWCASP x0, 0, x2, 0, [sp]
RCWCASPA x0, 0, x2, 0, [sp]
RCWCASPAL x0, 0, x2, 0, [sp]
RCWCASPL x0, 0, x2, 0, [sp]
RCWCLR x0, x1, [sp]
RCWCLRA x0, x1, [sp]
RCWCLRAL x0, x1, [sp]
RCWCLRL x0, x1, [sp]
RCWCLRP x0, x1, [sp]
RCWCLRPA x0, x1, [sp]
RCWCLRPAL x0, x1, [sp]
RCWCLRPL x0, x1, [sp]
RCWSCAS x0, x1, [sp]
RCWSCASA x0, x1, [sp]
RCWSCASAL x0, x1, [sp]
RCWSCASL x0, x1, [sp]
RCWSCASP x0, 0, x2, 0, [sp]
RCWSCASPA x0, 0, x2, 0, [sp]
RCWSCASPAL x0, 0, x2, 0, [sp]
RCWSCASPL x0, 0, x2, 0, [sp]
RCWSCLR x0, x1, [sp]
RCWSCLRA x0, x1, [sp]
RCWSCLRAL x0, x1, [sp]
RCWSCLRL x0, x1, [sp]
RCWSCLRP x0, x1, [sp]
RCWSCLRPA x0, x1, [sp]
.Lmicroprobe_catalog_target:
nop
