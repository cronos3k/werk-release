#!/usr/bin/env python3
"""p_material.py — core.material, one node per glTF material.

A straight transcription of the source's metallic-roughness parameters into
the werk schema, with the texture slots resolved to core.tex NODE IDS rather
than to indices into a table that only the source GLB has. That resolution is
the whole point: law 4 says identity is a stable id, and "texture 3" is not one.

Also builds the texel sampler the imposter baker shades with, so an imposter
carries the object's real base colour and not a flat vertex tint.
"""

import numpy as np

from .common import jbytes, kebab

SLOT = {"base_color_texture": "base_color",
        "metallic_roughness_texture": "metallic_roughness",
        "normal_texture": "normal",
        "occlusion_texture": "occlusion",
        "emissive_texture": "emissive"}


def effective_pbr(mat, textures):
    """metallic and roughness after the texture, not just the factor.

    glTF's default metallicFactor is 1.0, and almost every real asset leaves it
    there and puts the actual metalness in the metallic-roughness map. Reading
    the factor alone therefore calls every textured wooden crate a metal, which
    is exactly the kind of confident wrong answer this format exists to stop.
    """
    m = float(mat["metallic_factor"])
    r = float(mat["roughness_factor"])
    t = mat.get("metallic_roughness_texture")
    if t and t["image"] in textures:
        a = textures[t["image"]]["array"]
        if a.ndim == 3 and a.shape[2] >= 3:
            r = r * float(a[..., 1].mean()) / 255.0
            m = m * float(a[..., 2].mean()) / 255.0
    return m, r


def _class_of(metallic, roughness):
    """The manifest's coarse material class, from the PBR numbers alone.

    The enum offers wood, stone, ceramic, fabric and nine more, and a
    metallic-roughness pair cannot distinguish any of them: it can separate
    metal from not-metal and that is the whole of its evidence. So metal is the
    only positive answer this returns, and everything else is 'unknown' rather
    than a plausible guess. A vision-language model, when one is reachable, is
    what can say 'wood'; two floats cannot.
    """
    return "metal" if metallic > 0.5 else "unknown"


def run(ctx, scene, textures):
    docs = []
    for mat in scene.materials:
        mid = kebab(mat["name"]) or ("material-%d" % mat["index"])
        slots = {}
        for key, slot in SLOT.items():
            t = mat.get(key)
            if not t or t["image"] not in textures:
                continue
            tx = textures[t["image"]]
            entry = {"node": tx["node"], "path": tx["path"],
                     "uv_set": int(t.get("uv_set", 0))}
            if slot == "metallic_roughness":
                entry["channel"] = "rgb"
            slots[slot] = entry
        doc = {
            "material_id": mid,
            "name": mat["name"],
            "model": "metallic-roughness",
            "base_color_factor": [float(v) for v in mat["base_color_factor"]],
            "metallic_factor": float(mat["metallic_factor"]),
            "roughness_factor": float(mat["roughness_factor"]),
            "emissive_factor": [float(v) for v in mat["emissive_factor"]],
            "alpha_mode": mat["alpha_mode"].lower(),
            "double_sided": bool(mat["double_sided"]),
            "epistemic": "authored",
            "note": "Transcribed from the source GLB's material %d. Texture "
                    "slots name core.tex NODES; the mirrored path is a "
                    "convenience and the node id is the authority."
                    % mat["index"],
        }
        if slots:
            doc["textures"] = slots
        docs.append((mid, mat["index"], doc))

    if not docs:
        # A GLB with no material block is legal glTF and means "the default
        # material". Writing that default explicitly beats leaving a consumer
        # to know what glTF's default is.
        docs = [("default", -1, {
            "material_id": "default", "name": "glTF default material",
            "model": "metallic-roughness",
            "base_color_factor": [1.0, 1.0, 1.0, 1.0],
            "metallic_factor": 1.0, "roughness_factor": 1.0,
            "alpha_mode": "opaque", "double_sided": False,
            "epistemic": "authored",
            "note": "The source GLB declared no materials. This is glTF 2.0's "
                    "default material written out explicitly."})]

    by_index = {m["index"]: m for m in scene.materials}
    seen = {}
    for mid, srcidx, doc in docs:
        if mid in seen:
            mid = "%s-%d" % (mid, srcidx)
            doc["material_id"] = mid
        seen[mid] = srcidx
        src = by_index.get(srcidx)
        if src is not None:
            em, er = effective_pbr(src, textures)
            cls = _class_of(em, er)
        else:
            # No material block at all. glTF's default declares metallicFactor
            # 1.0, but that is the SPEC's default, not the author saying "this
            # is metal" - and reading it as evidence turns every untextured
            # test mesh into a solid lump of steel. The class is unknown.
            em, er = doc["metallic_factor"], doc["roughness_factor"]
            cls = "unknown"
        doc["note"] += (" Effective metallic %.3f and roughness %.3f after the "
                        "metallic-roughness map (the factors alone are %.3f / "
                        "%.3f), which is what the manifest's coarse class was "
                        "decided on." % (em, er, doc["metallic_factor"],
                                         doc["roughness_factor"]))
        f = ctx.put("materials/%s.json" % mid, jbytes(doc))
        ctx.node("mat-" + mid, "core.material",
                 ctx.version([f], "Material '%s' as the source authored it."
                             % doc["name"], "authored"),
                 material=mid, part="whole")
        ctx.materials.append({"material_id": mid, "part_id": "whole",
                              "name": doc["name"],
                              "class": cls})
    ctx.schemas["core.material"] = "spec/schemas/core.material.schema.json"
    return {"materials": [d[2] for d in docs],
            "ids": [d[0] for d in docs]}


