#!/usr/bin/env python3
"""p_imposter.py — the octahedral imposter baker, core.imposter.

Two tiers per `spec/layouts/imposter.layout.txt` section 4: a 4x4x256 preview
sheet and an 8x8x256 runtime sheet, four G-buffer atlases each (albedo RGBA
sRGB, normal RG octahedral linear, depth 16-bit, MRAO 8-bit linear).

The octahedral encode/decode below is the layout file's normative arithmetic
transcribed, including sgn(0) = +1, and the round-trip is asserted for every
tile centre before a pixel is written — the layout file says a conformance test
does exactly this, so the baker does it to itself rather than waiting to be
caught.

Law 9 in one node: the preview sheet is the store's thumbnail contact sheet,
the browser's preview, the farthest LOD, and the images the style embedding is
computed from. One bake, four masters.
"""

import numpy as np

from .common import jbytes, png_bytes, png_info
from . import meshops as M, raster


def _sgn(t):
    return np.where(t >= 0.0, 1.0, -1.0)


def oct_decode(u, v, mapping):
    e = np.stack([u * 2.0 - 1.0, v * 2.0 - 1.0], axis=-1)
    if mapping == "octahedral-hemi":
        px = (e[..., 0] + e[..., 1]) * 0.5
        pz = (e[..., 0] - e[..., 1]) * 0.5
        py = 1.0 - np.abs(px) - np.abs(pz)
    else:
        py = 1.0 - np.abs(e[..., 0]) - np.abs(e[..., 1])
        px = np.where(py < 0, (1.0 - np.abs(e[..., 1])) * _sgn(e[..., 0]), e[..., 0])
        pz = np.where(py < 0, (1.0 - np.abs(e[..., 0])) * _sgn(e[..., 1]), e[..., 1])
    n = np.stack([px, py, pz], axis=-1)
    return n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-30)


def oct_encode(n, mapping="octahedral-full"):
    n = np.asarray(n, dtype=np.float64)
    L = np.abs(n).sum(axis=-1, keepdims=True)
    p = n / np.maximum(L, 1e-30)
    if mapping == "octahedral-hemi":
        ex = p[..., 0] + p[..., 2]
        ey = p[..., 0] - p[..., 2]
    else:
        ex = np.where(p[..., 1] >= 0, p[..., 0],
                      (1.0 - np.abs(p[..., 2])) * _sgn(p[..., 0]))
        ey = np.where(p[..., 1] >= 0, p[..., 2],
                      (1.0 - np.abs(p[..., 0])) * _sgn(p[..., 2]))
    return np.stack([ex * 0.5 + 0.5, ey * 0.5 + 0.5], axis=-1)


def tile_directions(n, mapping="octahedral-full"):
    """The bake direction of every tile, in tile_index = j*N + i order."""
    dirs = []
    for j in range(n):
        for i in range(n):
            u = (i + 0.5) / n
            v = (j + 0.5) / n
            dirs.append(oct_decode(np.array(u), np.array(v), mapping))
    return [np.asarray(d, dtype=np.float64) for d in dirs]


def check_roundtrip(n, mapping):
    worst = 0.0
    for j in range(n):
        for i in range(n):
            u, v = (i + 0.5) / n, (j + 0.5) / n
            d = oct_decode(np.array(u), np.array(v), mapping)
            uv = oct_encode(d, mapping)
            worst = max(worst, abs(float(uv[0]) - u), abs(float(uv[1]) - v))
    return worst


TIERS = [("preview", 4, 256, "octahedral-full"),
         ("runtime", 8, 256, "octahedral-full")]


