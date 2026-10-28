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

/* Per-query silhouette on the sphere, occurrence-weighted.
 *
 * Point i has weight w[i]; the score equals the ordinary silhouette of a
 * multiset in which i is replicated w[i] times, so the per-cluster "size" is the
 * cluster weight wc[c] = sum_{j in c} w[j], distances are accumulated with
 * weight w[j], and out[i] is the silhouette of any one copy of i (they all
 * share the same value).
 *
 *   a(i) = sum_{j in c_i} w[j] d(i,j) / (wc[c_i] - 1)   (own cluster, others)
 *   b(i) = min_{c != c_i} sum_{j in c} w[j] d(i,j) / wc[c]
 *   s(i) = (b - a) / max(a, b)      [0 for a singleton cluster, Rousseeuw]
 *
 * Distance is the chord d(i,j) = sqrt(2 - 2 Q_i . X_j).  The caller forms the
 * weighted mean of out[] with the query weights.  When Q == X and lq == lx this
 * is the exact (weighted) silhouette.
 */
void silhouette_rows(const float *Q, int nq, const float *X, int n, int d,
                     const int *lq, const int *lx, int k, const float *w,
                     const double *wc, float *out) {
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
            acc[lx[j]] += (double)w[j] * sqrt((double)dd);
        }
        int li = lq[i];
        double own = wc[li];
        double a = 0.0, b = 1e300;
        int found = 0;
        if (own > 1.0) a = acc[li] / (own - 1.0);
        for (int c = 0; c < k; c++) {
            if (c == li || wc[c] <= 0.0) continue;
            double m = acc[c] / wc[c];
            if (m < b) { b = m; found = 1; }
        }
        double mx = a > b ? a : b;
        double s = (own <= 1.0 || !found) ? 0.0
                 : (mx > 0.0 ? (b - a) / mx : 0.0);
        out[i] = (float)s;
        free(acc);
    }
}
