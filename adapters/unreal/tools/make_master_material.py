"""make_master_material.py — build WerkLink's shipped master material.

Run INSIDE the Unreal editor's Python (the testbed does it for you):

    UnrealEditor-Cmd.exe <Project>.uproject -run=pythonscript \
        -script="<repo>/adapters/unreal/tools/make_master_material.py"

or from the editor's Output Log:  py "<repo>/adapters/unreal/tools/make_master_material.py"

Why a script and not a checked-in .uasset alone
-----------------------------------------------
A .uasset is opaque binary. One is checked in (WerkLink/Content/M_WerkPBR.uasset)
because a plugin has to WORK when it is copied into a project, but an opaque
binary nobody can regenerate is exactly the kind of artifact this format exists
to argue against. This script is the thing the .uasset is a build product of:
the graph is stated in source, in one place, and the parameter names come from
the SAME table the C++ importer and exporter read (WerkMaterialSlots.h) rather
than from a second list that can drift.

What it deliberately does NOT do
--------------------------------
* No `height` slot. `core.material.schema.json` allows one, and a base pass
  cannot shade it without parallax occlusion mapping. Declaring the parameter
  and wiring it to nothing would make the exporter write a slot that claims a
  shading the engine never performs. With no parameter, the importer reports
  the slot as unbound, which is true.
* `uv_set` is not honoured: every sampler reads UV0. Reported per binding by
  the importer when a payload declares anything else.
* `normal_scale` is applied as lerp(flat, sampled, scale), which is an
  approximation of glTF's normalScale and is written into the material's own
  description so nobody has to read this file to find out.
"""

import unreal

PACKAGE_PATH = "/WerkLink"
ASSET_NAME = "M_WerkPBR"

MEL = unreal.MaterialEditingLibrary

# The parameter names. Kept in the same order and spelling as
# adapters/unreal/WerkLink/Source/WerkLink/Private/WerkMaterialSlots.h.
SLOTS = [
    ("base_color", "BaseColorTexture", "UseBaseColorTexture"),
    ("metallic_roughness", "MetallicRoughnessTexture", "UseMetallicRoughnessTexture"),
    ("normal", "NormalTexture", "UseNormalTexture"),
    ("occlusion", "OcclusionTexture", "UseOcclusionTexture"),
    ("emissive", "EmissiveTexture", "UseEmissiveTexture"),
]

DESCRIPTION = (
    "WerkLink master material. Parameter names are normative for this adapter: "
    "core.material texture slots bind to <Slot>Texture and are enabled by the "
    "static switch Use<Slot>Texture. metallic_roughness follows glTF packing "
    "(occlusion=R, roughness=G, metallic=B) and multiplies the factors. "
    "normal_scale is applied as lerp(flat, sampled, NormalScale), an "
    "approximation of glTF normalScale. Every sampler reads UV0. There is no "
    "height slot: a base pass cannot shade one, and a parameter wired to "
    "nothing would make the exporter claim a shading that never happens."
)


def _tex(path):
    # unreal.load_asset, not EditorAssetLibrary.load_asset: in a commandlet the
    # asset registry has not scanned /Engine, so the registry-backed call fails
    # on textures that are demonstrably on disk. This one does a real
    # LoadObject. Measured, not guessed: DefaultNormal.uasset exists and the
    # registry call reported it "could not be found".
    t = unreal.load_asset(path)
    if t is None:
        raise RuntimeError("engine texture missing: %s" % path)
    return t


