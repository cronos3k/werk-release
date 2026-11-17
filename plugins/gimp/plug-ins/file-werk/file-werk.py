#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""werk for GIMP 3 (Python-Fu 3): File > Open and File > Export for .werk.

Procedures (registered as file load / export handlers for the extension
`werk`):

  file-werk-load    image/1        -> the primary image (SPEC 2.1 primary.image,
                                      loaded with GIMP's own loader for its
                                      format: PNG, JPEG, ...)
                    raster-layers/1 -> the layer tree: pixel layers (and the
                                      rendered caches of text / shape / smart
                                      layers), groups, names, opacity,
                                      visibility, blend modes
  file-werk-export  profile "image/1" (default): the visible layers merged,
                                      8-bit PNG inside an image/1 package
                    profile "raster-layers/1": every pixel layer as a layer,
                                      plus the merged picture as primary.image;
                                      needs a raster-layers/1 TEMPLATE capsule
                                      for its spec/ and loaders/ (argument
                                      `template` or $WERK_RASTER_LAYERS_TEMPLATE)

Reading and writing go through the werk release library (`werk_single.py`,
vendored byte-identically beside this file) and `werk_raster.py`.
"""

import hashlib
import os
import struct
import sys
import tempfile
import zlib

import gi
gi.require_version("Gimp", "3.0")
from gi.repository import Gimp            # noqa: E402
gi.require_version("Gegl", "0.4")
from gi.repository import Gegl            # noqa: E402
from gi.repository import GObject, GLib, Gio  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import werk_single as werk                # noqa: E402
import werk_raster                        # noqa: E402

TOOL = "werk-gimp"
VERSION = "1.0.0"
PARASITE_UUID = "werk-entity-uuid"

MODE_IN = {
    "Normal": "NORMAL", "Dissolve": "DISSOLVE", "PassThrough": "PASS_THROUGH",
    "Darken": "DARKEN_ONLY", "Multiply": "MULTIPLY", "ColorBurn": "BURN",
    "LinearBurn": "LINEAR_BURN", "Lighten": "LIGHTEN_ONLY", "Screen": "SCREEN",
    "ColorDodge": "DODGE", "LinearDodge": "ADDITION", "Overlay": "OVERLAY",
    "SoftLight": "SOFTLIGHT", "HardLight": "HARDLIGHT", "VividLight": "VIVID_LIGHT",
    "LinearLight": "LINEAR_LIGHT", "PinLight": "PIN_LIGHT", "HardMix": "HARD_MIX",
    "Difference": "DIFFERENCE", "Exclusion": "EXCLUSION", "Subtract": "SUBTRACT",
    "Divide": "DIVIDE", "Hue": "HSV_HUE", "Saturation": "HSV_SATURATION",
    "Color": "HSL_COLOR", "Luminosity": "HSV_VALUE",
}
MODE_OUT = {v: k for k, v in MODE_IN.items()}


def _mode(name):
    m = MODE_IN.get(name)
    return getattr(Gimp.LayerMode, m) if m else None


def _mode_name(layer_mode):
    for k, v in MODE_IN.items():
        if getattr(Gimp.LayerMode, v) == layer_mode:
            return k
    return None


def _scratch_dir(near):
    """Beside the package (never a user-profile path), or $WERK_GIMP_TMP."""
    env = os.environ.get("WERK_GIMP_TMP")
    base = env or os.path.join(os.path.dirname(os.path.abspath(near)), ".werk-gimp-tmp")
    try:
        os.makedirs(base, exist_ok=True)
        return tempfile.mkdtemp(prefix="werk-", dir=base), base
    except OSError:
        return tempfile.mkdtemp(prefix="werk-gimp-"), None


def _cleanup(tmp, base):
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    if base and not os.environ.get("WERK_GIMP_TMP"):
        try:
            os.rmdir(base)
        except OSError:
            pass


def _say(msg):
    try:
        Gimp.message(msg)
    except Exception:  # noqa: BLE001
        print(msg)


def _set_uuid(image, uuid):
    if not uuid:
        return
    try:
        image.attach_parasite(Gimp.Parasite.new(PARASITE_UUID, Gimp.PARASITE_PERSISTENT,
                                                list(uuid.encode("ascii"))))
    except Exception:  # noqa: BLE001 - identity is a convenience, never a failure
        pass


def _get_uuid(image):
    try:
        p = image.get_parasite(PARASITE_UUID)
        if p is not None:
            return bytes(p.get_data()).decode("ascii")
    except Exception:  # noqa: BLE001
        pass
    return None


# ---------------------------------------------------------------------------
# load
# ---------------------------------------------------------------------------

def _load_image1(path, pkg):
    nid, ppath, data = pkg.primary_image()
    tmp, base = _scratch_dir(path)
    try:
        f = os.path.join(tmp, "primary" + (os.path.splitext(ppath)[1] or ".png"))
        with open(f, "wb") as fh:
            fh.write(data)
        img = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(f))
    finally:
        _cleanup(tmp, base)
    for L in img.get_layers():
        L.set_name(pkg.manifest.get("entity", {}).get("name") or L.get_name())
    return img


_PRECISION = {"U8": "U8_NON_LINEAR", "U16": "U16_NON_LINEAR", "F32": "FLOAT_NON_LINEAR"}


def _load_raster_layers(path):
    doc, tree, rep = werk_raster.read_document(path)
    W, H = doc["width"], doc["height"]
    # The image precision is the deepest of the document and every decoded
    # surface, so no layer is quantised on the way in (a U8 document may hold
    # u16 and f32 layers).
    rank = {"U8": 0, "U16": 1, "F32": 2}
    deepest = doc["sample_type"] if doc["sample_type"] in rank else "U8"

    def scan(items):
        d = deepest
        for it in items:
            if it["children"] is not None:
                c = scan(it["children"])
            elif it["surface"] is not None:
                c = it["surface"]["sample_type"].upper()
            else:
                continue
            if rank.get(c, 0) > rank[d]:
                d = c
        return d
    deepest = scan(tree)
    prec = getattr(Gimp.Precision, _PRECISION[deepest])
    img = Gimp.Image.new_with_precision(W, H, Gimp.ImageBaseType.RGB, prec)
    notes = []

    def put(items, parent):
        for it in items:                       # bottom to top -> each on top
            if it["children"] is not None:
                g = Gimp.GroupLayer.new(img, it["name"])
                img.insert_layer(g, parent, 0)
                put(it["children"], g)
                L = g
            else:
                L = Gimp.Layer.new(img, it["name"], W, H, Gimp.ImageType.RGBA_IMAGE,
                                   100.0, Gimp.LayerMode.NORMAL)
                img.insert_layer(L, parent, 0)
                s = it["surface"]
                if s is not None:
                    buf = L.get_buffer()
                    buf.set(Gegl.Rectangle.new(0, 0, W, H), werk_raster.babl_format(s),
                            s["data"])
                    buf.flush()
                    L.update(0, 0, W, H)
            m = _mode(it["blend"])
            if m is None:
                notes.append("%s: blend %s shown as Normal" % (it["name"], it["blend"]))
            else:
                try:
                    L.set_mode(m)
                except Exception:  # noqa: BLE001 - e.g. PassThrough on a pixel layer
                    notes.append("%s: blend %s not settable" % (it["name"], it["blend"]))
            L.set_opacity(max(0.0, min(100.0, it["opacity"] * 100.0)))
            L.set_visible(it["visible"])

    put(tree, None)
    _set_uuid(img, doc["entity"].get("uuid"))
    summary = ("werk raster-layers/1: %d x %d, %s; %d report entries (%s)"
               % (W, H, doc["verdict"]["signature"], len(rep.entries),
                  ", ".join(sorted({c for _s, c, _m in rep.entries}))))
    return img, summary, rep, notes


def load_werk(procedure, run_mode, file, metadata, flags, config, data):
    path = file.get_path()
    try:
        pkg = werk.open(path)
    except werk.ContainerRefusal as e:
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error("werk: container refused (%s): %s" % (getattr(e, "code", "?"), e))), flags
    v = pkg.verdict()
    try:
        if v["profile"] == "raster-layers/1":
            img, summary, _rep, _notes = _load_raster_layers(path)
        else:
            img = _load_image1(path, pkg)
            _set_uuid(img, pkg.manifest.get("entity", {}).get("uuid"))
            summary = ("werk %s: signature %s, %d nodes (%d dead)"
                       % (v["profile"], v["signature"], v["nodes"], v["dead"]))
    except Exception as e:  # noqa: BLE001
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                           GLib.Error("werk: %s" % e)), flags
    if v["exit"] != 0 or run_mode == Gimp.RunMode.INTERACTIVE:
        _say(summary + ("" if v["exit"] == 0 else "; error codes %s" % v["error_codes"]))
    return Gimp.ValueArray.new_from_values([
        GObject.Value(Gimp.PDBStatusType, Gimp.PDBStatusType.SUCCESS),
        GObject.Value(Gimp.Image, img),
    ]), flags


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------

def _png(width, height, channels, rows):
    def chunk(tag, body):
        return (struct.pack(">I", len(body)) + tag + body
                + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, {3: 2, 4: 6}[channels], 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(rows, 6)) + chunk(b"IEND", b""))


def rgba_of(drawable, W, H):
    """The drawable's pixels in IMAGE coordinates, W x H, R'G'B'A u8."""
    ok, ox, oy = drawable.get_offsets() if hasattr(drawable, "get_offsets") else (True, 0, 0)
    buf = drawable.get_buffer()
    return bytes(buf.get(Gegl.Rectangle.new(-ox, -oy, W, H), 1.0, "R'G'B'A u8",
                         Gegl.AbyssPolicy.NONE))


def png_of_rgba(rgba, W, H):
    """8-bit PNG; RGB when every alpha byte is 255, else RGBA."""
    opaque = rgba[3::4] == b"\xff" * (W * H)
    C = 3 if opaque else 4
    px = bytearray(rgba)
    if opaque:
        del px[3::4]
    stride = W * C
    rows = bytearray((stride + 1) * H)
    for y in range(H):
        rows[y * (stride + 1) + 1:(y + 1) * (stride + 1)] = px[y * stride:(y + 1) * stride]
    return _png(W, H, C, bytes(rows))


def merged_rgba(image):
    W, H = image.get_width(), image.get_height()
    dup = image.duplicate()
    try:
        layer = dup.merge_visible_layers(Gimp.MergeType.CLIP_TO_IMAGE)
        return rgba_of(layer, W, H)
    finally:
        dup.delete()


def _leaf_layers(layers):
    """Bottom to top, groups flattened to their children."""
    out = []
    for L in reversed(list(layers)):           # GIMP lists top first
        if L.is_group():
            out += _leaf_layers(L.get_children())
        else:
            out.append(L)
    return out


def export_werk(procedure, run_mode, image, file, options, metadata, config, data):
    path = file.get_path()
    profile = config.get_property("profile") or "image/1"
    if run_mode == Gimp.RunMode.INTERACTIVE:
        try:
            gi.require_version("GimpUi", "3.0")
            from gi.repository import GimpUi
            GimpUi.init("file-werk")
            dlg = GimpUi.ProcedureDialog.new(procedure, config, "Export werk")
            dlg.fill(None)
            if not dlg.run():
                dlg.destroy()
                return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
            dlg.destroy()
            profile = config.get_property("profile") or "image/1"
        except Exception:  # noqa: BLE001 - no UI: export with the defaults
            pass
    W, H = image.get_width(), image.get_height()
    name = os.path.splitext(os.path.basename(path))[0] or "image"
    uuid = _get_uuid(image)
    gen = {"tool": TOOL, "version": VERSION}
    try:
        flat = merged_rgba(image)
        png = png_of_rgba(flat, W, H)
        if profile == "raster-layers/1":
            template = config.get_property("template") or \
                os.environ.get("WERK_RASTER_LAYERS_TEMPLATE")
            if not template or not os.path.exists(template):
                raise ValueError("raster-layers/1 export needs a template capsule of that "
                                 "profile (argument `template` or "
                                 "$WERK_RASTER_LAYERS_TEMPLATE): its spec/ and loaders/ "
                                 "are copied into the new file")
            layers = []
            for L in _leaf_layers(image.get_layers()):
                layers.append({"name": L.get_name(), "visible": L.get_visible(),
                               "opacity": L.get_opacity() / 100.0,
                               "blend": _mode_name(L.get_mode()) or "Normal",
                               "rgba": rgba_of(L, W, H)})
            werk_raster.write_capsule(path, template, name, W, H, layers,
                                      composite_png=png, uuid=uuid, tool=TOOL,
                                      version=VERSION)
        else:
            werk.write_image_package(path, png, name, uuid=uuid, generator=gen,
                                     producer=gen)
        v = werk.open(path).verdict()
        if v["exit"] != 0:
            raise ValueError("the werk library did not accept the file just written: %s"
                             % v["error_codes"])
    except Exception as e:  # noqa: BLE001
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                           GLib.Error("werk: %s" % e))
    return Gimp.ValueArray.new_from_values([
        GObject.Value(Gimp.PDBStatusType, Gimp.PDBStatusType.SUCCESS)])


class FileWerk(Gimp.PlugIn):
    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ["file-werk-load", "file-werk-export"]

    def do_create_procedure(self, name):
        if name == "file-werk-load":
            proc = Gimp.LoadProcedure.new(self, name, Gimp.PDBProcType.PLUGIN,
                                          load_werk, None)
            proc.set_menu_label("werk package")
            proc.set_documentation("Load a werk package (.werk)",
                                   "image/1: the primary image. raster-layers/1: the "
                                   "layers. Verified on load (hashes, signature).", name)
            proc.set_extensions("werk")
            proc.set_mime_types("application/x-werk")
        else:
            proc = Gimp.ExportProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, False,
                                            export_werk, None)
            proc.set_image_types("*")
            proc.set_menu_label("werk package")
            proc.set_documentation("Export a werk package (.werk)",
                                   "profile image/1 (default): the visible layers merged "
                                   "into one 8-bit PNG. profile raster-layers/1: every "
                                   "pixel layer, plus the merged picture.", name)
            proc.set_extensions("werk")
            proc.add_string_argument("profile", "Profile",
                                     "image/1 or raster-layers/1", "image/1",
                                     GObject.ParamFlags.READWRITE)
            proc.add_string_argument("template", "raster-layers/1 template",
                                     "an existing raster-layers/1 capsule whose spec/ "
                                     "and loaders/ are copied", "",
                                     GObject.ParamFlags.READWRITE)
        proc.set_attribution("werk", "werk", "2026")
        return proc


Gimp.main(FileWerk.__gtype__, sys.argv)
