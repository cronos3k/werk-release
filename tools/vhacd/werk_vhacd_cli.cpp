/* werk_vhacd_cli.cpp — a thin CLI around the real V-HACD.
 *
 * V-HACD v4.1 (Khaled Mamou, BSD-3-Clause) ships as ONE header, VHACD.h, which
 * is vendored beside this file unmodified. This translation unit is the only
 * place that defines ENABLE_VHACD_IMPLEMENTATION, so the whole algorithm is
 * compiled here and nowhere else.
 *
 * Why a CLI and not a DLL: V-HACD runs a thread pool and allocates through the
 * C++ runtime. A process boundary means a decomposition that asserts, hangs or
 * blows the stack on a hostile mesh takes the child down and the pipeline sees
 * a non-zero exit code, instead of taking the pipeline down with it.
 *
 * Usage:  werk_vhacd <in.bin> <out.bin>
 *
 * in.bin  : "WKVH" | u32 nverts | u32 ntris | u32 maxHulls | u32 resolution
 *           | u32 maxVertsPerHull | u32 fillMode(0 flood,1 surface,2 raycast)
 *           | u32 maxRecursionDepth | u32 findBestPlane(0/1)
 *           | f64 minVolumePercentError
 *           | f64[3*nverts] positions | u32[3*ntris] indices
 * out.bin : "WKVO" | u32 nhulls | per hull:
 *           u32 npoints | u32 ntris | f64[3*np] | u32[3*nt]
 *           | f64 volume | f64[3] center
 *
 * Binary rather than the stock OBJ front end because the pipeline's mesh is
 * already an array pair in memory and round-tripping it through ASCII would
 * quantise the vertices before V-HACD ever saw them.
 */

#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <vector>

#define ENABLE_VHACD_IMPLEMENTATION 1
#include "VHACD.h"

namespace {

template <typename T>
bool readv(FILE *f, std::vector<T> &v, size_t n)
{
    v.resize(n);
    return n == 0 || std::fread(v.data(), sizeof(T), n, f) == n;
}

template <typename T>
void writev(FILE *f, const T *p, size_t n)
{
    if (n) std::fwrite(p, sizeof(T), n, f);
}

void writeu32(FILE *f, uint32_t v) { std::fwrite(&v, sizeof(v), 1, f); }
void writef64(FILE *f, double v)   { std::fwrite(&v, sizeof(v), 1, f); }

} // namespace

int main(int argc, char **argv)
{
    if (argc != 3) {
        std::fprintf(stderr, "usage: werk_vhacd <in.bin> <out.bin>\n");
        return 2;
    }

    FILE *in = std::fopen(argv[1], "rb");
    if (!in) { std::fprintf(stderr, "cannot open %s\n", argv[1]); return 3; }

    char magic[4] = {0, 0, 0, 0};
    if (std::fread(magic, 1, 4, in) != 4 || std::memcmp(magic, "WKVH", 4) != 0) {
        std::fprintf(stderr, "bad input magic\n"); std::fclose(in); return 4;
    }

    uint32_t hdr[8];
    double minVolErr = 1.0;
    if (std::fread(hdr, sizeof(uint32_t), 8, in) != 8 ||
        std::fread(&minVolErr, sizeof(double), 1, in) != 1) {
        std::fprintf(stderr, "short header\n"); std::fclose(in); return 4;
    }
    const uint32_t nverts = hdr[0], ntris = hdr[1];

    std::vector<double>   pos;
    std::vector<uint32_t> idx;
    if (!readv(in, pos, (size_t)nverts * 3) || !readv(in, idx, (size_t)ntris * 3)) {
        std::fprintf(stderr, "short mesh payload\n"); std::fclose(in); return 4;
    }
    std::fclose(in);

    VHACD::IVHACD::Parameters p;
    p.m_maxConvexHulls    = hdr[2];
    p.m_resolution        = hdr[3];
    p.m_maxNumVerticesPerCH = hdr[4];
    p.m_fillMode          = hdr[5] == 1 ? VHACD::FillMode::SURFACE_ONLY
                          : hdr[5] == 2 ? VHACD::FillMode::RAYCAST_FILL
                                        : VHACD::FillMode::FLOOD_FILL;
    p.m_maxRecursionDepth = hdr[6];
    p.m_findBestPlane     = hdr[7] != 0;
    p.m_minimumVolumePercentErrorAllowed = minVolErr;
    p.m_shrinkWrap        = true;
    p.m_asyncACD          = false;   /* deterministic, single-threaded ACD */

    VHACD::IVHACD *iface = VHACD::CreateVHACD();
    if (!iface) { std::fprintf(stderr, "CreateVHACD failed\n"); return 5; }

    if (!iface->Compute(pos.data(), nverts, idx.data(), ntris, p)) {
        std::fprintf(stderr, "Compute returned false\n");
        iface->Release();
        return 6;
    }

    const uint32_t n = iface->GetNConvexHulls();
    FILE *out = std::fopen(argv[2], "wb");
    if (!out) { std::fprintf(stderr, "cannot write %s\n", argv[2]); iface->Release(); return 7; }
    std::fwrite("WKVO", 1, 4, out);
    writeu32(out, n);

    for (uint32_t i = 0; i < n; ++i) {
        VHACD::IVHACD::ConvexHull ch;
        if (!iface->GetConvexHull(i, ch)) {
            std::fprintf(stderr, "GetConvexHull(%u) failed\n", i);
            std::fclose(out); iface->Release(); return 8;
        }
        writeu32(out, (uint32_t)ch.m_points.size());
        writeu32(out, (uint32_t)ch.m_triangles.size());
        for (size_t k = 0; k < ch.m_points.size(); ++k) {
            writef64(out, ch.m_points[k].mX);
            writef64(out, ch.m_points[k].mY);
            writef64(out, ch.m_points[k].mZ);
        }
        for (size_t k = 0; k < ch.m_triangles.size(); ++k) {
            writeu32(out, ch.m_triangles[k].mI0);
            writeu32(out, ch.m_triangles[k].mI1);
            writeu32(out, ch.m_triangles[k].mI2);
        }
        writef64(out, ch.m_volume);
        writef64(out, ch.m_center.GetX());
        writef64(out, ch.m_center.GetY());
        writef64(out, ch.m_center.GetZ());
    }
    std::fclose(out);

    std::fprintf(stdout, "vhacd %u.%u hulls=%u\n",
                 VHACD_VERSION_MAJOR, VHACD_VERSION_MINOR, n);
    iface->Release();
    (void)writev<double>;
    return 0;
}
