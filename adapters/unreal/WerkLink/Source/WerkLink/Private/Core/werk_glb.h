// GLB (glTF 2.0 binary), the subset MINI-SPECS.md section 10 pins.
//
// Engine-free, so the gate can parse the golden fixture's geometry without an
// editor, and so the importer and the exporter share one parser rather than
// two that disagree.
//
// The mesh comes out in WERK model space: metres, +Y up, -Z forward, +X right,
// counter-clockwise front faces. Converting to Unreal is werk_basis.h's job
// and happens in the UE layer, exactly once, so that a reader of this file
// never has to wonder which space it is holding.
//
// SPEC.md 3.10 is what makes this parser small enough to be worth writing:
//   * every primitive is mode 4 (triangles) with an indices accessor of
//     component type 5123 or 5125 -- non-indexed primitives are not conformant
//   * POSITION is VEC3 f32 and is required; NORMAL is required for
//     core.geom.game and core.geom.lod but NOT for core.geom.source (S-9)
//   * TANGENT, when present, is VEC4 f32 with w = +/-1 exactly
//   * TEXCOORD_0 is the material UV set; COLOR_0 is LINEAR, never sRGB
//   * materials, textures, skins and animations in the GLB are NOT
//     authoritative -- core.material, core.skeleton and core.anim.clip are

#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "werk_basis.h"
#include "werk_report.h"

namespace werk
{

struct GlbPrimitive
{
    // All arrays are in werk model space and are parallel by vertex index.
    std::vector<float>        positions;  // 3 per vertex, metres
    std::vector<float>        normals;    // 3 per vertex, may be empty
    std::vector<float>        tangents;   // 4 per vertex (xyz + sign), may be empty
    std::vector<float>        uv0;        // 2 per vertex, may be empty
    std::vector<float>        uv1;        // 2 per vertex, may be empty
    std::vector<float>        colors;     // 4 per vertex, LINEAR, may be empty
    std::vector<unsigned int> indices;    // 3 per triangle, ccw in werk space

    size_t VertexCount() const { return positions.size() / 3; }
    size_t TriangleCount() const { return indices.size() / 3; }
};

struct GlbMesh
{
    std::vector<GlbPrimitive> primitives;
    std::string generator;

    size_t TotalVertices() const
    {
        size_t N = 0;
        for (const GlbPrimitive& P : primitives)
        {
            N += P.VertexCount();
        }
        return N;
    }
    size_t TotalTriangles() const
    {
        size_t N = 0;
        for (const GlbPrimitive& P : primitives)
        {
            N += P.TriangleCount();
        }
        return N;
    }
};

// Parses a GLB. bRequireNormals is the SPEC.md 3.10 distinction: true for
// core.geom.game and core.geom.lod, false for core.geom.source. Returns false
// only when nothing could be read; a primitive that fails leaves a report
// entry and the others still load.
bool GlbRead(const std::vector<uint8_t>& Bytes, bool bRequireNormals,
             GlbMesh& Out, const std::string& Subject, Report& Rep);

// Writes a GLB with one mesh, one node, one scene: JSON chunk padded with
// spaces, BIN chunk padded with zeros, one buffer with no uri, tightly packed
// accessors, min/max on POSITION (glTF requires it there and only there).
bool GlbWrite(const GlbMesh& Mesh, std::vector<uint8_t>& Out, const std::string& NodeName,
              const std::string& Generator, Report& Rep);

std::vector<std::string> GlbSelftest(bool bVerbose = false);

} // namespace werk
