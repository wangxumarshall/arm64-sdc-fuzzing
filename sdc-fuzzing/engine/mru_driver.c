/* mru_driver.c — Parameterized Eigen-machine-code driver for core-179 SDC
 *                reproduction cases (sdc-fuzzing).
 *
 * This is the parameterized generalization of mru_eigenmc.c: instead of
 * hard-coded N=256 / density=0.1 / seed, every dimension is a CLI argument.
 * The triggering Eigen machine code (eigen_cabidrv.o) is SHARED and UNCHANGED
 * across all 100 cases — only the matrix dimensions, seeds, mode, and iteration
 * count vary. This keeps the trigger signature constant (DESIGN.md §4, F1).
 *
 * The corruption signature (per the root-cause report) is fixed at x[0] and is
 * multi-bit data-aliasing. We CRC the whole result vector x and compare to a
 * golden reference computed once up front; any mismatch = a reproduction
 * (corruption is always at elem[0], which is inside the CRC window).
 *
 * Usage:
 *   ./mrueig <iters K> <matrix_seed ms> <rhs_seed s> [N] [density_p] [diag_d] [mode]
 *     defaults: N=256, density_p=0.10, diag_d=2.0, mode=1
 *     mode 1 = analyzePattern ONCE then factorize()+solve() repeated (numeric-only, highest trigger rate)
 *     mode 0 = analyzePattern()+factorize()+solve() each iter (compute-both, ~1/4 rate)
 *
 * Build: gcc -O2 -march=armv8.1-a+crc+crypto -std=gnu17 -ffp-contract=fast \
 *          mru_driver.c eigen_cabidrv.o -o mrueig -lm
 *
 * Exit: number of fails (>0 => reproduction observed). Prints "<fails>\n" to stdout
 *       for machine parsing; human detail to stderr.
 */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <arm_acle.h>

/* C ABI to the Eigen machine-code wrapper (eigen_cabidrv.o). Unchanged across
 * all cases — this is the constant trigger signature. */
extern void* escnew_solver(void);
extern void  escfree_solver(void* s);
extern int   escanalyze(void* s, const int* Ap, const int* Ai, const double* Ax, int n, int nnz);
extern int   escfactorize(void* s, const int* Ap, const int* Ai, const double* Ax, int n, int nnz);
extern int   escsolve(void* s, const double* b, double* x, int n);

/* ---- runtime-configurable parameters (from argv) ---- */
static int    g_N = 256;
static double g_density = 0.10;
static double g_diag = 2.0;
static int    g_mode = 1;            /* 1=numeric-only, 0=compute-both */
static uint32_t g_mseed = 12345;    /* matrix structure seed */
static uint32_t g_rseed = 99999;    /* rhs b seed */

/* ---- matrix workspace (allocated at runtime for the given N) ---- */
static int     *Ap, *Ai;
static double  *Ax, *bvec;

/* simple LCG, deterministic, no Date/random (workflow-safe) */
static uint32_t rng_state = 12345;
static double frand(void){ rng_state = rng_state*1103515245u + 12345u; return ((rng_state>>8)&0xffffff)/(double)0x1000000; }

/* Build an SPD sparse CSC lower-triangle matrix A (diag-dominant), mirroring
 * mru_eigenmc.c but parameterized on N/density/diag. Structure from g_mseed,
 * values from the same stream; b from g_rseed. */
static void build_matrix(void){
    int maxnnz = g_N * 128;   /* generous upper bound on nonzeros */
    Ap = malloc((g_N+1)*sizeof(int));
    Ai = malloc(maxnnz*sizeof(int));
    Ax = malloc(maxnnz*sizeof(double));
    bvec = malloc(g_N*sizeof(double));
    if(!Ap||!Ai||!Ax||!bvec){ fprintf(stderr,"alloc fail\n"); exit(2); }

    rng_state = g_mseed;
    int nz = 0; Ap[0] = 0;
    for(int j=0;j<g_N;j++){
        Ai[nz] = j; Ax[nz] = 0; nz++;                 /* diagonal placeholder */
        for(int i=j+1;i<g_N;i++){
            if(frand() < g_density){ Ai[nz]=i; Ax[nz]=frand()-0.5; nz++; }
        }
        Ap[j+1] = nz;
        if(nz >= maxnnz-1){ fprintf(stderr,"nnz overflow (raise maxnnz)\n"); exit(2); }
    }
    /* diag-dominant SPD: Ax[diag] = sum of |off-diag| + g_diag */
    for(int j=0;j<g_N;j++){
        double s=0;
        for(int p=Ap[j];p<Ap[j+1];p++){ if(Ai[p]!=j) s += fabs(Ax[p]); }
        Ax[Ap[j]] = s + g_diag;
    }
    /* rhs b from a separate seed */
    rng_state = g_rseed;
    for(int i=0;i<g_N;i++) bvec[i]=frand()-0.5;
}

