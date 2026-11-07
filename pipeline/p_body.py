#!/usr/bin/env python3
"""p_body.py — core.phys.body: mass, centre of mass, inertia.

The GEOMETRY half is exact: volume, centroid and the six second moments come
from the signed-tetrahedron form of the divergence theorem over the triangles,
which is arithmetic on the mesh and nothing else. That half is `measured`.

The DENSITY half is a guess, and the node keeps the two apart instead of
multiplying them together and calling the product a fact. Each entry in
`densities[]` carries its own epistemic stamp, so a consumer reading a mass of
19 kg can see that the volume was measured to a millionth of a cubic metre and
the density was assumed from a material class. When a vision-language model is
reachable, `p_props` overrides the density and the stamp says `inferred` with
that model named; when it is not, the stamp still says `inferred` and the
source is the table below. Neither case ever says `measured`, because nobody
weighed it.
"""

import numpy as np

from .common import jbytes
from . import meshops as M

# Density priors, kg/m^3, with a plausible range. Deliberately coarse: this is
# a class-level prior and pretending to three significant figures would be the
# dishonest part, not the width of the range.
DENSITY = {
    "metal": (7200.0, [2700.0, 8960.0], "metal prior: the material's effective "
                                        "metallic is above 0.5, which is the "
                                        "only material fact a PBR pair carries"),
    "wood": (600.0, [350.0, 900.0], "wood prior"),
    "stone": (2600.0, [2200.0, 3000.0], "stone prior"),
    "ceramic": (2300.0, [1800.0, 2600.0], "ceramic prior"),
    "glass": (2500.0, [2400.0, 2600.0], "glass prior"),
    "plastic": (1100.0, [900.0, 1450.0], "plastic prior"),
    "rubber": (1200.0, [900.0, 1600.0], "rubber prior"),
    "fabric": (300.0, [100.0, 800.0], "fabric prior"),
    "organic": (900.0, [200.0, 1400.0], "organic prior"),
}
DEFAULT = (1000.0, [100.0, 8000.0],
           "material class 'unknown': the PBR numbers said only 'not metal', "
           "so this is a water-density placeholder with a range wide enough to "
           "be honest about knowing nothing")


def run(ctx, mesh, bounds, materials, collider=None, density_override=None):
    pos, idx = mesh["pos"], mesh["idx"]
    mp = bounds["mass_props"]
    volume = float(mp["volume"])
    watertight = bool(bounds["watertight"])
    method = "divergence-theorem-over-triangles"
    vol_stamp = "measured"

    if volume <= 0 or not watertight:
        if collider and collider.get("voxel_volume", 0) > 0:
            volume = float(collider["voxel_volume"])
            method = "voxel-occupancy-%dx%dx%d (mesh is not closed)" % collider["dims"]
            vol_stamp = "inferred"
        else:
            raise ValueError("mesh is not closed and no voxel volume is "
                             "available: a mass would be a fiction")

    cls = ctx.materials[0]["class"] if ctx.materials else None
    prior = DENSITY.get(cls, DEFAULT)
    density, rng, src = density_override or prior
    material_id = ctx.materials[0]["material_id"] if ctx.materials else "default"

    centroid = mp["centroid"]
    if vol_stamp == "inferred" and collider:
        pass  # centroid from the (open) mesh is still the best estimate there is
    mass, comps = M.inertia_about(mp["second_moments_origin"],
                                 mp["volume"] if watertight else volume,
                                 centroid, density)
    if not watertight:
        # the integrals were taken over an open surface; scale them by the
        # volume correction rather than pretending they were exact
        scale = volume / mp["volume"] if abs(mp["volume"]) > 1e-30 else 1.0
        comps = tuple(c * scale for c in comps)
        mass = density * volume
    comps = tuple(abs(c) if i < 3 else c for i, c in enumerate(comps))

    moments, quat = M.principal(comps)
    moments = [max(0.0, float(v)) for v in moments]

    doc = {
        "schema_version": 1,
        # S10-3, ruled 2026-08-08: core.phys.body is MODEL space, and it now
        # says so instead of leaving a reader to infer it from inertia.frame.
        "space": "model",
        "mass_kg": round(float(mass), 6),
        "center_of_mass_m": [round(float(v), 6) for v in centroid],
        "inertia": {
            "about": "center-of-mass",
            "frame": "model-axes",
            "component_order": ["ixx", "iyy", "izz", "ixy", "ixz", "iyz"],
            "components_kg_m2": [round(float(v), 9) for v in comps],
            "principal_axes": {"rotation": [round(float(v), 8) for v in quat],
                               "moments_kg_m2": [round(v, 9) for v in moments]},
        },
        "densities": [{
            "material_id": material_id,
            "density_kg_m3": float(density),
            "volume_m3": round(float(volume), 9),
            "hollow": False,
            "epistemic": "inferred",
            "confidence": 0.35,
        }],
        "method": method,
        "epistemic": "inferred",
        "confidence": 0.35,
        "note": "The geometry is measured and the density is not, and this node "
                "keeps them apart on purpose. Volume %s: %.9f m^3 by %s. "
                "Density %.0f kg/m^3 is a class-level prior (%s, plausible "
                "range %s), so mass_kg inherits that uncertainty in full - it "
                "is volume x a guess. The inertia components are the POSITIVE "
                "products of inertia and enter the tensor negated, per the "
                "schema's component_order."
                % (vol_stamp, volume, method, density, src, rng),
    }
    f = ctx.put("physics/body.json", jbytes(doc))
    ctx.node("body", "core.phys.body",
             ctx.version([f], "Mass properties: exact volume integrals over the "
                              "mesh, times an assumed density that is stamped as "
                              "assumed.",
                         "inferred", inputs=["geometry/game.glb"],
                         params={"density_kg_m3": float(density),
                                 "density_source": src},
                         confidence=0.35),
             edges=[{"to": "geom-game", "kind": "requires", "role": "integrates"}],
             part="whole")
    ctx.schemas["core.phys.body"] = "spec/schemas/core.phys.body.schema.json"
    return {"mass": mass, "com": centroid, "volume": volume,
            "density": density, "density_range": rng, "density_source": src,
            "material_id": material_id}
