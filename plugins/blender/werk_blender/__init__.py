"""werk_blender — import and export werk 3D entities in Blender.

Two ways in, and they share every line of the work:

  * the UI: File > Import > werk Entity (.werk), File > Export > werk Entity
  * headless, for CI and pipelines:

        blender --background --python-expr "import werk_blender; \\
            werk_blender.import_file(r'crate.werk')"

        blender --background --python-expr "import werk_blender; \\
            werk_blender.export_file(r'out.werk')"

Zero external dependencies: the Python standard library and `bpy`, with werk
parsing vendored byte-identically from `loaders/werk_read.py`. No pip, ever —
an add-on that needed one would be a promise about another file, which law 1
bans at the constitutional level.

Blender 4.2 LTS through 5.0 (gated on 4.2.1 and 5.0.1). Registered through
`bl_info`; the 4.2+ extension platform, 5.0 included, accepts a legacy add-on
unchanged, so one form serves both. Installing from a zip and running the package straight off disk both
work, and `test_gate.py` measures both.
"""

bl_info = {
    "name": "werk Entity (.werk)",
    "author": "werk",
    "version": (1, 1, 1),
    "blender": (4, 0, 0),
    "location": "File > Import/Export > werk Entity (.werk)",
    "description": "Import and export werk hermetic 3D entity packages",
    "category": "Import-Export",
    "doc_url": "https://github.com/werk-format/werk",
}

import os
import sys

# Running under `--background --python-expr` means this package may be imported
# before Blender has been told where it lives. Put its parent on sys.path so
# `import werk_blender` works from a checkout as well as from an install.
_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from . import axes, bounds, envelope, wzip          # noqa: E402

__all__ = ["import_file", "export_file", "import_image_file", "export_image_file",
           "selftest", "register", "unregister", "bl_info"]


# `importer` and `exporter` import `bpy` at module level, so they are pulled in
# on first use rather than at package import. That is what lets `selftest()`
# run the axis, bounds, zip and MessagePack checks under a plain CPython with
# no Blender anywhere — the parts that fail silently should not need a 400 MB
# application to check.

def import_file(filepath, **kwargs):
    """Headless entry point. See `importer.import_file` for the options."""
    from .importer import import_file as _impl
    return _impl(filepath, **kwargs)


def export_file(filepath, objects=None, **kwargs):
    """Headless entry point. See `exporter.export_file` for the options."""
    from .exporter import export_file as _impl
    return _impl(filepath, objects=objects, **kwargs)


def import_image_file(filepath, **kwargs):
    """Headless: image/1 -> a packed image datablock. See `image_io`."""
    from .image_io import import_image_file as _impl
    return _impl(filepath, **kwargs)


def export_image_file(filepath, image, **kwargs):
    """Headless: an image datablock (or its name) -> image/1. See `image_io`."""
    from .image_io import export_image_file as _impl
    return _impl(filepath, image, **kwargs)


def selftest(verbose=False):
    """Every pure-Python invariant this add-on relies on, as measurements.

    Runs without Blender, which is the point: the axis swing, the minimal
    sphere, the zip writer and the MessagePack encoder are the parts that are
    wrong silently, and they should not need a 400 MB application to check.
    Returns a list of failure strings; empty means everything held.
    """
    bad = []
    for name, mod in (("axes", axes), ("bounds", bounds), ("wzip", wzip),
                      ("envelope", envelope)):
        if verbose:
            print("[%s]" % name)
        bad += ["%s: %s" % (name, f) for f in mod.selftest(verbose=verbose)]
    return bad


# ---------------------------------------------------------------------------
# Blender UI. Everything below is registration; the work is in the modules.
# ---------------------------------------------------------------------------

try:
    import bpy
    from bpy.props import BoolProperty, StringProperty
    from bpy_extras.io_utils import ExportHelper, ImportHelper
    _HAVE_BPY = True
except ImportError:                                   # pragma: no cover
    _HAVE_BPY = False


