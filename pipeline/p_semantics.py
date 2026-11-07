#!/usr/bin/env python3
"""p_semantics.py — core.semantics and core.embedding.

Three things, with three very different epistemic standings, kept apart:

  scale-class   MEASURED. The registry gives numeric bands for the longest
                axis, so the tag is arithmetic on a number this pipeline
                already measured. It is the only facet tag written without a
                model in the loop.

  the embedding MEASURED, and checkably so. `werk.descriptor.labhog/1` is
  and the      defined completely in spec/layouts/embedding.layout.txt section
  palette      4, so anyone holding the package can recompute both from the
                imposter atlas that is also in the package and check them to
                the declared 1e-6. That is what makes `measured` a claim a
                stranger can test rather than one the writer makes about
                itself. Stage 9 proved the recomputation; this reuses the same
                implementation, `fixtures/labhog.py`, unchanged.

  every other   INFERRED, or absent. Without a vision-language model there is
  facet         no evidence for `style`, `era`, `mood` or `condition`, and
                inventing plausible tags is the exact failure the manifesto
                calls out. What is emitted instead is the source asset's own
                name, as `x.`-prefixed free tags at low confidence, because a
                filename is weak evidence but it is evidence.
"""

import importlib.util
import os

import numpy as np

from .common import jbytes, hexcolor, kebab, write_envelope, ROOT

FACETS = os.path.join(ROOT, "spec", "facets.json")


