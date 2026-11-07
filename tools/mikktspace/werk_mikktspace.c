/* werk_mikktspace.c — the werk pipeline's shim around the reference
 * MikkTSpace implementation (mikktspace.c / mikktspace.h, vendored beside this
 * file, unmodified, Morten S. Mikkelsen, zlib-style licence — see LICENSE.txt).
 *
 * The reference implementation is callback-driven, which is awkward to drive
 * from ctypes. So the callbacks live HERE, in C, over flat arrays, and the
 * library exposes exactly one entry point:
 *
 *   werk_mikktspace(pos, nrm, uv, idx, ntri, out_tan)
 *
 * pos/nrm are 3 floats per vertex, uv 2 floats per vertex, idx 3 uint32 per
 * triangle. out_tan receives FOUR floats per FACE CORNER (3 corners per
 * triangle, so 12 floats per triangle): tangent xyz plus the sign w in the
 * glTF convention, which is MikkTSpace's own fSign unchanged — both define
 * bitangent = w * cross(normal, tangent).
 *
 * Per-corner, not per-vertex, on purpose: MikkTSpace's whole point is that the
 * basis is discontinuous across a UV chart seam, so the caller has to be told
 * the per-corner answer and decide whether to split the vertex. Averaging the
 * corners back down here would throw away the one thing this file exists for.
 */

#include <string.h>
#include "mikktspace.h"

typedef struct {
    const float *pos;
    const float *nrm;
    const float *uv;
    const unsigned int *idx;
    int ntri;
    float *out;   /* 12 floats per triangle */
} werk_mesh;

static int wk_num_faces(const SMikkTSpaceContext *ctx)
{
    return ((const werk_mesh *)ctx->m_pUserData)->ntri;
}

static int wk_num_verts_of_face(const SMikkTSpaceContext *ctx, const int f)
{
    (void)ctx; (void)f;
    return 3;
}

static unsigned int wk_index(const werk_mesh *m, int f, int v)
{
    return m->idx[(size_t)f * 3 + (size_t)v];
}

static void wk_get_position(const SMikkTSpaceContext *ctx, float out[],
                            const int f, const int v)
{
    const werk_mesh *m = (const werk_mesh *)ctx->m_pUserData;
    const float *p = m->pos + (size_t)wk_index(m, f, v) * 3;
    out[0] = p[0]; out[1] = p[1]; out[2] = p[2];
}

static void wk_get_normal(const SMikkTSpaceContext *ctx, float out[],
                          const int f, const int v)
{
    const werk_mesh *m = (const werk_mesh *)ctx->m_pUserData;
    const float *p = m->nrm + (size_t)wk_index(m, f, v) * 3;
    out[0] = p[0]; out[1] = p[1]; out[2] = p[2];
}

static void wk_get_texcoord(const SMikkTSpaceContext *ctx, float out[],
                            const int f, const int v)
{
    const werk_mesh *m = (const werk_mesh *)ctx->m_pUserData;
    const float *p = m->uv + (size_t)wk_index(m, f, v) * 2;
    out[0] = p[0]; out[1] = p[1];
}

static void wk_set_tspace_basic(const SMikkTSpaceContext *ctx,
                                const float tangent[], const float sign,
                                const int f, const int v)
{
    werk_mesh *m = (werk_mesh *)ctx->m_pUserData;
    float *o = m->out + ((size_t)f * 3 + (size_t)v) * 4;
    o[0] = tangent[0]; o[1] = tangent[1]; o[2] = tangent[2]; o[3] = sign;
}

#if defined(_WIN32)
#  define WERK_EXPORT __declspec(dllexport)
#else
#  define WERK_EXPORT __attribute__((visibility("default")))
#endif

/* Returns 1 on success, 0 if the reference implementation refused the mesh. */
WERK_EXPORT int werk_mikktspace(const float *pos, const float *nrm,
                                const float *uv, const unsigned int *idx,
                                int ntri, float *out_tan)
{
    werk_mesh mesh;
    SMikkTSpaceInterface iface;
    SMikkTSpaceContext ctx;

    memset(&iface, 0, sizeof(iface));
    memset(&ctx, 0, sizeof(ctx));

    mesh.pos = pos; mesh.nrm = nrm; mesh.uv = uv; mesh.idx = idx;
    mesh.ntri = ntri; mesh.out = out_tan;

    iface.m_getNumFaces          = wk_num_faces;
    iface.m_getNumVerticesOfFace = wk_num_verts_of_face;
    iface.m_getPosition          = wk_get_position;
    iface.m_getNormal            = wk_get_normal;
    iface.m_getTexCoord          = wk_get_texcoord;
    iface.m_setTSpaceBasic       = wk_set_tspace_basic;

    ctx.m_pInterface = &iface;
    ctx.m_pUserData  = &mesh;

    return genTangSpaceDefault(&ctx) ? 1 : 0;
}

/* Version of the reference implementation this shim was built against. */
WERK_EXPORT const char *werk_mikktspace_version(void)
{
    return "mikktspace/1.0";
}