if _HAVE_BPY:

    class WERK_OT_import(bpy.types.Operator, ImportHelper):
        """Import a werk package: a 3D entity, or an image/1 image as an image datablock"""

        bl_idname = "werk.import_entity"
        bl_label = "Import werk Entity"
        bl_options = {"REGISTER", "UNDO"}

        filename_ext = ".werk"
        filter_glob: StringProperty(default="*.werk", options={"HIDDEN"})

        import_lods: BoolProperty(
            name="Import all LODs",
            description="Put each core.geom.lod node in its own lod1..lod4 "
                        "collection",
            default=False)
        import_source: BoolProperty(
            name="Import source-hi",
            description="Also import core.geom.source, the archival master. Off by "
                        "default because it is the big one",
            default=False)
        import_colliders: BoolProperty(
            name="Colliders",
            description="core.phys.colliders as sphere/box empties in a `colliders` "
                        "collection",
            default=True)
        rigid_body_colliders: BoolProperty(
            name="As rigid bodies", description="Attempt Blender rigid-body shapes",
            default=False)
        import_skeleton: BoolProperty(name="Skeleton", default=True)
        import_animation: BoolProperty(name="Animation clips", default=True)
        import_audio_preview: BoolProperty(
            name="Load preview sound",
            description="Load the one-shot named by primary.sound as a sound "
                        "datablock. The full audio set is listed in the report "
                        "either way",
            default=False)

        def execute(self, context):
            try:
                res = import_file(
                    self.filepath,
                    import_lods=self.import_lods,
                    import_source=self.import_source,
                    import_colliders=self.import_colliders,
                    rigid_body_colliders=self.rigid_body_colliders,
                    import_skeleton=self.import_skeleton,
                    import_animation=self.import_animation,
                    import_audio_preview=self.import_audio_preview)
            except RuntimeError as e:
                # Container-scoped refusal: the only scope allowed to come back
                # empty-handed (SPEC section 10.1).
                self.report({"ERROR"}, str(e))
                return {"CANCELLED"}

            self.report(
                {"INFO"},
                "werk: %d node(s) — %d alive, %d dead, %d skipped; signature %s; "
                "%d object(s) in %.2f s. Full report in the text editor as "
                "`werk_import_report.txt`."
                % (res.nodes_total, res.nodes_alive, res.nodes_dead,
                   res.nodes_skipped_unknown, res.signature, len(res.objects),
                   res.seconds))
            for sev, code, msg in res.report:
                if sev == "error":
                    self.report({"WARNING"}, "%s: %s" % (code, msg))
            # A load is never failed by damage alone (SPEC section 10.1): the
            # operator succeeds with dead nodes and the report says what died.
            return {"FINISHED"}

    class WERK_OT_export(bpy.types.Operator, ExportHelper):
        """Export the selection as a werk hermetic 3D entity package"""

        bl_idname = "werk.export_entity"
        bl_label = "Export werk Entity"
        bl_options = {"REGISTER"}

        filename_ext = ".werk"
        filter_glob: StringProperty(default="*.werk", options={"HIDDEN"})

        use_selection: BoolProperty(
            name="Selection only",
            description="Export the selected objects. Off means the whole scene "
                        "collection",
            default=True)
        include_spec: BoolProperty(
            name="Embed spec/",
            description="Carry the format specification inside the package (law 2). "
                        "Turning this off leaves the manifest's `schemas` map "
                        "pointing at files that are not in the package",
            default=True)
        include_loader: BoolProperty(
            name="Embed reader",
            description="Carry loaders/werk_read.py inside the package (law 1)",
            default=True)
        export_skeleton: BoolProperty(name="Skeleton", default=True)
        export_animation: BoolProperty(name="Animation clips", default=True)

        def execute(self, context):
            objs = list(context.selected_objects) if self.use_selection else None
            try:
                res = export_file(
                    self.filepath, objects=objs,
                    include_spec=self.include_spec,
                    include_loader=self.include_loader,
                    export_skeleton=self.export_skeleton,
                    export_animation=self.export_animation)
            except ValueError as e:
                self.report({"ERROR"}, str(e))
                return {"CANCELLED"}

            self.report(
                {"INFO"},
                "werk: wrote %d bytes, %d entries, %d nodes, %d files; entity %s "
                "(%s); preview prefix %d B; %.2f s"
                % (res.bytes, res.entries, res.nodes, res.files, res.entity_uuid,
                   "identity carried forward" if res.reused_identity
                   else "new identity", res.preview_prefix_bytes, res.seconds))
            for sev, code, msg in res.report:
                if sev in ("warn", "error"):
                    self.report({"WARNING"}, "%s: %s" % (code, msg))
            return {"FINISHED"}

    class WERK_OT_export_image(bpy.types.Operator, ExportHelper):
        """Export an image datablock as a werk image/1 package"""

        bl_idname = "werk.export_image"
        bl_label = "Export werk Image"
        bl_options = {"REGISTER"}

        filename_ext = ".werk"
        filter_glob: StringProperty(default="*.werk", options={"HIDDEN"})
        image_name: StringProperty(
            name="Image",
            description="The image datablock to export (default: the image shown "
                        "in the active Image Editor, else the first image)")

        def invoke(self, context, event):
            if not self.image_name:
                space = getattr(context, "space_data", None)
                img = getattr(space, "image", None) if space else None
                if img is None and bpy.data.images:
                    img = bpy.data.images[0]
                if img is not None:
                    self.image_name = img.name
            return ExportHelper.invoke(self, context, event)

        def draw(self, context):
            self.layout.prop_search(self, "image_name", bpy.data, "images")

        def execute(self, context):
            if self.image_name not in bpy.data.images:
                self.report({"ERROR"}, "no image named `%s`" % self.image_name)
                return {"CANCELLED"}
            try:
                res = export_image_file(self.filepath, self.image_name)
            except ValueError as e:
                self.report({"ERROR"}, str(e))
                return {"CANCELLED"}
            self.report({"INFO"}, "werk: wrote image/1, %d bytes, %dx%d, %d channel(s)"
                        % (res.bytes, res.width, res.height, res.channels))
            for sev, code, msg in res.report:
                if sev in ("warn", "error"):
                    self.report({"WARNING"}, "%s: %s" % (code, msg))
            return {"FINISHED"}

    def _menu_import(self, context):
        self.layout.operator(WERK_OT_import.bl_idname, text="werk Entity (.werk)")

    def _menu_export(self, context):
        self.layout.operator(WERK_OT_export.bl_idname, text="werk Entity (.werk)")
        self.layout.operator(WERK_OT_export_image.bl_idname, text="werk Image (.werk)")

    _CLASSES = (WERK_OT_import, WERK_OT_export, WERK_OT_export_image)

    def register():
        for cls in _CLASSES:
            bpy.utils.register_class(cls)
        bpy.types.TOPBAR_MT_file_import.append(_menu_import)
        bpy.types.TOPBAR_MT_file_export.append(_menu_export)

    def unregister():
        bpy.types.TOPBAR_MT_file_export.remove(_menu_export)
        bpy.types.TOPBAR_MT_file_import.remove(_menu_import)
        for cls in reversed(_CLASSES):
            bpy.utils.unregister_class(cls)

else:                                                 # pragma: no cover

    def register():
        raise RuntimeError("werk_blender.register() needs Blender")

    def unregister():
        raise RuntimeError("werk_blender.unregister() needs Blender")