static uint32_t crc_x(const double*x, int n){
    uint32_t c=0xffffffffu; const uint8_t*p=(const uint8_t*)x;
    for(int i=0;i<n*8;i++) c=__crc32cb(c,p[i]);
    return ~c;
}

int main(int argc,char**argv){
    if(argc < 3){ fprintf(stderr,"usage: %s <iters> <matrix_seed> [rhs_seed] [N] [density] [diag] [mode]\n",argv[0]); return 2; }
    int iters = atoi(argv[1]);
    g_mseed = (uint32_t)strtoul(argv[2],0,10);
    if(argc > 3) g_rseed = (uint32_t)strtoul(argv[3],0,10);
    if(argc > 4) g_N = atoi(argv[4]);
    if(argc > 5) g_density = atof(argv[5]);
    if(argc > 6) g_diag = atof(argv[6]);
    if(argc > 7) g_mode = atoi(argv[7]);

    if(g_N < 256){ fprintf(stderr,"WARN: N=%d < 256 (root-cause threshold); may not trigger\n",g_N); }
    if(g_density <= 0 || g_density > 0.5){ fprintf(stderr,"WARN: density=%g unusual\n",g_density); }

    build_matrix();
    int nnz = Ap[g_N];

    void* s = escnew_solver();
    if(!s){ fprintf(stderr,"alloc solver fail\n"); return 2; }

    /* golden: analyze + factorize + solve once (mode 1 path) */
    if(escanalyze(s, Ap, Ai, Ax, g_N, nnz)){ fprintf(stderr,"analyze fail\n"); escfree_solver(s); return 2; }
    if(escfactorize(s, Ap, Ai, Ax, g_N, nnz)){ fprintf(stderr,"factorize fail (golden)\n"); escfree_solver(s); return 2; }
    double* golden = malloc(g_N*sizeof(double));
    escsolve(s, bvec, golden, g_N);
    uint32_t gcrc = crc_x(golden, g_N);
    fprintf(stderr,"sdc-fuzzing MRU: N=%d nnz=%d density=%.3f diag=%.1f mode=%d ms=%u rs=%u\n",
            g_N, nnz, g_density, g_diag, g_mode, g_mseed, g_rseed);
    fprintf(stderr,"golden x-crc=0x%08x x[0]=%.17g\n", gcrc, golden[0]);

    /* mode 1: analyzePattern done ONCE (above), repeat factorize()+solve().
     * mode 0: redo analyzePattern()+factorize()+solve() each iter (compute-both). */
    int fail = 0;
    double* x = malloc(g_N*sizeof(double));
    for(int k=0;k<iters;k++){
        if(g_mode == 0){
            escanalyze(s, Ap, Ai, Ax, g_N, nnz);   /* symbolic refresh (lowers trigger rate, F6) */
        }
        if(escfactorize(s, Ap, Ai, Ax, g_N, nnz)){ fail++; continue; }
        escsolve(s, bvec, x, g_N);
        uint32_t c = crc_x(x, g_N);
        if(c != gcrc){
            fail++;
            if(fail <= 8) fprintf(stderr,"k=%d x-crc mismatch (0x%08x vs 0x%08x) x[0]=%.6g (golden %.6g)\n",
                                  k, c, gcrc, x[0], golden[0]);
        }
    }
    free(x);
    free(golden);
    escfree_solver(s);
    free(Ap); free(Ai); free(Ax); free(bvec);

    fprintf(stderr,"RESULT core179-repro: %d/%d fails (rate=%.4f)\n", fail, iters, (double)fail/iters);
    printf("%d\n", fail);   /* machine-parseable: stdout = fail count */
    return fail>0;
}