def make_sampler(scene, textures, mat_of_tri):
    """Texel sampler for the imposter bake. Nearest-neighbour, wrap-repeat.

    Nearest rather than bilinear because the bake writes one sample per texel
    and a filtered read would blur across UV islands, which is a worse error
    than aliasing at 256 px.
    """
    per_mat = {}
    for mat in scene.materials:
        t = mat.get("base_color_texture")
        arr = None
        if t and t["image"] in textures:
            a = textures[t["image"]]["array"].astype(np.float64) / 255.0
            if a.ndim == 2:
                a = np.stack([a] * 3, axis=-1)
            lin = np.where(a[..., :3] <= 0.04045, a[..., :3] / 12.92,
                           ((a[..., :3] + 0.055) / 1.055) ** 2.4)
            alpha = a[..., 3] if a.shape[2] > 3 else np.ones(a.shape[:2])
            arr = (lin, alpha)
        mr = mat.get("metallic_roughness_texture")
        mrarr = None
        if mr and mr["image"] in textures:
            b = textures[mr["image"]]["array"].astype(np.float64) / 255.0
            if b.ndim == 2:
                b = np.stack([b] * 3, axis=-1)
            mrarr = b
        per_mat[mat["index"]] = {
            "tex": arr, "mr": mrarr,
            "bcf": np.array(mat["base_color_factor"], dtype=np.float64),
            "m": float(mat["metallic_factor"]),
            "r": float(mat["roughness_factor"])}
    if not per_mat:
        return None

    def sampler(uv, tri):
        n = len(uv)
        albedo = np.ones((n, 3))
        alpha = np.ones(n)
        met = np.zeros(n)
        rgh = np.full(n, 0.5)
        mats = mat_of_tri[tri]
        for mi in np.unique(mats):
            e = per_mat.get(int(mi))
            if e is None:
                continue
            sel = mats == mi
            albedo[sel] = e["bcf"][:3]
            alpha[sel] = e["bcf"][3]
            met[sel] = e["m"]
            rgh[sel] = e["r"]
            if e["tex"] is not None:
                lin, a = e["tex"]
                h, w = lin.shape[:2]
                u = np.mod(uv[sel, 0], 1.0)
                v = np.mod(uv[sel, 1], 1.0)
                x = np.clip((u * w).astype(np.int64), 0, w - 1)
                y = np.clip((v * h).astype(np.int64), 0, h - 1)
                albedo[sel] = albedo[sel] * lin[y, x]
                alpha[sel] = alpha[sel] * a[y, x]
            if e["mr"] is not None:
                b = e["mr"]
                h, w = b.shape[:2]
                u = np.mod(uv[sel, 0], 1.0)
                v = np.mod(uv[sel, 1], 1.0)
                x = np.clip((u * w).astype(np.int64), 0, w - 1)
                y = np.clip((v * h).astype(np.int64), 0, h - 1)
                rgh[sel] = rgh[sel] * b[y, x, 1]
                met[sel] = met[sel] * b[y, x, 2]
        return {"albedo": albedo, "alpha": alpha, "metallic": met,
                "roughness": rgh}
    return sampler
