#!/usr/bin/env python3
"""enrich.py — bare GLB in, fully-enriched conformant .werk out. Unattended.

    python pipeline/enrich.py <input.glb> <out.werk> [options]

Every producer is an island. A producer that throws is timed, logged into
x/pipeline-report.json with its exact exception, and skipped; the package is
written anyway, missing that node. That is not error handling bolted on the
side, it is the format's law 3 executed: absence is legal, and a pipeline that
died because a convex decomposition was hard would be the wrong shape of tool.

Every derived node carries `input_files`, an `input_hash` over exactly those
files plus its canonical `input_params`, and an epistemic stamp. Nothing is
`measured` unless it is arithmetic over bytes in this package, and nothing a
model said is ever promoted out of `inferred`.

No absolute path is baked in anywhere: the input, the output and the model
endpoints all arrive as arguments or environment, which is what keeps this
hostable somewhere that is not this machine.
"""

import argparse
import json
import os
import platform
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from pipeline.common import (Ctx, Stage, TOOL, TOOL_VERSION, kebab,   # noqa: E402
                             sha256, uuid_from)
from pipeline import (glb, package, p_body, p_bounds, p_collider,     # noqa: E402
                      p_flow, p_geom, p_imposter, p_lod, p_material,
                      p_props, p_restpose, p_semantics, p_texture)


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="a GLB file")
    ap.add_argument("output", help="the .werk to write")
    ap.add_argument("--name", default=None, help="entity name (default: filename)")
    ap.add_argument("--created", default=None,
                    help="ISO timestamp to stamp on every node; default is now. "
                         "Pass a fixed value to make two runs byte-identical.")
    ap.add_argument("--spdx", default=None)
    ap.add_argument("--license-file", default=None)
    ap.add_argument("--lod-levels", type=int, default=4)
    ap.add_argument("--imposter-preview", type=int, default=4,
                    help="preview tier tiles per axis (N)")
    ap.add_argument("--imposter-runtime", type=int, default=8)
    ap.add_argument("--imposter-tile-px", type=int, default=256)
    ap.add_argument("--sse-px", type=int, default=1080,
                    help="silhouette measurement resolution; the profile fixes "
                         "the REPORTED reference at 1080 and lowering this "
                         "makes the number less exact, not cheaper to trust")
    ap.add_argument("--collider-grid", type=int, default=40)
    ap.add_argument("--collider-parts", type=int, default=12)
    ap.add_argument("--flow-grid", type=int, default=32)
    ap.add_argument("--drop-trials", type=int, default=512)
    ap.add_argument("--no-vlm", action="store_true",
                    help="do not contact a vision-language model even if one is "
                         "configured")
    ap.add_argument("--reproducible", action="store_true",
                    help="omit the measured wall times from the package, so "
                         "two runs over one input are byte-identical. Use with "
                         "--created. Nothing else in the package depends on "
                         "the clock or on a random seed.")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    t_start = time.perf_counter()
    started = now_iso()
    with open(args.input, "rb") as fh:
        glb_bytes = fh.read()
    source_name = os.path.basename(args.input)
    stem = os.path.splitext(source_name)[0]
    if stem.lower() in ("model", "scene", "mesh", "untitled", "export", "out"):
        # "model.glb" names nothing; the directory it sits in usually does.
        stem = os.path.basename(os.path.dirname(os.path.abspath(args.input))) or stem
    name = args.name or kebab(stem).replace("-", " ").title()
    ctx = Ctx(created=args.created or started,
              entity_uuid=uuid_from(glb_bytes), name=name,
              record_timings=not args.reproducible)
    ctx.parts = [{"part_id": "whole", "name": name, "parent": None,
                  "transform": {"translation": [0.0, 0.0, 0.0],
                                "rotation": [1.0, 0.0, 0.0, 0.0],
                                "scale": [1.0, 1.0, 1.0]}}]
    verbose = not args.quiet
    if verbose:
        print("werk enrich: %s (%d bytes, sha256 %s)"
              % (source_name, len(glb_bytes), sha256(glb_bytes)[:16]))

    scene = None
    with Stage(ctx, "read-glb", verbose) as st:
        scene = glb.load_scene(glb_bytes)
        st.says("%d primitives, %d vertices, %d triangles, %d materials, "
                "%d images" % (scene.prim_count, len(scene.pos), len(scene.idx),
                               len(scene.materials), len(scene.images)))
    if scene is None:
        print("FATAL: the input is not readable as glTF 2.0; nothing to enrich.")
        return 2

    mesh = bounds = textures = None
    lods = imposter = collider = body = semantics = None
    sampler = None
    material_ids = []

    with Stage(ctx, "geometry", verbose) as st:
        mesh = p_geom.run(ctx, scene, glb_bytes, source_name)
        st.produced("geom-source", "geom-game")
        st.says("%d welded vertices, %d triangles, %d normals recomputed"
                % (len(mesh["pos"]), len(mesh["idx"]), mesh["normals_recomputed"]))
    if mesh is None:
        print("FATAL: the mesh could not be prepared; nothing downstream can run.")
        return 2
    ctx.primary["mesh"] = "geom-game"

    with Stage(ctx, "bounds", verbose) as st:
        bounds = p_bounds.run(ctx, mesh)
        st.produced("bounds")
        st.says("aabb %.4f x %.4f x %.4f m, sphere r=%.4f m, watertight=%s"
                % (*(bounds["aabb_max"] - bounds["aabb_min"]), bounds["radius"],
                   bounds["watertight"]))

    with Stage(ctx, "textures", verbose) as st:
        textures = p_texture.run(ctx, scene)
        st.produced(*[t["node"] for t in textures.values()])
        st.says("%d textures, %d mip levels total"
                % (len(textures), sum(t["mips"] for t in textures.values())))

    with Stage(ctx, "materials", verbose) as st:
        mres = p_material.run(ctx, scene, textures or {})
        material_ids = mres["ids"]
        st.produced(*["mat-" + m for m in material_ids])
        st.says("%d materials: %s" % (len(material_ids), ", ".join(material_ids)))
        sampler = p_material.make_sampler(scene, textures or {}, scene.mat_of_tri)

    if bounds is not None:
        with Stage(ctx, "imposters", verbose) as st:
            tiers = [("preview", args.imposter_preview, args.imposter_tile_px,
                      "octahedral-full"),
                     ("runtime", args.imposter_runtime, args.imposter_tile_px,
                      "octahedral-full")]
            imposter = p_imposter.run(ctx, mesh, bounds, scene.materials,
                                      sampler, tiers=tiers)
            st.produced("imposter", "tex-contact-sheet",
                        *["tex-imposter-%s-%s" % (t[0], r) for t in tiers
                          for r in ("albedo", "normal", "depth", "mrao")])
            st.says("preview IoU %.4f, runtime IoU %.4f"
                    % (imposter["quality"]["preview"]["silhouette_iou"],
                       imposter["quality"]["runtime"]["silhouette_iou"]))
        if imposter:
            ctx.primary["image"] = "tex-imposter-preview-albedo"

        with Stage(ctx, "lods", verbose) as st:
            fr = [0.5, 0.25, 0.12, 0.06][:max(1, args.lod_levels)]
            lods = p_lod.run(ctx, mesh, bounds, levels=fr,
                             views=args.imposter_preview ** 2, size=args.sse_px)
            st.produced(*[l["node"] for l in lods])
            st.says(", ".join("L%d %d tris / %.2f px" % (l["level"], l["tris"],
                                                         l["sse_px"]) for l in lods))

        with Stage(ctx, "colliders", verbose) as st:
            collider = p_collider.run(ctx, mesh, bounds, material_ids,
                                      grid=args.collider_grid,
                                      max_parts=args.collider_parts)
            st.produced("colliders", "collider-hulls")
            st.says("%d convex parts, hausdorff %.4f m, volume ratio %.3f"
                    % (collider["parts"], collider["hausdorff"],
                       collider["volume_ratio"]))

        with Stage(ctx, "body", verbose) as st:
            body = p_body.run(ctx, mesh, bounds, scene.materials, collider)
            st.produced("body")
            st.says("%.4f kg from %.6f m3 x %.0f kg/m3 (density INFERRED)"
                    % (body["mass"], body["volume"], body["density"]))

        if body is not None:
            with Stage(ctx, "rest-poses", verbose) as st:
                rp = p_restpose.run(ctx, mesh, bounds, body,
                                    trials=args.drop_trials)
                st.produced("restposes")
                st.says("%d poses from %d drops, top %.1f%%, %d hull faces"
                        % (rp["poses"], rp["trials"],
                           100 * rp["top"]["probability"], rp["hull_faces"]))

        with Stage(ctx, "flow-field", verbose) as st:
            fl = p_flow.run(ctx, mesh, bounds, grid=args.flow_grid)
            st.produced("flow")
            st.says("%dx%dx%d cells, %d inside, %.1f KiB"
                    % (*fl["dims"], fl["inside_cells"], fl["bytes"] / 1024.0))

    view_path = None
    if imposter and imposter["view_paths"]:
        view_path = imposter["view_paths"][0]

    vlm_answer = None
    if view_path and not args.no_vlm:
        with Stage(ctx, "properties", verbose) as st:
            pr = p_props.run(ctx, body, view_path, name)
            st.produced("props")
            vlm_answer = pr["answer"]
            st.says("vision model %s" % ("%s, %d fields" % (pr["model"], pr["fields"])
                                         if pr["vlm"] else
                                         "NOT reachable (%s); stub written" % pr["why"]))
    elif body is not None:
        with Stage(ctx, "properties", verbose) as st:
            pr = p_props.run(ctx, body, None, name)
            st.produced("props")
            st.says("no preview sheet or --no-vlm; stub written")

    if view_path:
        with Stage(ctx, "semantics", verbose) as st:
            semantics = p_semantics.run(ctx, bounds, view_path, stem,
                                        vlm_facets=vlm_answer,
                                        coverage=imposter.get("coverage"))
            st.produced("semantics", "embedding")
            st.says("scale-class '%s', %d palette colours, dominant %s"
                    % (semantics["scale_class"], semantics["colors"],
                       semantics["dominant"]))

    # -- the parts every package carries ---------------------------------
    with Stage(ctx, "spec+loaders", verbose) as st:
        package.embed_spec_and_loaders(ctx)
        st.produced("spec", "loader-python", "loader-rust", "loader-c")

    license_block = None
    with Stage(ctx, "license", verbose) as st:
        license_block = package.write_license(ctx, args.license_file, args.spdx)
        st.produced("license")
    if license_block is None:
        license_block = package.write_license(ctx, None, None)

    summary_lines = []
    if bounds:
        summary_lines.append("bounds     %.4f x %.4f x %.4f m, sphere r=%.4f m, "
                             "watertight=%s"
                             % (*(bounds["aabb_max"] - bounds["aabb_min"]),
                                bounds["radius"], bounds["watertight"]))
    if lods:
        summary_lines.append("lods       " + ", ".join(
            "L%d %d tris at %.2f px error" % (l["level"], l["tris"], l["sse_px"])
            for l in lods))
    if imposter:
        summary_lines.append("imposters  preview IoU %.4f, runtime IoU %.4f"
                             % (imposter["quality"]["preview"]["silhouette_iou"],
                                imposter["quality"]["runtime"]["silhouette_iou"]))
    if collider:
        summary_lines.append("colliders  %d convex parts, hausdorff %.4f m, "
                             "volume ratio %.3f"
                             % (collider["parts"], collider["hausdorff"],
                                collider["volume_ratio"]))
    if body:
        summary_lines.append("mass       %.4f kg = %.6f m3 measured x %.0f kg/m3 "
                             "INFERRED" % (body["mass"], body["volume"],
                                           body["density"]))
    if semantics:
        summary_lines.append("semantics  scale-class '%s', palette dominant %s"
                             % (semantics["scale_class"], semantics["dominant"]))
    for n in ctx.notes:
        summary_lines.append("NOTE       " + n)
    failed = [r.stage for r in ctx.reports if r.status == "failed"]
    if failed:
        summary_lines.append("MISSING    %s (see x/pipeline-report.json)"
                             % ", ".join(failed))

    with Stage(ctx, "readme", verbose) as st:
        package.write_readme(ctx, summary_lines)
        st.produced("readme")

    host = ({"host": "(omitted: --reproducible)", "os": "(omitted: --reproducible)"}
            if args.reproducible else
            {"host": platform.node(),
             "os": "%s %s" % (platform.system(), platform.release())})
    finished = now_iso()
    if args.reproducible:
        # The clock and the caller's paths are the last two things in the
        # package that differ between runs. Under --reproducible they are
        # replaced by ctx.created and by the option list with the paths
        # removed, and the report says that is what happened rather than
        # pretending the run had no start time.
        started = finished = ctx.created
        recorded_argv = [TOOL, "--reproducible",
                         "(input and output paths omitted so two runs agree)"]
    else:
        recorded_argv = [TOOL] + list(argv or sys.argv[1:])
    package.write_provenance(ctx, started, finished, host)
    report = package.write_report(ctx, recorded_argv, host)

    summary = ("%s, enriched unattended from %s by %s %s. %d producers ran, %d "
               "succeeded, %d failed and left their node absent. Every derived "
               "node carries input_files, an input_hash over exactly those "
               "files, and an epistemic stamp; density and any model-supplied "
               "property are stamped inferred and are never promoted."
               % (name, source_name, TOOL, TOOL_VERSION, len(ctx.reports),
                  report["summary"]["ok"], report["summary"]["failed"]))

    res = package.finish(ctx, args.output, license_block, summary)
    total = time.perf_counter() - t_start

    if verbose:
        print("wrote %s" % args.output)
        print("  %d bytes, sha256 %s" % (res["bytes"], res["sha256"]))
        print("  %d entries, %d nodes, %d declared files"
              % (res["entries"], res["nodes"], res["files"]))
        print("  manifest %d bytes, preview_prefix_bytes %d (%.2f%%)"
              % (res["manifest_bytes"], res["preview_prefix_bytes"],
                 100.0 * res["preview_prefix_bytes"] / res["bytes"]))
        print("  %d/%d producers ok, %d failed, total %.2fs"
              % (report["summary"]["ok"], len(ctx.reports),
                 report["summary"]["failed"], total))
    res["seconds"] = total
    res["report"] = report
    return 0


if __name__ == "__main__":
    sys.exit(main())