def build():
    full = "%s/%s" % (PACKAGE_PATH, ASSET_NAME)
    # The registry has not scanned the plugin's own content in a commandlet, so
    # does_asset_exist lies by omission and create_asset then refuses with
    # "already exists". Tell the registry to look first -- the same
    # ScanPathsSynchronous fact the importer's findings B6 records.
    unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous(
        [PACKAGE_PATH], force_rescan=True)
    if unreal.EditorAssetLibrary.does_asset_exist(full):
        unreal.EditorAssetLibrary.delete_asset(full)

    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mat = tools.create_asset(ASSET_NAME, PACKAGE_PATH, unreal.Material,
                             unreal.MaterialFactoryNew())
    if mat is None:
        raise RuntimeError("could not create %s/%s" % (PACKAGE_PATH, ASSET_NAME))

    white = _tex("/Engine/EngineResources/WhiteSquareTexture")
    flat_normal = _tex("/Engine/EngineMaterials/DefaultNormal")

    def expr(cls, x, y):
        return MEL.create_material_expression(mat, cls, x, y)

    def scalar(name, value, x, y):
        e = expr(unreal.MaterialExpressionScalarParameter, x, y)
        e.set_editor_property("parameter_name", name)
        e.set_editor_property("default_value", value)
        return e

    def vector(name, value, x, y):
        e = expr(unreal.MaterialExpressionVectorParameter, x, y)
        e.set_editor_property("parameter_name", name)
        e.set_editor_property("default_value", value)
        return e

    def texparam(name, default, sampler_type, x, y):
        e = expr(unreal.MaterialExpressionTextureSampleParameter2D, x, y)
        e.set_editor_property("parameter_name", name)
        e.set_editor_property("texture", default)
        e.set_editor_property("sampler_type", sampler_type)
        return e

    def switch(name, x, y):
        e = expr(unreal.MaterialExpressionStaticSwitchParameter, x, y)
        e.set_editor_property("parameter_name", name)
        e.set_editor_property("default_value", False)
        return e

    def const3(v, x, y):
        e = expr(unreal.MaterialExpressionConstant3Vector, x, y)
        e.set_editor_property("constant", v)
        return e

    def const(v, x, y):
        e = expr(unreal.MaterialExpressionConstant, x, y)
        e.set_editor_property("r", v)
        return e

    # EVERY connection is checked. UMaterialEditingLibrary::
    # ConnectMaterialExpressions returns false when it cannot find the named
    # output or input and logs nothing a script sees, so an unchecked call
    # produces a material that compiles, renders BLACK, and looks correct in
    # every listing. That is exactly what the first version of this file did:
    # `UseBaseColorTexture` on gave a black crate and every parameter query
    # said the bind was fine. The only way it surfaced was a screenshot.
    failures = []

    def link(a, ao, b, bi):
        if not MEL.connect_material_expressions(a, ao, b, bi):
            failures.append("%s['%s'] -> %s['%s']"
                            % (type(a).__name__, ao, type(b).__name__, bi))

    def link_prop(a, ao, prop):
        if not MEL.connect_material_property(a, ao, prop):
            failures.append("%s['%s'] -> %s" % (type(a).__name__, ao, prop))

    def mul(a, ao, b, bo, x, y):
        e = expr(unreal.MaterialExpressionMultiply, x, y)
        link(a, ao, e, "A")
        link(b, bo, e, "B")
        return e

    def lerp(a, ao, b, bo, alpha, alpha_o, x, y):
        e = expr(unreal.MaterialExpressionLinearInterpolate, x, y)
        link(a, ao, e, "A")
        link(b, bo, e, "B")
        link(alpha, alpha_o, e, "Alpha")
        return e

    def sw(name, true_e, true_o, false_e, false_o, x, y):
        e = switch(name, x, y)
        link(true_e, true_o, e, "True")
        link(false_e, false_o, e, "False")
        return e

    # --- base colour -------------------------------------------------------
    p_basecolor = vector("BaseColor", unreal.LinearColor(1, 1, 1, 1), -1200, -600)
    t_basecolor = texparam("BaseColorTexture", white,
                           unreal.MaterialSamplerType.SAMPLERTYPE_COLOR, -1600, -400)
    bc_mul = mul(t_basecolor, "RGB", p_basecolor, "", -900, -500)
    bc = sw("UseBaseColorTexture", bc_mul, "", p_basecolor, "", -600, -550)
    link_prop(bc, "", unreal.MaterialProperty.MP_BASE_COLOR)

    # --- metallic / roughness, glTF packed --------------------------------
    p_metallic = scalar("Metallic", 0.0, -1200, -180)
    p_rough = scalar("Roughness", 0.5, -1200, -100)
    t_mr = texparam("MetallicRoughnessTexture", white,
                    unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR, -1600, 0)
    rough_mul = mul(t_mr, "G", p_rough, "", -900, -60)
    metal_mul = mul(t_mr, "B", p_metallic, "", -900, 40)
    rough = sw("UseMetallicRoughnessTexture", rough_mul, "", p_rough, "", -600, -80)
    metal = sw("UseMetallicRoughnessTexture", metal_mul, "", p_metallic, "", -600, 60)
    link_prop(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    link_prop(metal, "", unreal.MaterialProperty.MP_METALLIC)

    # --- normal ------------------------------------------------------------
    p_nscale = scalar("NormalScale", 1.0, -1200, 260)
    t_normal = texparam("NormalTexture", flat_normal,
                        unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL, -1600, 380)
    flat = const3(unreal.LinearColor(0.0, 0.0, 1.0, 1.0), -1200, 380)
    n_lerp = lerp(flat, "", t_normal, "RGB", p_nscale, "", -900, 340)
    nrm = sw("UseNormalTexture", n_lerp, "", flat, "", -600, 300)
    link_prop(nrm, "", unreal.MaterialProperty.MP_NORMAL)

    # --- occlusion ---------------------------------------------------------
    p_ao = scalar("OcclusionStrength", 1.0, -1200, 620)
    t_ao = texparam("OcclusionTexture", white,
                    unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR, -1600, 720)
    one = const(1.0, -1200, 700)
    ao_lerp = lerp(one, "", t_ao, "R", p_ao, "", -900, 680)
    ao = sw("UseOcclusionTexture", ao_lerp, "", one, "", -600, 640)
    link_prop(ao, "", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)

    # --- emissive ----------------------------------------------------------
    p_emissive = vector("EmissiveColor", unreal.LinearColor(0, 0, 0, 1), -1200, 960)
    p_estrength = scalar("EmissiveStrength", 1.0, -1200, 1040)
    t_emissive = texparam("EmissiveTexture", white,
                          unreal.MaterialSamplerType.SAMPLERTYPE_COLOR, -1600, 1100)
    em_mul = mul(t_emissive, "RGB", p_emissive, "", -900, 1020)
    em_sw = sw("UseEmissiveTexture", em_mul, "", p_emissive, "", -700, 980)
    em = mul(em_sw, "", p_estrength, "", -450, 1000)
    link_prop(em, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    mat.set_editor_property("two_sided", False)
    MEL.recompile_material(mat)
    unreal.EditorAssetLibrary.save_asset("%s/%s" % (PACKAGE_PATH, ASSET_NAME))

    # Report what the material actually exposes, measured off the asset rather
    # than off this script's intentions.
    report = {
        "asset": "%s/%s" % (PACKAGE_PATH, ASSET_NAME),
        "scalar": sorted(str(p) for p in MEL.get_scalar_parameter_names(mat)),
        "vector": sorted(str(p) for p in MEL.get_vector_parameter_names(mat)),
        "texture": sorted(str(p) for p in MEL.get_texture_parameter_names(mat)),
        "switch": sorted(str(p) for p in MEL.get_static_switch_parameter_names(mat)),
    }
    missing = []
    for _slot, tex_param, switch_param in SLOTS:
        if tex_param not in report["texture"]:
            missing.append(tex_param)
        if switch_param not in report["switch"]:
            missing.append(switch_param)
    report["missing"] = missing
    report["unconnected"] = failures
    report["ok"] = not missing and not failures

    # A file, not a print: a commandlet's stdout is not reliably captured and a
    # gate that reads log lines is a gate that can be fooled by a log format
    # change. The caller reads this.
    import json
    import os
    out = os.environ.get("WERK_MASTER_REPORT", os.path.join(
        os.environ.get("WERK_UE_TESTBED", "<WERK_UE_TESTBED unset>"), "logs", "master_material.json"))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    unreal.log("WERKMAT %s -> %s" % ("OK" if report["ok"] else "FAIL", out))


build()
