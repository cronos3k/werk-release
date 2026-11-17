"""image/1 <-> Blender image datablocks, through the werk release library.

Import: `primary_image()` (SPEC 2.1: `primary.image`, never files[0]) -> the
exact payload bytes are loaded and PACKED into the .blend, so the image
datablock carries the package's bytes, not a re-encoding of them.

Export: an image datablock -> 8-bit PNG (RGB, or RGBA when any pixel is not
opaque), encoded here with zlib from the datablock's pixels, then
`write_image_package()`. Float images are converted linear -> sRGB first and
clamped to [0, 1]; 16-bit and HDR depth is NOT carried (stated limit).
"""

import os
import struct
import time
import zlib

import bpy

from .common import Scratch, sha256_hex
from .libwerk import werk

TOOL = "werk_blender"
TOOL_VERSION = "1.1.0"

PROP_UUID = "werk_entity_uuid"
PROP_NAME = "werk_entity_name"
PROP_SOURCE = "werk_source"
PROP_NODE = "werk_primary_node"
PROP_PAYLOAD_SHA = "werk_payload_sha256"
PROP_SIGNATURE = "werk_signature"

REPORT_TEXT = "werk_import_report.txt"


class ImageResult(object):
    """What an image/1 import produced, in numbers a gate can assert on."""

    kind = "image"

    def __init__(self):
        self.source_path = ""
        self.image = None
        self.images = []
        self.objects = []
        self.meshes = []
        self.report = []
        self.library_verdict = None
        self.signature = "absent"
        self.signature_verified = "unknown"
        self.entity_uuid = None
        self.entity_name = ""
        self.node_id = None
        self.payload_path = None
        self.payload_sha256 = None
        self.payload_bytes = 0
        self.width = 0
        self.height = 0
        self.nodes_total = self.nodes_alive = self.nodes_dead = 0
        self.nodes_skipped_unknown = 0
        self.seconds = 0.0

    def add(self, severity, code, message):
        self.report.append((severity, code, message))

    def errors(self):
        return sum(1 for s, _, _ in self.report if s == "error")

    def as_text(self):
        lines = ["werk image import report", "========================", "",
                 "source      : %s" % self.source_path,
                 "entity      : %s (%s)" % (self.entity_name, self.entity_uuid),
                 "signature   : %s (werk library, Ed25519 checked)" % self.signature_verified,
                 "primary     : %s -> %s, %d bytes, sha256 %s"
                 % (self.node_id, self.payload_path, self.payload_bytes, self.payload_sha256),
                 "image       : %d x %d" % (self.width, self.height),
                 "nodes       : %d total, %d alive, %d dead, %d skipped"
                 % (self.nodes_total, self.nodes_alive, self.nodes_dead,
                    self.nodes_skipped_unknown), "", "REPORT", "------"]
        if not self.report:
            lines.append("(none)")
        for sev, code, msg in self.report:
            lines.append("[%s] %s: %s" % (sev, code, msg))
        return "\n".join(lines) + "\n"


def import_image_file(filepath, pack=True, write_report_text=True):
    """Load the primary image of an image/1 package as an image datablock.

    Raises RuntimeError only on a container-scoped refusal or when the
    package has no usable primary image; node damage elsewhere is reported.
    """
    t0 = time.time()
    res = ImageResult()
    res.source_path = os.path.abspath(filepath)
    try:
        pkg = werk.open(res.source_path)
    except werk.ContainerRefusal as e:
        raise RuntimeError("werk: container refused (%s): %s"
                           % (getattr(e, "code", "?"), e))
    v = pkg.verdict()
    res.library_verdict = dict(v)
    res.signature = res.signature_verified = v["signature"]
    res.nodes_total, res.nodes_alive = v["nodes"], v["alive"]
    res.nodes_dead, res.nodes_skipped_unknown = v["dead"], v["skipped"]
    for e in pkg.report:
        res.add(e.severity, e.code, ("%s: %s" % (e.node, e.message)) if e.node
                else e.message)
    ent = pkg.manifest.get("entity", {})
    res.entity_uuid = ent.get("uuid")
    res.entity_name = ent.get("name") or os.path.basename(res.source_path)

    try:
        nid, ppath, data = pkg.primary_image()
    except Exception as e:  # noqa: BLE001
        raise RuntimeError("werk: no usable primary image in %s: %s"
                           % (res.source_path, e))
    res.node_id, res.payload_path = nid, ppath
    res.payload_sha256, res.payload_bytes = sha256_hex(data), len(data)

    ext = os.path.splitext(ppath)[1] or ".png"
    with Scratch(near=res.source_path) as scratch:
        if scratch.fell_back:
            res.add("info", "scratch-fallback",
                    "could not write beside the package; used the system temp "
                    "directory for the intermediate image file")
        tmp = scratch.file("primary" + ext)
        with open(tmp, "wb") as fh:
            fh.write(data)
        img = bpy.data.images.load(tmp, check_existing=False)
        if pack:
            img.pack()
        # Size is read while the file still exists.
        res.width, res.height = int(img.size[0]), int(img.size[1])
        img.name = res.entity_name
        if pack:
            img.filepath = ""
            img.filepath_raw = ""
    try:
        img.colorspace_settings.name = "sRGB"
    except TypeError:
        pass
    img[PROP_UUID] = res.entity_uuid or ""
    img[PROP_NAME] = res.entity_name
    img[PROP_SOURCE] = res.source_path
    img[PROP_NODE] = nid
    img[PROP_PAYLOAD_SHA] = res.payload_sha256
    img[PROP_SIGNATURE] = res.signature_verified
    res.image = img
    res.images = [img]
    res.seconds = time.time() - t0
    if write_report_text:
        t = bpy.data.texts.get(REPORT_TEXT) or bpy.data.texts.new(REPORT_TEXT)
        t.clear()
        t.write(res.as_text())
    return res


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------

