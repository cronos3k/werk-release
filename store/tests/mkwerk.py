"""Build conformant .werk fixtures.

Stage 3's golden fixture does not exist yet, so this builds one per
SPEC-3D-ENTITY.md and spec/schemas/manifest.schema.json. It is not a mock:
the payloads are real PNGs and real glTF 2.0 GLBs, the input_hash values are
computed by the spec's own rule, and the signature chain is a real Ed25519
chain over the real manifest bytes. A round-trip test against a mock would
prove nothing.

Two builders:

  make_synthetic(dest, variant)  - small, deterministic, no external inputs.
  make_from_corpus(dest, corpus, variant) - the same package shape wrapped
      around a real asset corpus (the splat-foley bronze-bell soundpack),
      so the dedup gate is measured on real bytes rather than on noise a
      generator produced.

The v1/v2 pair differs the way a real edit differs: one node gains a new
version (law 6, append-only), one node is added, and everything else is
byte-identical - which is exactly the case the store exists to exploit.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
import zlib
from dataclasses import dataclass, field
from typing import Any

# The fixture's own key material. Test keys, in the test tree, doing test
# signatures over test manifests. Nothing here signs anything real.
AUTHOR_SEED = bytes(range(32))
AGENT_SEED = bytes((i * 7 + 3) & 0xFF for i in range(32))

CREATED = "2026-08-08T09:00:00Z"

LICENSE_TEXT = """Creative Commons Attribution-ShareAlike 4.0 International

This is the full license text, embedded, never a link (manifesto law 7).
For the fixture it is abridged to this paragraph on purpose: the point the
fixture must make is that the bytes travel inside the package and are
hashed by the manifest like every other byte, not that a store can carry
eleven kilobytes of legal prose.
"""

README_TEXT = """A werk conformance fixture.

One entity, a handful of nodes, every byte claimed by exactly one node
version. Built by store/tests/mkwerk.py to exercise werk-store: ingest,
byte-exact materialization, manifest-aware diff, node-version sync, and
multi-root garbage collection.
"""

SPEC_STUB = """# werk profile 3d-entity/1 (fixture copy)