def _labhog():
    spec = importlib.util.spec_from_file_location(
        "werk_labhog", os.path.join(ROOT, "fixtures", "labhog.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def scale_class(registry, longest_axis_m):
    meta = registry["facets"]["scale-class"]["tag_meta"]
    for tag in registry["facets"]["scale-class"]["tags"]:
        m = meta[tag]
        if m["longest_axis_min_m"] <= longest_axis_m < m["longest_axis_max_m"]:
            return tag, m
    return registry["facets"]["scale-class"]["tags"][-1], \
        meta[registry["facets"]["scale-class"]["tags"][-1]]


def run(ctx, bounds, view_path, source_name, vlm_facets=None, coverage=None):
    import json
    with open(FACETS, "r", encoding="utf-8") as fh:
        registry = json.load(fh)

    longest = float((bounds["aabb_max"] - bounds["aabb_min"]).max())
    sc, band = scale_class(registry, longest)

    # -- the descriptor, over the imposter preview sheet ------------------
    lab = _labhog()
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(ctx.files[view_path]))
    vec, pal, diag = lab.descriptor(img)

    colors = []
    for r, g, b, w in pal:
        if w <= 0.0:
            continue
        colors.append({"hex_srgb": hexcolor((r, g, b)),
                       "linear_rgb": [round(float(r), 6), round(float(g), 6),
                                      round(float(b), 6)],
                       "weight": round(float(w), 6)})
    total_w = sum(c["weight"] for c in colors)
    lum = sum(c["weight"] * (0.2126729 * c["linear_rgb"][0] +
                             0.7151522 * c["linear_rgb"][1] +
                             0.0721750 * c["linear_rgb"][2]) for c in colors)
    lum = lum / total_w if total_w > 0 else 0.0

    facets = {"scale-class": [sc]}
    stamps = {"scale-class/%s" % sc: {"epistemic": "measured", "confidence": 1.0}}
    free = []
    for tok in kebab(os.path.splitext(source_name)[0]).split("-"):
        if len(tok) >= 3 and not tok.isdigit():
            free.append("x." + tok)
    if vlm_facets:
        for facet, tags in vlm_facets.get("facets", {}).items():
            valid = set(registry["facets"].get(facet, {}).get("tags", []))
            keep = [t for t in tags if t in valid]
            if keep:
                facets.setdefault(facet, [])
                facets[facet] = keep if facet != "scale-class" else facets[facet]
                for t in keep:
                    stamps["%s/%s" % (facet, t)] = {
                        "epistemic": "inferred",
                        "confidence": float(vlm_facets.get("confidence", 0.5))}
    if free:
        facets.setdefault("function", [])
        # free tags are legal in any facet; 'function' is where a name most
        # often lands, and the x. prefix means no validator will mistake them
        # for registry vocabulary.
        facets["function"] = facets["function"] + free
        for t in free:
            stamps["function/%s" % t] = {"epistemic": "inferred", "confidence": 0.2}
    if not facets.get("function"):
        facets.pop("function", None)

    embedding = {
        "model": lab.MODEL_ID,
        "dim": int(lab.DIM),
        "dtype": "f32",
        "normalized": True,
        "vec": [float(np.float32(v)) for v in vec],
        "input": {"kind": "image-views", "views": [view_path]},
    }
    doc = {
        "schema_version": 1,
        "facets_version": int(registry["version"]),
        "facets": facets,
        "tag_stamps": stamps,
        "embedding": embedding,
        "palette": {
            "method": "labhog/1 top-8 CIELAB bins over %s; TRUNCATED top-N, so "
                      "the weights sum to %.4f and NOT to 1.0 - they are not "
                      "renormalised, because the same palette rides in the "
                      "core.embedding WKEM payload and two spellings of one "
                      "fact that disagree are worse than one (S-24). The sheet "
                      "is composited over 50%% grey (#808080, linear 0.2158) "
                      "and the entity covers %s of it, so a swatch at or near "
                      "that grey is THE BACKGROUND and a consumer filtering by "
                      "colour should drop it. Cropping it out was rejected: it "
                      "would make the vector unrecomputable from a file in the "
                      "package, which is the only reason this node may say "
                      "'measured'."
                      % (view_path, total_w,
                         ("%.1f%%" % (100.0 * coverage)) if coverage is not None
                         else "an unrecorded fraction"),
            "colors": colors,
            "dominant_index": 0,
            "average_luminance": round(float(lum), 6),
        },
        "description": "%s. Longest axis %.4f m, which the registry's scale "
                       "bands put in '%s' (%s). Everything above that is either "
                       "arithmetic over the package's own pixels or explicitly "
                       "stamped as a guess." % (ctx.name, longest, sc,
                                                band.get("gloss", "")),
        "keywords": [t[2:] for t in free],
        "note": "The only facet tag with evidence behind it is scale-class, "
                "which is a number in a band. %s"
                % ("A vision-language model supplied the rest and every one of "
                   "its tags is stamped inferred with its confidence."
                   if vlm_facets else
                   "No vision-language model was reachable, so no style, era, "
                   "mood or condition tag was written: an invented tag is worse "
                   "than an absent one."),
    }
    f = ctx.put("semantics/semantics.json", jbytes(doc))
    ctx.node("semantics", "core.semantics",
             ctx.version([f], "Facet tags, the labhog/1 style descriptor and the "
                              "palette, all computed from what is already in "
                              "this package.",
                         "measured", inputs=[view_path],
                         params={"descriptor": lab.MODEL_ID}),
             edges=[{"to": "imposter", "kind": "requires", "role": "embedded-from"}])
    ctx.schemas["core.semantics"] = "spec/schemas/core.semantics.schema.json"

    # -- the same numbers again, as the base-doctrine WKEM binary ---------
    header = {
        "model": lab.MODEL_ID,
        "dim": int(lab.DIM),
        "normalized": True,
        "metric": "cosine",
        "swatch_count": int(lab.SWATCHES),
        "source_path": view_path,
        "colour_space": "linear-srgb",
        "tolerance": float(lab.TOLERANCE),
        "producer": {"tool": "pipeline/p_semantics.py", "version": "0.1"},
        "epistemic": "measured",
        "note": "Bit-identical to core.semantics' JSON embedding and palette: "
                "one computation, two spellings, and they agree by construction.",
    }
    blob = write_envelope("WKEM", "core.embedding", header, [
        ("vector", "f32", [int(lab.DIM)], 4, lab.as_f32_bytes(vec)),
        ("palette", "f32", [int(lab.SWATCHES), 4], 16, lab.as_f32_bytes(pal)),
    ])
    ef = ctx.put("semantics/embedding.wkem", blob)
    ctx.node("embedding", "core.embedding",
             ctx.version([ef], "The style descriptor as the binary the layout "
                               "grammar defines, so a consumer that wants the "
                               "vector reads one declared section and parses no "
                               "JSON. Recomputable from %s to 1e-6." % view_path,
                         "measured", inputs=[view_path],
                         params={"descriptor": lab.MODEL_ID}),
             edges=[{"to": "semantics", "kind": "enhances", "role": "binary-form"}])
    ctx.layouts["core.embedding"] = "spec/layouts/embedding.layout.txt"
    return {"scale_class": sc, "colors": len(colors), "palette_weight": total_w,
            "dominant": colors[0]["hex_srgb"] if colors else None,
            "diag": diag, "free_tags": free, "vlm": bool(vlm_facets)}