def _png_bytes(width, height, channels, rows_top_down):
    """A minimal valid PNG: IHDR, one IDAT (filter 0 rows), IEND."""
    def chunk(tag, body):
        return (struct.pack(">I", len(body)) + tag + body
                + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))
    colour_type = {3: 2, 4: 6}[channels]
    ihdr = struct.pack(">IIBBBBB", width, height, 8, colour_type, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(rows_top_down, 6)) + chunk(b"IEND", b""))


def image_to_png(img):
    """(png_bytes, width, height, channels) from an image datablock."""
    import numpy as np
    w, h = int(img.size[0]), int(img.size[1])
    if w == 0 or h == 0:
        raise ValueError("image `%s` has no pixels (size %dx%d)" % (img.name, w, h))
    c = int(img.channels)
    px = np.empty(w * h * c, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, c)[::-1]          # Blender stores bottom row first
    if c == 1:
        px = np.repeat(px, 3, axis=2)
    elif c == 2:
        px = np.concatenate([np.repeat(px[:, :, :1], 3, axis=2), px[:, :, 1:]], axis=2)
    rgb = px[:, :, :3]
    if img.is_float and img.colorspace_settings.name not in ("sRGB",):
        rgb = np.clip(rgb, 0.0, 1.0)
        rgb = np.where(rgb <= 0.0031308, rgb * 12.92,
                       1.055 * np.power(rgb, 1.0 / 2.4) - 0.055)
    out = [rgb]
    channels = 3
    if px.shape[2] == 4:
        a = px[:, :, 3:4]
        if float(a.min()) < 1.0:
            out.append(a)
            channels = 4
    arr = np.concatenate(out, axis=2)
    arr = np.rint(np.clip(arr, 0.0, 1.0) * 255.0).astype(np.uint8)
    rows = np.zeros((h, 1 + w * channels), dtype=np.uint8)
    rows[:, 1:] = arr.reshape(h, w * channels)
    return _png_bytes(w, h, channels, rows.tobytes()), w, h, channels


class ImageExportResult(object):
    def __init__(self):
        self.path = ""
        self.bytes = 0
        self.sha256 = ""
        self.png_sha256 = ""
        self.width = self.height = self.channels = 0
        self.entity_uuid = ""
        self.reused_identity = False
        self.library_verdict = None
        self.report = []
        self.seconds = 0.0

    def add(self, severity, code, message):
        self.report.append((severity, code, message))

    def errors(self):
        return sum(1 for s, _, _ in self.report if s == "error")


def export_image_file(filepath, image, name=None, license_text=None, created=None,
                      uuid=None):
    """Write `image` (a bpy image datablock or its name) as an image/1 package.

    Identity survives (law 4): an image that came from `import_image_file`
    keeps its entity uuid unless `uuid` is given.
    """
    t0 = time.time()
    if isinstance(image, str):
        image = bpy.data.images[image]
    res = ImageExportResult()
    res.path = os.path.abspath(filepath)
    png, res.width, res.height, res.channels = image_to_png(image)
    res.png_sha256 = sha256_hex(png)
    prior = image.get(PROP_UUID) or None
    res.reused_identity = bool(prior) and uuid is None
    ent_uuid = uuid or prior
    if not license_text:
        res.add("warn", "license-unspecified",
                "no licence text was given; the library's 'terms not established' "
                "LICENSE was written")
    gen = {"tool": TOOL, "version": TOOL_VERSION}
    werk.write_image_package(
        res.path, png, name or image.get(PROP_NAME) or image.name,
        uuid=ent_uuid, created=created, license_text=license_text,
        generator=gen, producer=gen)
    res.entity_uuid = werk.open(res.path).manifest["entity"]["uuid"]
    with open(res.path, "rb") as fh:
        blob = fh.read()
    res.bytes, res.sha256 = len(blob), sha256_hex(blob)
    from .libwerk import verdict_of
    res.library_verdict, why = verdict_of(res.path)
    if res.library_verdict is None or res.library_verdict.get("exit") != 0:
        res.add("error", "self-verify-failed",
                "the werk library did not accept the package just written: %s"
                % (why or res.library_verdict))
    res.seconds = time.time() - t0
    return res
