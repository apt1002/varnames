/* Small OpenMP kernels for spherical K-means.
 *
 * The host's BLAS is reference (netlib) BLAS (~0.2 GFLOP/s), far too slow for
 * many restarts of K-means at n ~ 1e4.  These hand-written kernels are compiled
 * with -O3 -march=native -fopenmp and loaded through ctypes; the Python code
 * falls back to NumPy if compilation is unavailable.
 *
 * All matrices are row-major float32; labels are int32; accumulators are double.
 */
#include <math.h>
#include <stdlib.h>
#include <string.h>

#ifdef _OPENMP
#include <omp.h>
#endif

/* labels[i] = argmax_j  sum_t X[i,t] * C[j,t]   (nearest centre on the sphere) */
void assign(const float *X, int n, int d, const float *C, int k, int *labels) {
#pragma omp parallel for schedule(static)
    for (int i = 0; i < n; i++) {
        const float *xi = X + (size_t)i * d;
        float best = -3.4e38f;
        int bj = 0;
        for (int j = 0; j < k; j++) {
            const float *cj = C + (size_t)j * d;
            float s = 0.0f;
            for (int t = 0; t < d; t++) s += xi[t] * cj[t];
            if (s > best) { best = s; bj = j; }
        }
        labels[i] = bj;
    }
}

/* out[i] = sum_t X[i,t] * c[t] */
void matvec(const float *X, int n, int d, const float *c, float *out) {
#pragma omp parallel for schedule(static)
    for (int i = 0; i < n; i++) {
        const float *xi = X + (size_t)i * d;
        float s = 0.0f;
        for (int t = 0; t < d; t++) s += xi[t] * c[t];
        out[i] = s;
    }
}

/* sums[j,t] = sum_i w[i] * X[i,t] over i with labels[i] == j  (k*d doubles, zeroed).
 * w[i] is the occurrence weight of point i; pass all-ones for an unweighted mean. */
void accumulate(const float *X, int n, int d, const int *labels, int k,
                const float *w, double *sums) {
    memset(sums, 0, sizeof(double) * (size_t)k * d);
#pragma omp parallel
    {
        double *loc = (double *)calloc((size_t)k * d, sizeof(double));
#pragma omp for schedule(static)
        for (int i = 0; i < n; i++) {
            const float *xi = X + (size_t)i * d;
            double wi = w[i];
            double *l = loc + (size_t)labels[i] * d;
            for (int t = 0; t < d; t++) l[t] += wi * xi[t];
        }
#pragma omp critical
        for (size_t t = 0; t < (size_t)k * d; t++) sums[t] += loc[t];
        free(loc);
    }
}
