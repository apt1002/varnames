/* Small OpenMP kernels for spherical K-means + silhouette.
 *
 * The host's BLAS is reference (netlib) BLAS (~0.2 GFLOP/s), which is far too
 * slow for the O(n^2) silhouette and for many restarts of K-means at n ~ 1e4.
 * These hand-written kernels are compiled with -O3 -march=native -fopenmp and
 * loaded through ctypes; the Python code falls back to NumPy if compilation is
 * unavailable.
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

/* sums[j,t] = sum of X[i,t] over i with labels[i] == j  (k*d doubles, zeroed) */
void accumulate(const float *X, int n, int d, const int *labels, int k,
                double *sums) {
    memset(sums, 0, sizeof(double) * (size_t)k * d);
#pragma omp parallel
    {
        double *loc = (double *)calloc((size_t)k * d, sizeof(double));
#pragma omp for schedule(static)
        for (int i = 0; i < n; i++) {
            const float *xi = X + (size_t)i * d;
            double *l = loc + (size_t)labels[i] * d;
            for (int t = 0; t < d; t++) l[t] += xi[t];
        }
#pragma omp critical
        for (size_t t = 0; t < (size_t)k * d; t++) sums[t] += loc[t];
        free(loc);
    }
}

/* Per-query silhouette on the sphere.
 *
 * For each query row i, distances d(i,j) = sqrt(2 - 2 Q_i . X_j) are accumulated
 * per cluster label of X.  a(i) = mean distance to the *other* members of its own
 * cluster; b(i) = min over other clusters of the mean distance to that cluster.
 * score = (b - a) / max(a, b).  n_c[c] is the size (over X) of cluster c.
 * When Q == X the query labels lq == lx and this is the exact silhouette.
 */
void silhouette_rows(const float *Q, int nq, const float *X, int n, int d,
                     const int *lq, const int *lx, int k, const int *n_c,
                     float *out) {
#pragma omp parallel for schedule(dynamic)
    for (int i = 0; i < nq; i++) {
        const float *qi = Q + (size_t)i * d;
        double *acc = (double *)calloc((size_t)k, sizeof(double));
        for (int j = 0; j < n; j++) {
            const float *xj = X + (size_t)j * d;
            float dot = 0.0f;
            for (int t = 0; t < d; t++) dot += qi[t] * xj[t];
            float dd = 2.0f - 2.0f * dot;
            if (dd < 0.0f) dd = 0.0f;
            acc[lx[j]] += sqrt((double)dd);
        }
        int li = lq[i];
        int nc = n_c[li];
        double a = nc > 1 ? acc[li] / (nc - 1) : 0.0;
        double b = 1e300;
        for (int c = 0; c < k; c++) {
            if (c == li || n_c[c] == 0) continue;
            double m = acc[c] / n_c[c];
            if (m < b) b = m;
        }
        double mx = a > b ? a : b;
        out[i] = mx > 0.0 ? (float)((b - a) / mx) : 0.0f;
        free(acc);
    }
}
