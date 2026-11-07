#!/usr/bin/env python3
"""p_geom.py — core.geom.source and core.geom.game.

`source` is the input GLB, byte for byte. It is the archival anchor and it is
never touched: whatever the pipeline gets wrong downstream, the thing it was
handed is still in the file.

`game` is the renderable mesh: welded, with normals where the input had none,
with a tangent basis, and written as one primitive with no extensions. It is
what `primary.mesh` points at and what every other producer measures.
"""

import numpy as np

from . import glb, meshops as M, mikktspace as MT


def run(ctx, scene, glb_bytes, source_name):
    src_f = ctx.put("geometry/source.glb", glb_bytes)
    ctx.node("geom-source", "core.geom.source",
             ctx.version([src_f],
                         "The input GLB, byte for byte. %d primitives, %d "
                         "vertices, %d triangles before welding. Never rewritten: "
                         "it is the archival anchor and every derived node below "
                         "names it as an input." %
                         (scene.prim_count, len(scene.pos), len(scene.idx)),
                         "authored"),
             meta={"source_filename": source_name,
                   "primitive_count": scene.prim_count,
                   "vertex_count": int(len(scene.pos)),
                   "triangle_count": int(len(scene.idx)),
                   "had_normals": bool(scene.had_normals),
                   "had_texcoords": bool(scene.had_uv)},
             part="whole")

    pos, idx, extra, _keep = M.weld(scene.pos, scene.idx,
                                    [scene.nrm, scene.uv, scene.col])
    nrm, uv, col = extra
    bad = np.linalg.norm(nrm, axis=1) < 1e-9
    recomputed = int(bad.sum())
    if recomputed:
        vn = M.vertex_normals(pos, idx)
        nrm = np.where(bad[:, None], vn, nrm)
    ln = np.linalg.norm(nrm, axis=1, keepdims=True)
    nrm = nrm / np.maximum(ln, 1e-30)

    has_color = bool(np.any(np.abs(col - 1.0) > 1e-6))

    # -- the tangent basis ------------------------------------------------
    # Ruling 19: the reference MikkTSpace is the default. The vendored C is in
    # tools/mikktspace/ (upstream, unmodified, licence recorded there) and it
    # gives a per-FACE-CORNER answer, so vertices are split where the corners
    # disagree -- which is the entire point: the basis is discontinuous across
    # a UV chart seam and one shared vertex cannot carry both answers.
    #
    # Splitting duplicates vertices; it never moves one. The surface written to
    # geometry/game.glb is bit-identical to the welded surface every other
    # producer measures, which is why the mesh handed downstream stays welded
    # and only the GLB carries the split set.
    #
    # If the library is not built, the old accumulate-then-Gram-Schmidt basis
    # runs and the node RECORDS that it did. The algorithm is never assumed.
    mt_ok, mt_note = MT.available()
    split = MT.tangents_split(pos, nrm, uv, idx, extra=(col,)) if (
        mt_ok and scene.had_uv) else None
    if split is None and mt_ok and not scene.had_uv:
        mt_note = ("the GLB has no TEXCOORD_0; MikkTSpace is defined over a UV "
                   "parameterisation and has nothing to work from")
    elif split is None and mt_ok:
        mt_note = "genTangSpaceDefault refused the mesh"

    if split is not None:
        g_pos, g_idx, g_nrm, g_uv = split["pos"], split["idx"], split["nrm"], split["uv"]
        g_col = split["extra"][0]
        tan = split["tan"]
        degenerate = split["degenerate"]
        tangent_method = split["engine"]
        tangent_meta = {
            "tangent_vertex_splits": split["splits"],
            "tangent_note":
                "The reference MikkTSpace (tools/mikktspace/, upstream and "
                "unmodified) computed the basis per face corner; %d vertices "
                "were duplicated where the corners disagreed, so this GLB has "
                "%d vertices against the welded mesh's %d. Positions were "
                "duplicated, never moved: the surface is identical to the "
                "welded one that every other node measures. TANGENT.w is "
                "MikkTSpace's own fSign, which is glTF's convention unchanged "
                "- both define bitangent = w * cross(N, T)."
                % (split["splits"], split["vertex_count"], len(pos)),
        }
    else:
        g_pos, g_idx, g_nrm, g_uv, g_col = pos, idx, nrm, uv, col
        tan, degenerate = M.tangents(pos, nrm, uv, idx)
        tangent_method = "gram-schmidt-accumulated/0.1"
        tangent_meta = {
            "tangent_vertex_splits": 0,
            "tangent_fallback_reason": mt_note,
            "tangent_note":
                "NOT MikkTSpace: %s. This is the accumulate-then-Gram-Schmidt "
                "basis, which agrees with MikkTSpace wherever the UV chart is "
                "continuous and diverges at chart seams, where MikkTSpace "
                "splits a vertex and this does not." % mt_note,
        }

    game = glb.build_glb(g_pos, g_idx, nrm=g_nrm,
                         uv=g_uv if scene.had_uv else None,
                         col=g_col if has_color else None, tan=tan, name="game")
    game_f = ctx.put("geometry/game.glb", game)
    ctx.node("geom-game", "core.geom.game",
             ctx.version([game_f],
                         "The renderable mesh: welded to %d shared vertices and "
                         "%d triangles, one primitive, no extensions, written "
                         "with %d vertices after the tangent split. %d normals "
                         "were missing and were recomputed area-weighted; the "
                         "tangent basis is %s - see meta.tangent_method and the "
                         "note beside it."
                         % (len(pos), len(idx), len(g_pos), recomputed,
                            tangent_method),
                         "measured", inputs=["geometry/source.glb"],
                         params={"weld_decimals": 6,
                                 "tangent_method": tangent_method}),
             edges=[{"to": "geom-source", "kind": "enhances", "role": "derived-from"}],
             meta=dict({"vertex_count": int(len(g_pos)),
                        "welded_vertex_count": int(len(pos)),
                        "triangle_count": int(len(idx)),
                        "attributes": ["POSITION", "NORMAL", "TANGENT"] +
                                      (["TEXCOORD_0"] if scene.had_uv else []) +
                                      (["COLOR_0"] if has_color else []),
                        "normals_recomputed": recomputed,
                        "tangent_method": tangent_method,
                        "tangent_degenerate_vertices": degenerate},
                       **tangent_meta),
             part="whole")

    # pos/idx/nrm/uv/col are the WELDED mesh: that is what every downstream
    # producer measures, and it is unchanged by the tangent split. `tan` and
    # everything under `render` address the SPLIT vertex set that
    # geometry/game.glb actually carries -- the two index spaces differ
    # whenever tangent_splits > 0, so they are kept apart by name.
    return {"pos": pos, "idx": idx, "nrm": nrm, "uv": uv, "col": col,
            "tan": tan, "has_color": has_color,
            "render": {"pos": g_pos, "idx": g_idx, "nrm": g_nrm, "uv": g_uv,
                       "col": g_col, "tan": tan},
            "normals_recomputed": recomputed,
            "tangent_method": tangent_method,
            "tangent_splits": tangent_meta.get("tangent_vertex_splits", 0),
            "render_vertex_count": int(len(g_pos))}