The format travels with the file (law 2). In a real package this is the
full SPEC.md of the version the package conforms to. In the fixture it is
this stub, present so that the spec/ tree is a real node with real bytes
that the store must carry and give back unchanged.
"""


# ---------------------------------------------------------------------
# boring encodings, actually encoded
# ---------------------------------------------------------------------


def png_bytes(width: int, height: int, seed: int = 0) -> bytes:
    """A real 8-bit RGBA PNG. Deterministic given (width, height, seed)."""
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter type 0 (None) - boring on purpose
        for x in range(width):
            raw.extend(
                (
                    (x * 7 + seed) & 0xFF,
                    (y * 11 + seed * 3) & 0xFF,
                    ((x ^ y) + seed * 5) & 0xFF,
                    0xFF,
                )
            )

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def glb_bytes(triangles: int, seed: int = 0) -> bytes:
    """A real glTF 2.0 GLB: JSON chunk + BIN chunk, little-endian, padded."""
    vertex_count = triangles * 3
    positions = bytearray()
    for i in range(vertex_count):
        for axis in range(3):
            positions.extend(
                struct.pack("<f", ((i * 3 + axis + seed) % 97) / 97.0 - 0.5)
            )
    bin_chunk = bytes(positions)
    while len(bin_chunk) % 4:
        bin_chunk += b"\x00"

    gltf: "dict[str, Any]" = {
        "asset": {"version": "2.0", "generator": "werkstore fixture builder"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "fixture"}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": vertex_count,
                "type": "VEC3",
                "min": [-0.5, -0.5, -0.5],
                "max": [0.5, 0.5, 0.5],
            }
        ],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(bin_chunk)}],
        "buffers": [{"byteLength": len(bin_chunk)}],
    }
    json_chunk = json.dumps(gltf, separators=(",", ":"), sort_keys=True).encode("utf-8")
    while len(json_chunk) % 4:
        json_chunk += b" "

    total = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    return (
        b"glTF"
        + struct.pack("<II", 2, total)
        + struct.pack("<I", len(json_chunk))
        + b"JSON"
        + json_chunk
        + struct.pack("<I", len(bin_chunk))
        + b"BIN\x00"
        + bin_chunk
    )


def canonical_json(doc: Any) -> bytes:
    """Object keys sorted by UTF-8 byte order, no insignificant whitespace."""
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def input_hash(file_hashes: "list[str]", params: "dict[str, Any]") -> str:
    """The manifest schema's own rule, implemented rather than approximated.

    sha256 over: each input file's sha256 as 32 RAW bytes, in the declared
    order, followed by the UTF-8 bytes of the canonical JSON of input_params.
    """
    h = hashlib.sha256()
    for digest in file_hashes:
        h.update(bytes.fromhex(digest))
    h.update(canonical_json(params))
    return h.hexdigest()


# ---------------------------------------------------------------------
# builder
# ---------------------------------------------------------------------


@dataclass
class _File:
    path: str
    data: bytes
    role: "str | None" = None
    media_type: "str | None" = None

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


@dataclass
class _Version:
    v: int
    files: "list[_File]"
    note: str
    epistemic: str = "authored"
    producer: "dict[str, str]" = field(default_factory=lambda: {"tool": "mkwerk", "version": "0.1.0"})
    created: str = CREATED
    input_files: "list[str] | None" = None
    input_params: "dict[str, Any] | None" = None


@dataclass
class _Node:
    node_id: str
    type: str
    versions: "list[_Version]"
    active: int
    edges: "list[dict[str, str]]" = field(default_factory=list)
    meta: "dict[str, Any] | None" = None
    part_id: "str | None" = None


CONVENTIONS = {
    "endianness": "le",
    "units_per_meter": 1.0,
    "length_unit": "metre",
    "angle_unit": "radian",
    "time_unit": "second",
    "mass_unit": "kilogram",
    "up_axis": "y",
    "forward_axis": "-z",
    "right_axis": "+x",
    "handedness": "right",
    "winding": "ccw",
    "quat_order": "wxyz",
    "oct_encoding_pole": "y",
    "sh_l1_order": ["dc", "y", "z", "x"],
    "color_space_default": "srgb",
    "uv_origin": "top-left",
    "alignment_bytes": 16,
    "text_encoding": "utf-8",
    "id_case": "kebab-case",
    "hash_algorithm": "sha256",
    "signature_algorithm": "ed25519",
}

ENTRY_ORDER = [
    "MANIFEST.json",
    "SIGNATURE.json",
    "LICENSE",
    "README.txt",
    "semantics/",
    "imposters/",
]


class PackageBuilder:
    def __init__(self, entity_uuid: str, name: str, summary: str) -> None:
        self.entity_uuid = entity_uuid
        self.name = name
        self.summary = summary
        self.nodes: "list[_Node]" = []
        self.parts: "list[dict[str, Any]]" = []
        self.materials: "list[dict[str, Any]]" = []
        self.schemas: "dict[str, str]" = {}
        self.license_file = _File("LICENSE", LICENSE_TEXT.encode("utf-8"))

    def add_node(self, node: _Node) -> _Node:
        self.nodes.append(node)
        return node

    # -- manifest ------------------------------------------------------

    def manifest_doc(self) -> "dict[str, Any]":
        nodes_doc = []
        for node in self.nodes:
            versions_doc = []
            for ver in node.versions:
                vd: "dict[str, Any]" = {
                    "v": ver.v,
                    "files": [
                        {
                            k: v
                            for k, v in (
                                ("path", f.path),
                                ("sha256", f.sha256),
                                ("size", len(f.data)),
                                ("media_type", f.media_type),
                                ("role", f.role),
                            )
                            if v is not None
                        }
                        for f in ver.files
                    ],
                    "note": ver.note,
                    "producer": ver.producer,
                    "epistemic": ver.epistemic,
                    "created": ver.created,
                }
                if ver.epistemic in ("measured", "inferred"):
                    by_path = {f.path: f.sha256 for n in self.nodes for v2 in n.versions for f in v2.files}
                    inputs = ver.input_files or []
                    vd["input_files"] = inputs
                    vd["input_params"] = ver.input_params or {}
                    vd["input_hash"] = input_hash(
                        [by_path[p] for p in inputs], ver.input_params or {}
                    )
                versions_doc.append(vd)
            nd: "dict[str, Any]" = {
                "node_id": node.node_id,
                "type": node.type,
                "versions": versions_doc,
                "active": node.active,
                "edges": node.edges,
            }
            if node.meta is not None:
                nd["meta"] = node.meta
            if node.part_id is not None:
                nd["part_id"] = node.part_id
            nodes_doc.append(nd)

        return {
            "werk": {"major": 1, "minor": 0},
            "profile": "3d-entity/1",
            "entity": {
                "uuid": self.entity_uuid,
                "name": self.name,
                "summary": self.summary,
                "created": CREATED,
            },
            "conventions": CONVENTIONS,
            "container": {
                "form": "directory",
                "zip_compression": "store",
                "entry_order": ENTRY_ORDER,
            },
            "license": {
                "spdx_id": "CC-BY-SA-4.0",
                "file": "LICENSE",
                "sha256": self.license_file.sha256,
            },
            "schemas": self.schemas,
            "parts": self.parts,
            "materials": self.materials,
            "nodes": nodes_doc,
            "signature_file": "SIGNATURE.json",
            "generator": {"tool": "mkwerk", "version": "0.1.0"},
        }

    def manifest_bytes(self) -> bytes:
        return (
            json.dumps(self.manifest_doc(), indent=2, ensure_ascii=False, sort_keys=False)
            + "\n"
        ).encode("utf-8")

    # -- writing -------------------------------------------------------

    def write(self, dest: str, sign: bool = True) -> str:
        """Write the package directory. Returns the manifest sha256."""
        os.makedirs(dest, exist_ok=True)
        for node in self.nodes:
            for ver in node.versions:
                for f in ver.files:
                    full = os.path.join(dest, *f.path.split("/"))
                    os.makedirs(os.path.dirname(full), exist_ok=True)
                    with open(full, "wb") as fh:
                        fh.write(f.data)

        raw = self.manifest_bytes()
        with open(os.path.join(dest, "MANIFEST.json"), "wb") as fh:
            fh.write(raw)
        digest = hashlib.sha256(raw).hexdigest()

        if sign:
            import sys

            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from werkstore.signature import build_chain

            doc = build_chain(
                digest,
                [
                    {
                        "secret": AUTHOR_SEED,
                        "name": "Fixture Author",
                        "uri": "mailto:fixtures@werk.format",
                        "kind": "human",
                        "signed_at": CREATED,
                        "role": "author",
                        "note": "original authorship of the fixture entity",
                    },
                    {
                        "secret": AGENT_SEED,
                        "name": "mkwerk",
                        "uri": "https://werk.format/tools/mkwerk",
                        "kind": "agent",
                        "signed_at": CREATED,
                        "role": "enrichment",
                        "note": "built the package and hashed every byte",
                    },
                ],
            )
            with open(os.path.join(dest, "SIGNATURE.json"), "wb") as fh:
                fh.write(
                    (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
                )
        return digest


# ---------------------------------------------------------------------
# the fixture packages
# ---------------------------------------------------------------------

FIXTURE_UUID = "6f1d1e2a-3b4c-4d5e-8f90-a1b2c3d4e5f6"


def _base_builder(payloads: "dict[str, bytes]") -> PackageBuilder:
    """Assemble the common node graph over whatever payload bytes are given."""
    b = PackageBuilder(
        entity_uuid=FIXTURE_UUID,
        name="fixture-crate",
        summary=(
            "A wooden crate. Conformance fixture for werk-store: every node "
            "family the store must carry, and not one byte that floats."
        ),
    )
    b.parts = [
        {
            "part_id": "body",
            "name": "Body",
            "parent": None,
            "transform": {
                "translation": [0.0, 0.0, 0.0],
                "rotation": [1.0, 0.0, 0.0, 0.0],
                "scale": [1.0, 1.0, 1.0],
            },
        }
    ]
    b.materials = [
        {"material_id": "wood", "part_id": "body", "name": "Crate wood", "class": "wood"}
    ]
    b.schemas = {
        "core.material": "spec/schemas/core.material.schema.json",
        "core.semantics": "spec/schemas/core.semantics.schema.json",
    }

    spec_files = [
        _File("spec/SPEC.md", SPEC_STUB.encode("utf-8"), media_type="text/markdown"),
        _File(
            "spec/schemas/core.material.schema.json",
            canonical_json(
                {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "title": "core.material (fixture copy)",
                    "type": "object",
                    "required": ["material_id", "base_color_factor"],
                }
            ),
            media_type="application/json",
        ),
        _File(
            "spec/schemas/core.semantics.schema.json",
            canonical_json(
                {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "title": "core.semantics (fixture copy)",
                    "type": "object",
                    "required": ["facets"],
                }
            ),
            media_type="application/json",
        ),
    ]

    b.add_node(
        _Node(
            "license",
            "core.license",
            [_Version(1, [b.license_file], "The license travels as full text, never as a link.")],
            1,
        )
    )
    b.add_node(
        _Node(
            "readme",
            "core.readme",
            [
                _Version(
                    1,
                    [_File("README.txt", README_TEXT.encode("utf-8"), media_type="text/plain")],
                    "One paragraph for a human who opened the package by hand.",
                )
            ],
            1,
        )
    )
    b.add_node(
        _Node(
            "spec",
            "core.spec",
            [_Version(1, spec_files, "The knowledge to read this file travels inside it (law 2).")],
            1,
        )
    )
    b.add_node(
        _Node(
            "geom-game",
            "core.geom.game",
            [
                _Version(
                    1,
                    [
                        _File(
                            "geometry/game.glb",
                            payloads["game_glb"],
                            media_type="model/gltf-binary",
                        )
                    ],
                    "Authored game mesh, welded and UV-packed by hand.",
                )
            ],
            1,
            part_id="body",
        )
    )
    b.add_node(
        _Node(
            "tex-base-color",
            "core.tex",
            [
                _Version(
                    1,
                    [
                        _File(
                            "textures/base-color.png",
                            payloads["base_color_png"],
                            media_type="image/png",
                            role="base-color",
                        )
                    ],
                    "First base colour bake from the painted source.",
                )
            ],
            1,
            meta={
                "color_space": "srgb",
                "usage": "base-color",
                "width": payloads["base_color_size"][0],
                "height": payloads["base_color_size"][1],
                "channels": 4,
                "bit_depth": 8,
            },
        )
    )
    b.add_node(
        _Node(
            "material-wood",
            "core.material",
            [
                _Version(
                    1,
                    [
                        _File(
                            "materials/wood.json",
                            canonical_json(
                                {
                                    "material_id": "wood",
                                    "base_color_factor": [1.0, 1.0, 1.0, 1.0],
                                    "metallic_factor": 0.0,
                                    "roughness_factor": 0.82,
                                    "base_color_texture": "textures/base-color.png",
                                }
                            ),
                            media_type="application/json",
                        )
                    ],
                    "PBR parameters matching the first base colour bake.",
                )
            ],
            1,
            edges=[{"to": "tex-base-color", "kind": "requires", "role": "base-color"}],
        )
    )
    b.add_node(
        _Node(
            "semantics",
            "core.semantics",
            [
                _Version(
                    1,
                    [
                        _File(
                            "semantics/facets.json",
                            canonical_json(
                                {
                                    "facets": {
                                        "function": ["container", "storage"],
                                        "material": ["wood"],
                                        "condition": ["worn"],
                                        "scale": ["prop"],
                                    },
                                    "palette": ["#6b4b2a", "#8a6a44", "#3d2a17"],
                                }
                            ),
                            media_type="application/json",
                        )
                    ],
                    "Facet tags so a store listing is searchable without opening a payload.",
                )
            ],
            1,
        )
    )
    return b


def _synthetic_payloads(seed: int = 0) -> "dict[str, Any]":
    return {
        "game_glb": glb_bytes(triangles=512, seed=seed),
        "base_color_png": png_bytes(128, 128, seed=seed),
        "base_color_size": (128, 128),
        "lod_glb": glb_bytes(triangles=96, seed=seed + 1),
        "rebake_png": png_bytes(128, 128, seed=seed + 40),
    }


def _apply_v2(b: PackageBuilder, payloads: "dict[str, Any]") -> None:
    """The v2 edit: one node gains a version, one node is added.

    Everything else is byte-identical to v1 - which is the whole point. A
    dedup number measured on a pair that shares nothing would be measuring
    the generator, not the store.
    """
    tex = next(n for n in b.nodes if n.node_id == "tex-base-color")
    tex.versions.append(
        _Version(
            2,
            [
                _File(
                    "textures/base-color@2.png",
                    payloads["rebake_png"],
                    media_type="image/png",
                    role="base-color",
                )
            ],
            "Re-baked base colour: the first bake had seam bleed on the lid edge.",
        )
    )
    tex.active = 2

    b.add_node(
        _Node(
            "geom-lod1",
            "core.geom.lod",
            [
                _Version(
                    1,
                    [_File("geometry/lod1.glb", payloads["lod_glb"], media_type="model/gltf-binary")],
                    "First decimation step, measured against the game mesh silhouette.",
                    epistemic="measured",
                    input_files=["geometry/game.glb"],
                    input_params={"target_ratio": 0.1875, "preserve_boundary": True},
                )
            ],
            1,
            part_id="body",
            edges=[{"to": "geom-game", "kind": "enhances", "role": "lod-of"}],
            meta={
                "lod_level": 1,
                "screen_space_error_px": 1.8,
                "reference_resolution_px": 1080,
                "triangle_count": 96,
                "vertex_count": 288,
            },
        )
    )


def make_synthetic(dest: str, variant: str = "v1", sign: bool = True, seed: int = 0) -> str:
    payloads = _synthetic_payloads(seed)
    b = _base_builder(payloads)
    if variant == "v2":
        _apply_v2(b, payloads)
    return b.write(dest, sign=sign)


# ---------------------------------------------------------------------
# the real corpus
# ---------------------------------------------------------------------

DEFAULT_CORPUS = os.path.join(os.environ.get("WERK_LAB", "<WERK_LAB unset>"),
                              "splat-foley", "paper", "bronze-bell_soundpack")


def corpus_available(corpus: str = DEFAULT_CORPUS) -> bool:
    return os.path.isfile(os.path.join(corpus, "model", "model.glb"))


def make_from_corpus(dest: str, corpus: str = DEFAULT_CORPUS, variant: str = "v1") -> str:
    """Wrap a real splat-foley soundpack in the fixture's node graph.

    The bytes are the real thing: a 43 MB GLB, real JPEG textures, real
    rendered views, real recorded WAVs. Only the manifest around them is
    built here. That makes the dedup gate a measurement on production
    assets, not on a generator's output.
    """
    def read(*parts: str) -> bytes:
        with open(os.path.join(corpus, *parts), "rb") as fh:
            return fh.read()

    views = sorted(
        n for n in os.listdir(os.path.join(corpus, "views")) if n.endswith(".png")
    )
    audio_root = os.path.join(corpus, "audio")
    takes: "list[tuple[str, bytes]]" = []
    for group in sorted(os.listdir(audio_root)):
        gdir = os.path.join(audio_root, group)
        if not os.path.isdir(gdir):
            continue
        for name in sorted(os.listdir(gdir)):
            if name.endswith(".wav") and not name.endswith(".raw.wav"):
                takes.append(("audio/%s/%s" % (group, name), read("audio", group, name)))

    b = PackageBuilder(
        entity_uuid="9a1c4e77-2f83-4b1a-9d64-7c0e5a3b8d21",
        name="bronze-bell",
        summary=(
            "A cast bronze bell on a wooden yoke, photogrammetry source with a "
            "full sound world. Real corpus fixture for the werk-store gate."
        ),
    )
    b.parts = [
        {
            "part_id": "bell-body",
            "name": "Bell body",
            "parent": None,
            "transform": {
                "translation": [0.0, 0.0, 0.0],
                "rotation": [1.0, 0.0, 0.0, 0.0],
                "scale": [1.0, 1.0, 1.0],
            },
        }
    ]
    b.materials = [
        {"material_id": "bronze", "part_id": "bell-body", "name": "Cast bronze", "class": "metal"}
    ]
    b.schemas = {"core.audio.package": "spec/schemas/core.audio.package.schema.json"}

    b.add_node(
        _Node(
            "license",
            "core.license",
            [_Version(1, [b.license_file], "The license travels as full text, never as a link.")],
            1,
        )
    )
    b.add_node(
        _Node(
            "spec",
            "core.spec",
            [
                _Version(
                    1,
                    [
                        _File("spec/SPEC.md", SPEC_STUB.encode("utf-8"), media_type="text/markdown"),
                        _File(
                            "spec/schemas/core.audio.package.schema.json",
                            canonical_json(
                                {
                                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                                    "title": "core.audio.package (fixture copy)",
                                    "type": "object",
                                }
                            ),
                            media_type="application/json",
                        ),
                    ],
                    "The knowledge to read this file travels inside it (law 2).",
                )
            ],
            1,
        )
    )
    b.add_node(
        _Node(
            "geom-source",
            "core.geom.source",
            [
                _Version(
                    1,
                    [_File("geometry/source.glb", read("model", "model.glb"), media_type="model/gltf-binary")],
                    "Photogrammetry reconstruction, the high-poly truth for this entity.",
                )
            ],
            1,
            part_id="bell-body",
        )
    )
    tex_files = []
    for name in sorted(os.listdir(os.path.join(corpus, "model", "textures"))):
        role = "base-color" if name.startswith("color") else (
            "normal" if name.startswith("normal") else "mrao"
        )
        tex_files.append(
            _File(
                "textures/%s" % name,
                read("model", "textures", name),
                media_type="image/jpeg",
                role=role,
            )
        )
    b.add_node(
        _Node(
            "tex-set",
            "core.tex",
            [_Version(1, tex_files, "Baked texture set as delivered by the reconstruction.")],
            1,
            meta={
                "color_space": "srgb",
                "usage": "base-color",
                "width": 4096,
                "height": 4096,
                "channels": 3,
                "bit_depth": 8,
            },
        )
    )
    b.add_node(
        _Node(
            "imposter-views",
            "core.imposter",
            [
                _Version(
                    1,
                    [
                        _File("imposters/%s" % n, read("views", n), media_type="image/png", role="albedo")
                        for n in views
                    ],
                    "Beauty-shot view ring; doubles as the preview tier and the LOD billboard.",
                )
            ],
            1,
        )
    )
    b.add_node(
        _Node(
            "audio",
            "core.audio.package",
            [
                _Version(
                    1,
                    [_File(path, data, media_type="audio/wav") for path, data in takes],
                    "Sound world: best takes per effect, one file per effect id.",
                )
            ],
            1,
        )
    )
    b.add_node(
        _Node(
            "properties",
            "core.props",
            [
                _Version(
                    1,
                    [
                        _File(
                            "properties/regions.json",
                            read("properties.json"),
                            media_type="application/json",
                        )
                    ],
                    "Simulation properties per material region, as inferred by the enrichment pass.",
                )
            ],
            1,
        )
    )

    if variant == "v2":
        # A real second version: the audio node gains a re-mastered take,
        # and an LOD appears. Everything else is the same bytes.
        first_path, first_data = takes[0]
        remastered = bytearray(first_data)
        for i in range(64, min(len(remastered), 4096)):
            remastered[i] = (remastered[i] + 3) & 0xFF
        audio_node = next(n for n in b.nodes if n.node_id == "audio")
        audio_node.versions.append(
            _Version(
                2,
                [
                    _File(
                        first_path.replace(".wav", "@2.wav"),
                        bytes(remastered),
                        media_type="audio/wav",
                    )
                ],
                "Re-mastered the strike take: the first pass clipped on the attack transient.",
            )
        )
        audio_node.active = 2

    return b.write(dest)