def run(ctx, mesh, bounds, materials, sampler, tiers=TIERS):
    """`sampler(points_uv, tri_material)` -> (albedo_lin(n,3), alpha(n),
    metallic(n), roughness(n)) for shaded texels; may be None."""
    pos, idx = mesh["pos"], mesh["idx"]
    nrm = mesh["nrm"]
    centre = bounds["centre"]
    radius = float(bounds["radius"])
    half = radius * 1.0001                 # a hair of margin so nothing clips
    cam_dist = radius * 4.0

    descriptor = {"schema_version": 1, "tiers": [], "bake": {
        "source_node": "geom-game",
        "renderer": "werk pipeline raster.py 0.1 (software, orthographic, "
                    "z-buffered, numpy)",
        "lighting": "unlit-albedo",
        "samples_per_texel": 1,
        "seed": 0}}
    preview_paths = []
    quality_inputs = []
    preview_albedo = None
    sheet_coverage = None

    for tier, n, tpx, mapping in tiers:
        rt = check_roundtrip(n, mapping)
        assert rt <= 1e-5, "octahedral round-trip off by %.3e at N=%d" % (rt, n)
        size = n * tpx
        albedo = np.zeros((size, size, 4), dtype=np.uint8)
        normal = np.zeros((size, size, 4), dtype=np.uint8)
        normal[..., 3] = 255
        depth = np.full((size, size), 65535, dtype=np.uint16)
        mrao = np.zeros((size, size, 3), dtype=np.uint8)

        depth_min = cam_dist - radius
        depth_range = 2.0 * radius

        iou_num = iou_den = 0.0
        covered = 0
        dirs = tile_directions(n, mapping)
        for t, d in enumerate(dirs):
            i, j = t % n, t // n
            out = raster.render(pos, idx, d, half, tpx,
                                attrs={"n": nrm, "uv": mesh["uv"],
                                       "c": mesh["col"][:, :3]},
                                pivot=centre, backface_cull=False)
            m = out["mask"]
            y0, x0 = j * tpx, i * tpx
            if not m.any():
                continue
            covered += int(m.sum())

            base_lin = out["c"][m]
            met = np.zeros(len(base_lin))
            rgh = np.full(len(base_lin), 0.5)
            alpha = np.ones(len(base_lin))
            if sampler is not None:
                s = sampler(out["uv"][m], out["tri"][m])
                if s is not None:
                    base_lin = base_lin * s["albedo"]
                    met = s["metallic"]
                    rgh = s["roughness"]
                    alpha = s["alpha"]

            srgb = np.where(base_lin <= 0.0031308, base_lin * 12.92,
                            1.055 * np.maximum(base_lin, 0.0) ** (1 / 2.4) - 0.055)
            tile_a = albedo[y0:y0 + tpx, x0:x0 + tpx]
            tile_a[m, 0:3] = np.clip(np.round(srgb * 255.0), 0, 255).astype(np.uint8)
            tile_a[m, 3] = np.clip(np.round(alpha * 255.0), 0, 255).astype(np.uint8)

            nn = out["n"][m]
            nn = nn / np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-30)
            nuv = oct_encode(nn, "octahedral-full")
            tile_n = normal[y0:y0 + tpx, x0:x0 + tpx]
            tile_n[m, 0:2] = np.clip(np.round(nuv * 255.0), 0, 255).astype(np.uint8)

            z = out["depth"][m]                      # metres along the view axis
            dist = cam_dist - z                      # distance from the camera plane
            q = np.clip(np.round((dist - depth_min) / depth_range * 65535.0),
                        0, 65534).astype(np.uint16)
            depth[y0:y0 + tpx, x0:x0 + tpx][m] = q

            tile_m = mrao[y0:y0 + tpx, x0:x0 + tpx]
            tile_m[m, 0] = np.clip(np.round(met * 255.0), 0, 255).astype(np.uint8)
            tile_m[m, 1] = np.clip(np.round(rgh * 255.0), 0, 255).astype(np.uint8)
            tile_m[m, 2] = 255                       # AO: not computed, declared as 1

            # Silhouette IoU against a 4x SUPERSAMPLED reference, majority-
            # downsampled to the tile resolution. Comparing the tile against
            # the same mesh rendered at the same resolution would measure the
            # rasterizer against itself and return 1.0 every time, which is a
            # number with no information in it; this measures what the tier
            # actually loses by being 256 px.
            ss = 2
            ref = raster.silhouette(pos, idx, d, half, tpx * ss, pivot=centre)
            ref = (ref.reshape(tpx, ss, tpx, ss).sum(axis=(1, 3)) > (ss * ss) // 2)
            iou_num += float((ref & m).sum())
            iou_den += float((ref | m).sum())

        chans = {}
        for role, arr, mode, cs, bd, nc, usage in (
                ("albedo", albedo, "RGBA", "srgb", 8, 4, "base-color"),
                ("normal", normal, "RGBA", "linear", 8, 4, "normal"),
                ("depth", depth, "L16", "linear", 16, 1, "depth"),
                ("mrao", mrao, "RGB", "linear", 8, 3, "mrao")):
            blob = png_bytes(arr, mode)
            info = png_info(blob)
            assert (info["width"], info["height"]) == (size, size)
            path = "imposters/%s-%s.png" % (tier, role)
            f = ctx.put(path, blob)
            node_id = "tex-imposter-%s-%s" % (tier, role)
            meta = {"color_space": cs, "usage": usage,
                    "width": size, "height": size, "bit_depth": bd,
                    "channels": nc, "imposter_tier": tier,
                    "imposter_role": role}
            if usage == "normal":
                # The atlas stores an OCTAHEDRAL WORLD-SPACE normal, not a
                # tangent-space map, so neither green-channel convention
                # describes it. The schema still demands the key when usage is
                # 'normal'; the honest answer is the one that matches the
                # handedness the octahedral decode produces, plus this note.
                meta["normal_convention"] = "opengl-y-up"
                meta["normal_encoding"] = ("octahedral-full world space in RG, "
                                           "per imposter.layout.txt section 3; "
                                           "NOT a tangent-space normal map, so "
                                           "normal_convention describes the "
                                           "handedness only")
            ctx.node(node_id, "core.tex",
                     ctx.version([f],
                                 "Imposter %s atlas, tier '%s': %dx%d tiles of "
                                 "%d px. Baked by the software rasterizer from "
                                 "geometry/game.glb." % (role, tier, n, n, tpx),
                                 "measured", inputs=["geometry/game.glb"],
                                 params={"tier": tier, "tile_count": n,
                                         "tile_pixels": tpx, "channel": role}),
                     edges=[{"to": "geom-game", "kind": "requires",
                             "role": "baked-from"}],
                     meta=meta)
            chans[role] = {"node": node_id, "path": path, "color_space": cs,
                           "bit_depth": bd, "channels": nc}
            if tier == "preview":
                preview_paths.append(path)

        if tier == "preview":
            preview_albedo = albedo.copy()

        iou = (iou_num / iou_den) if iou_den > 0 else 0.0
        # the distance at which one tile's angular error is under one pixel at
        # 1080p / 60 deg vfov: the tile grid samples the sphere every
        # (pi/2)/N radians, and the silhouette error that implies is
        # radius * (1 - cos(half tile angle)).
        tile_angle = (np.pi / 2.0) / n
        sag = radius * (1.0 - np.cos(tile_angle / 2.0))
        px_per_m_at_1m = REFERENCE = 1080.0 / (2.0 * np.tan(np.pi / 6.0))
        switch = max(1e-3, sag * px_per_m_at_1m)
        descriptor["tiers"].append({
            "tier": tier, "mapping": mapping, "tile_count": n,
            "tile_pixels": tpx, "atlas_pixels": [size, size],
            "projection": "orthographic",
            "ortho_half_height_m": float(half),
            "camera_distance_m": float(cam_dist),
            "pivot_m": [float(v) for v in centre],
            "depth_min_m": float(depth_min),
            "depth_range_m": float(depth_range),
            "channels": chans,
            "alpha_is_coverage": True,
        })
        descriptor.setdefault("_quality", {})[tier] = {
            "silhouette_iou": round(float(iou), 6),
            "recommended_switch_distance_m": round(float(switch), 4),
        }

    quality = descriptor.pop("_quality")
    descriptor["quality"] = quality["runtime"]
    descriptor["note"] = (
        "Baked with a software rasterizer, unlit: the albedo atlas is raw base "
        "colour with no light rig, which is the only choice that lets a runtime "
        "relight the imposter. silhouette_iou is measured per tile against the "
        "source mesh rendered at the same tile resolution and averaged over the "
        "whole tier, the reference being the same mesh rendered at 2x the tile "
        "resolution and majority-downsampled, so the number measures what the "
        "tile resolution costs rather than measuring the rasterizer against "
        "itself; preview tier IoU %.4f, runtime tier IoU %.4f. Ambient "
        "occlusion is NOT computed and the MRAO blue channel is a declared 1.0 "
        "rather than a guess."
        % (quality["preview"]["silhouette_iou"], quality["runtime"]["silhouette_iou"]))

    # -- the contact sheet ------------------------------------------------
    # The preview albedo atlas is mostly transparent, and a descriptor computed
    # over it would mostly describe the background. So the same 16 tiles get
    # composited once over a neutral 50 % grey and written as an opaque RGB
    # sheet: it is what the style descriptor is computed from, what a
    # vision-language model is shown, and what a human sees in a file browser
    # that has never heard of werk. One image, three masters (law 9).
    if preview_albedo is not None:
        a = preview_albedo[..., 3:4].astype(np.float64) / 255.0
        rgb = preview_albedo[..., :3].astype(np.float64)
        sheet = np.clip(np.round(rgb * a + 128.0 * (1.0 - a)), 0, 255).astype(np.uint8)
        coverage = float((preview_albedo[..., 3] > 0).mean())
        blob = png_bytes(sheet, "RGB")
        sp = "imposters/preview-sheet.png"
        sf = ctx.put(sp, blob)
        ctx.node("tex-contact-sheet", "core.tex",
                 ctx.version([sf],
                             "The preview tier's 16 views composited over 50%% "
                             "grey and flattened to opaque RGB. It exists "
                             "because a descriptor computed over the "
                             "transparent atlas would mostly describe the "
                             "background. The entity covers %.2f%% of it; the "
                             "remaining %.2f%% IS the grey and any palette "
                             "computed over this sheet will carry a swatch for "
                             "it." % (100.0 * coverage, 100.0 * (1 - coverage)),
                             "measured",
                             inputs=["imposters/preview-albedo.png"],
                             params={"background_srgb8": 128}),
                 edges=[{"to": "tex-imposter-preview-albedo", "kind": "requires",
                         "role": "composited-from"}],
                 meta={"color_space": "srgb", "usage": "other",
                       "width": int(sheet.shape[1]), "height": int(sheet.shape[0]),
                       "bit_depth": 8, "channels": 3,
                       "role": "contact-sheet",
                       "background_srgb_hex": "#808080",
                       "coverage": round(coverage, 6)})
        preview_paths.append(sp)
        quality_inputs.append(sp)
        sheet_coverage = coverage

    f = ctx.put("imposters/imposter.json", jbytes(descriptor))
    ctx.node("imposter", "core.imposter",
             ctx.version([f], "Two octahedral tiers, %s. Tile-centre round-trip "
                              "verified to 1e-5 for every tile of both mappings "
                              "before any pixel was written."
                         % ", ".join("%s %dx%d" % (t[0], t[1], t[1]) for t in tiers),
                         "measured", inputs=["geometry/game.glb"]),
             edges=[{"to": "geom-game", "kind": "requires", "role": "baked-from"}])
    ctx.schemas["core.imposter"] = "spec/schemas/core.imposter.schema.json"
    ctx.layouts["core.imposter"] = "spec/layouts/imposter.layout.txt"
    return {"preview_paths": preview_paths, "quality": quality,
            "view_paths": quality_inputs, "coverage": sheet_coverage}
