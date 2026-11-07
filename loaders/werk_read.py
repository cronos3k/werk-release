#!/usr/bin/env python3
"""werk_read.py — a single-file, zero-dependency bootstrap reader for werk.

This file ships INSIDE werk packages as a `core.loader` node. Law 1 taken to
its conclusion: a werk file does not merely describe how to read it, it carries
a working reader. If you have this file and a `.werk`, you can list its graph,
verify every byte and pull payloads out, with nothing installed.

Implements, from the spec that travels beside it in `spec/`:
    spec/SPEC.md                     §1 container, §2 manifest, §5 degradation,
                                     §6 signature states, §10 reader checklist
    spec/MINI-SPECS.md               §5 zip (EOCD / central directory / local
                                     header), §11 SHA-256
    spec/layouts/ENVELOPE.layout.txt §1-§7 the binary envelope and the
                                     MessagePack subset its header uses

Declared capabilities (honest and narrow — the conformance harness runs each).
This list, the `CAPABILITIES` constant below and the `meta.capabilities` array
a manifest declares for this node are ONE list; a gauntlet reader found two of
them disagreeing, which is exactly the drift the format exists to prevent
(S-19), and `tests/run_gate_reference.py` now compares all three and checks
each name against the `capabilities` enum of both manifest schemas:
    read-manifest, verify-hashes, read-envelope, materialize,
    summarize-points, summarize-gsplat
The next line is the machine-readable statement of it, and it is what a writer
that embeds this file reads to fill `meta.capabilities` (tools/loader_caps.py):
    WERK-LOADER-CAPABILITIES: read-manifest verify-hashes read-envelope materialize summarize-points summarize-gsplat
(`materialize` is `--extract <node_id> --out <dir>`. The two summarize-*
capabilities are `--points` and `--gsplat`: a DECODE of a WKPC or WKGS payload
from the offsets its own header declares, added in Stage 12 because Python is
this format's demo face and "here are your positions and colours" is the first
thing anyone wants from a splat. They are declared separately from
`read-envelope` on purpose — reading an envelope's section table and
interpreting a section's contents are different claims, and the Rust and C
loaders make only the first.)

Zip method 8 (DEFLATE) IS read (ruling 9 of 2026-10-13), through the standard
library's `zlib`; the inflated bytes are checked against the directory's size
and CRC-32 before they are returned. Any other method, and an encrypted entry,
is refused by name for that entry only (`zip-entry-unsupported`).

NOT implemented, deliberately, and reported rather than faked:
    * JSON Schema validation. A bootstrap loader cannot carry a validator; it
      does targeted structural checks instead. For a profile it does not have
      built in it says so in ONE `unsupported-profile` entry, checks the six
      base conventions it itself depends on, and still lists, hash-verifies
      and extracts every file (SPEC section 10.3).
    * Ed25519. SPEC section 10 step 4's four fixed state words are used
      verbatim -- signed-and-valid / absent / present-and-invalid /
      unverified -- and this reader can only ever report the last three,
      because it says plainly that it did not verify the mathematics.
    * zip64 — and by ruling it will not be: a zip64 container is refused
      WHOLE and by name (`zip64-unsupported`, exit status 2), and nothing is
      read from it. A package past the zip32 ceiling is carried in directory
      form, which is the same format.

Exit status (SPEC section 10.1): 0 the container opened; 2 container-scoped
refusal (not a zip, zip64, two zip entries with one name, no or unparseable
MANIFEST.json) — nothing loaded. With --strict, 1 when the report holds an
`error` entry: a dead node, a hash mismatch (also the one a version fallback
recovered from), an invalid signature. This reader never ends in a traceback:
a manifest it cannot interpret is a refusal with a code, not a crash.

Dependencies: the Python standard library, nothing else (`hashlib`, `struct`,
`json`, `os`, `sys`, `zlib`). Python >= 3.8.

Read-only by construction: it never writes into the package.

Usage:
    werk_read.py <pkg.werk|dir> --list
    werk_read.py <pkg> --verify [--strict]
    werk_read.py <pkg> --report
    werk_read.py <pkg> --extract <node_id> --out <dir>
    werk_read.py <pkg> --cat <package/relative/path>
    werk_read.py <pkg> --envelope <package/relative/path>
    werk_read.py <pkg> --points <package/relative/path.wkpc> [--head N]
    werk_read.py <pkg> --gsplat <package/relative/path.wkgs> [--head N]
    werk_read.py --selftest
"""

import hashlib
import json
import os
import struct
import sys
import zlib

MANIFEST = "MANIFEST.json"
SIGNATURE = "SIGNATURE.json"

CAPABILITIES = ["read-manifest", "verify-hashes", "read-envelope", "materialize",
                "summarize-points", "summarize-gsplat"]


class ContainerRefusal(Exception):
    """SPEC section 10.1's container scope: nothing can be loaded. Carries the
    stable report code, so the refusal is printed under the same name whichever
    reader makes it."""

    def __init__(self, code, message):
        Exception.__init__(self, message)
        self.code = code
        self.message = message


class EntryUnsupported(ValueError):
    """One zip entry this reader will not return bytes for: a compression
    method other than store or deflate, or encryption. `zip-entry-unsupported`."""


class EntryInvalid(ValueError):
    """One zip entry damaged at the container level: a deflate stream that does
    not decode, or bytes that disagree with the directory. `zip-entry-invalid`."""


ZIP64_REMEDY = ("this reader implements 32-bit zip only and reads nothing from a "
                "zip64 container, because the offsets it would follow are "
                "sentinels. werk does not use zip64: a package past the zip32 "
                "ceiling (4 GiB, 65534 entries) is carried in DIRECTORY form, "
                "which is the same format and has no ceiling.")

# The six conventions EVERY reader depends on to read any werk at all — the
# container, the manifest and the envelope frame — whatever the profile. A
# reader that does not have a package's profile built in still checks these
# (SPEC section 10.3); the profile's own conventions govern payload meaning it
# does not claim.
BASE_CONVENTIONS = {
    "endianness": "le",
    "alignment_bytes": 16,
    "text_encoding": "utf-8",
    "id_case": "kebab-case",
    "hash_algorithm": "sha256",
    "signature_algorithm": "ed25519",
}

# The values this reader implements, PER PROFILE. SPEC §10 step 3: check what
# is declared against what you support, and refuse rather than guess.
#
# Keyed by profile, because a convention list is profile property and not a
# reader property: profile image/1 has no handedness, no up axis and no
# quaternions, and a reader that checked profile 1's twenty-one against it
# would report fourteen missing conventions about a package that is perfectly
# well formed. (Found the first time a second profile existed; recorded as
# spec finding S-25.)
SUPPORTED_CONVENTIONS = {
    "3d-entity/1": {
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
    },
    "image/1": {
        "endianness": "le",
        "color_space_default": "srgb",
        "pixel_origin": "top-left",
        "alpha_mode": "straight",
        "alignment_bytes": 16,
        "text_encoding": "utf-8",
        "id_case": "kebab-case",
        "hash_algorithm": "sha256",
        "signature_algorithm": "ed25519",
    },
}


# ---------------------------------------------------------------------------
# Container: store-mode zip, parsed by hand from MINI-SPECS §5, or a directory.
# ---------------------------------------------------------------------------

class Container:
    """Common interface: names() and read(path). Nothing else is needed."""

    def names(self):
        raise NotImplementedError

    def read(self, path):
        """Return bytes, or raise KeyError (absent) / ValueError (unsupported)."""
        raise NotImplementedError


class DirContainer(Container):
    """SPEC §1: 'Directory and zip layouts are identical. Both are the format.'"""

    def __init__(self, root):
        self.root = root

    def names(self):
        out = []
        for dirpath, _dirnames, filenames in os.walk(self.root):
            for f in filenames:
                full = os.path.join(dirpath, f)
                rel = os.path.relpath(full, self.root).replace(os.sep, "/")
                out.append(rel)
        return sorted(out)

    def read(self, path):
        _reject_unsafe(path)
        full = os.path.join(self.root, *path.split("/"))
        if not os.path.isfile(full):
            raise KeyError(path)
        with open(full, "rb") as fh:
            return fh.read()


class ZipContainer(Container):
    """A store-mode zip reader written straight from the byte tables in
    MINI-SPECS §5.1-§5.3. No zipfile, no zlib: the point of this file is to
    show that reading a werk needs neither."""

    def __init__(self, data):
        self.data = data
        self.entries = {}
        self.order = []
        self._parse_central_directory()

    def _parse_central_directory(self):
        d = self.data
        n = len(d)
        if n < 22:
            raise ContainerRefusal("bad-container", "file is too short to be a zip")
        # Scan backwards for PK\x05\x06. The comment is the only thing that can
        # follow the EOCD, and it is at most 65535 bytes.
        limit = max(0, n - 22 - 65535)
        eocd = -1
        for i in range(n - 22, limit - 1, -1):
            if d[i:i + 4] == b"PK\x05\x06":
                comment_len = struct.unpack_from("<H", d, i + 20)[0]
                # Disambiguate a signature that merely occurs inside data: the
                # declared comment length must account for exactly the rest of
                # the file. Take the highest such offset.
                if i + 22 + comment_len == n:
                    eocd = i
                    break
        if eocd < 0:
            raise ContainerRefusal(
                "bad-container", "no end-of-central-directory record: not a zip")

        disk_count = struct.unpack_from("<H", d, eocd + 8)[0]
        count = struct.unpack_from("<H", d, eocd + 10)[0]
        cd_size = struct.unpack_from("<I", d, eocd + 12)[0]
        cd_off = struct.unpack_from("<I", d, eocd + 16)[0]
        # MINI-SPECS section 5.5, BOTH signals, either one is enough: a sentinel
        # in the EOCD, or the zip64 locator sitting immediately before it.
        sentinel = (0xFFFFFFFF in (cd_size, cd_off)
                    or 0xFFFF in (count, disk_count))
        locator = eocd >= 20 and d[eocd - 20:eocd - 16] == b"PK\x06\x07"
        if sentinel or locator:
            raise ContainerRefusal(
                "zip64-unsupported",
                "zip64 container (EOCD sentinel: %s; zip64 locator before the "
                "EOCD: %s). %s" % (str(sentinel).lower(), str(locator).lower(),
                                   ZIP64_REMEDY))

        p = cd_off
        for _ in range(count):
            if d[p:p + 4] != b"PK\x01\x02":
                raise ContainerRefusal(
                    "bad-container", "bad central directory signature at %d" % p)
            flags = struct.unpack_from("<H", d, p + 8)[0]
            method = struct.unpack_from("<H", d, p + 10)[0]
            crc = struct.unpack_from("<I", d, p + 16)[0]
            comp = struct.unpack_from("<I", d, p + 20)[0]
            uncomp = struct.unpack_from("<I", d, p + 24)[0]
            nlen = struct.unpack_from("<H", d, p + 28)[0]
            mlen = struct.unpack_from("<H", d, p + 30)[0]
            klen = struct.unpack_from("<H", d, p + 32)[0]
            lho = struct.unpack_from("<I", d, p + 42)[0]
            if p + 46 + nlen > n:
                raise ContainerRefusal(
                    "bad-container", "central directory name at %d runs past the end "
                    "of the file" % p)
            name = d[p + 46:p + 46 + nlen].decode("utf-8", "replace")
            if 0xFFFFFFFF in (comp, uncomp, lho):
                # MINI-SPECS 5.5 step 5: the per-entry sentinel.
                raise ContainerRefusal(
                    "zip64-unsupported",
                    "entry %r carries a 0xFFFFFFFF size or offset sentinel (a "
                    "zip64 entry). %s" % (name, ZIP64_REMEDY))
            if flags & 0x0008:
                raise ContainerRefusal(
                    "bad-container",
                    "entry %r sets flag bit 3 (data descriptor), which a werk "
                    "writer MUST NOT set" % name)
            if name in self.entries:
                # Which bytes ARE that file cannot be decided, and readers
                # that pick different records disagree about one package.
                raise ContainerRefusal(
                    "bad-container",
                    "the zip holds two entries named %r; which bytes are that "
                    "file cannot be decided, so the container is refused" % name)
            self.entries[name] = (method, comp, uncomp, lho, flags, crc)
            self.order.append(name)
            p += 46 + nlen + mlen + klen

    def names(self):
        return [n for n in self.order if not n.endswith("/")]

    def read(self, path):
        if path not in self.entries:
            raise KeyError(path)
        method, comp, uncomp, lho, flags, crc = self.entries[path]
        if flags & 0x0001:
            raise EntryUnsupported(
                "entry %r is encrypted; werk has no encryption and this reader "
                "returns no bytes for it" % path)
        if method not in (0, 8):
            raise EntryUnsupported(
                "entry %r uses compression method %d; this reader implements 0 "
                "(store) and 8 (deflate) and will not return wrong bytes"
                % (path, method))
        d = self.data
        if d[lho:lho + 4] != b"PK\x03\x04" or lho + 30 > len(d):
            raise EntryInvalid("bad local header signature for %r" % path)
        # The local header's name/extra lengths may differ from the central
        # directory's; MINI-SPECS §5.3 says always re-read them here.
        nlen = struct.unpack_from("<H", d, lho + 26)[0]
        mlen = struct.unpack_from("<H", d, lho + 28)[0]
        start = lho + 30 + nlen + mlen
        if start + comp > len(d):
            raise EntryInvalid("entry %r runs past the end of the file" % path)
        raw = d[start:start + comp]
        if method == 0:
            return raw
        # Method 8: a raw DEFLATE stream (MINI-SPECS section 7.1). The
        # directory's uncompressed size bounds the output, and size and CRC-32
        # are checked before a byte is handed over, so a stream that decodes to
        # the wrong thing is damage to this entry, never a wrong payload.
        try:
            z = zlib.decompressobj(-15)
            out = z.decompress(raw, uncomp + 1)
        except zlib.error as e:
            raise EntryInvalid("entry %r: deflate stream does not decode: %s"
                               % (path, e))
        if len(out) != uncomp or not z.eof:
            raise EntryInvalid(
                "entry %r does not inflate to the %d bytes the directory declares"
                % (path, uncomp))
        if (zlib.crc32(out) & 0xFFFFFFFF) != crc:
            raise EntryInvalid(
                "entry %r inflates to bytes whose CRC-32 is %08x; the directory "
                "declares %08x" % (path, zlib.crc32(out) & 0xFFFFFFFF, crc))
        return out

    def deflated(self):
        return [n for n in self.order if self.entries[n][0] == 8]


def _reject_unsafe(path):
    if path.startswith("/") or "\\" in path or ".." in path.split("/"):
        raise ValueError("refusing an unsafe package path: %r" % path)


def open_container(path):
    if os.path.isdir(path):
        return DirContainer(path), "directory"
    with open(path, "rb") as fh:
        # A zip64 container is refused from its TAIL, before the file - which
        # may be larger than memory, that being what zip64 is for - is read.
        # The EOCD and the zip64 locator are in the last 22 + 65535 + 20 bytes.
        fh.seek(0, 2)
        size = fh.tell()
        fh.seek(max(0, size - (22 + 65535 + 20)))
        tail = fh.read()
        e = tail.rfind(b"PK\x05\x06")
        if e >= 0 and len(tail) - e >= 22:
            counts = struct.unpack_from("<HHII", tail, e + 8)
            sentinel = (0xFFFF in counts[:2]) or (0xFFFFFFFF in counts[2:])
            locator = e >= 20 and tail[e - 20:e - 16] == b"PK\x06\x07"
            if sentinel or locator:
                raise ContainerRefusal(
                    "zip64-unsupported",
                    "zip64 container (EOCD sentinel: %s; zip64 locator before the "
                    "EOCD: %s). %s" % (str(sentinel).lower(), str(locator).lower(),
                                       ZIP64_REMEDY))
        fh.seek(0)
        data = fh.read()
    try:
        return ZipContainer(data), "zip"
    except (struct.error, IndexError) as e:
        raise ContainerRefusal("bad-container",
                               "the zip directory is truncated or malformed: %s" % e)


# ---------------------------------------------------------------------------
# The load
# ---------------------------------------------------------------------------

class Report:
    def __init__(self):
        self.lines = []

    def add(self, severity, code, message):
        self.lines.append((severity, code, message))

    def dump(self, out=sys.stdout):
        for sev, code, msg in self.lines:
            out.write("[%s] %s: %s\n" % (sev, code, msg))

    def errors(self):
        return sum(1 for s, _, _ in self.lines if s == "error")


class Package:
    def __init__(self, path):
        self.path = path
        self.container, self.form = open_container(path)
        self.report = Report()
        self._blobs = {}

        try:
            raw = self.container.read(MANIFEST)
        except KeyError:
            raise ContainerRefusal(
                "manifest-absent", "%s is not in %s" % (MANIFEST, path))
        except ValueError as e:
            raise ContainerRefusal(
                "manifest-unparseable", "%s cannot be read: %s" % (MANIFEST, e))
        self.manifest_bytes = raw
        try:
            self.manifest = json.loads(raw.decode("utf-8"))
        except Exception as e:  # noqa: BLE001 - a bad manifest IS fatal
            raise ContainerRefusal(
                "manifest-unparseable", "%s is not valid JSON: %s" % (MANIFEST, e))
        if not isinstance(self.manifest, dict):
            raise ContainerRefusal(
                "manifest-unparseable", "%s is not a JSON object" % MANIFEST)
        if not isinstance(self.manifest.get("nodes"), list):
            # SPEC section 12.1: no graph to walk is a structural failure of
            # the manifest itself, container-scoped. One malformed NODE is not.
            raise ContainerRefusal(
                "manifest-structurally-invalid",
                "%s has no `nodes` array: there is no graph to walk" % MANIFEST)

        self.manifest_sha256 = hashlib.sha256(raw).hexdigest()
        self.envelopes_validated = 0
        self._check_conventions()
        self._signature_state()
        self.nodes = []
        self._walk_nodes()
        self._propagate_edges()
        self._check_floating()

    # -- reading -------------------------------------------------------
    def blob(self, path):
        if path in self._blobs:
            return self._blobs[path]
        data = self.container.read(path)
        self._blobs[path] = data
        return data

    # -- checklist step 3 ----------------------------------------------
    def _check_conventions(self):
        conv = self.manifest.get("conventions")
        if not isinstance(conv, dict):
            self.report.add("error", "unsupported-convention",
                            "manifest declares no conventions block")
            return
        profile = self.manifest.get("profile", "")
        table = SUPPORTED_CONVENTIONS.get(profile)
        if table is None:
            # Not an error about the package: an admission about this reader.
            # Listing, hashing and extraction all still happen; only the
            # payload-meaning layer is off the table (S-25). What this reader
            # itself depends on — the six base conventions — it still checks
            # (SPEC section 10.3).
            own = sorted(k for k in conv if k not in BASE_CONVENTIONS)
            schema = self.manifest.get("manifest_schema")
            self.report.add(
                "warn", "unsupported-profile",
                "profile %r is not built into this reader (it has %s). The "
                "manifest names %s as the schema that validates it; this "
                "bootstrap loader carries no JSON Schema validator and did NOT "
                "validate the manifest against it. The six base conventions were "
                "checked against this reader; the profile's own %d (%s) govern "
                "payload meaning and were NOT interpreted. Every file is still "
                "listed, hash-verified and extractable"
                % (profile, ", ".join(sorted(SUPPORTED_CONVENTIONS)),
                   ("`%s`" % schema) if schema else "NO manifest_schema",
                   len(own), ", ".join(own)))
            table = BASE_CONVENTIONS
        for key, expected in table.items():
            if key not in conv:
                self.report.add("error", "unsupported-convention",
                                "`%s` is missing; this reader requires %r" % (key, expected))
            elif conv[key] != expected:
                self.report.add(
                    "error", "unsupported-convention",
                    "`%s` is %r; this reader implements only %r — refusing to guess"
                    % (key, conv[key], expected))

    # -- checklist step 4 ----------------------------------------------
    def _signature_state(self):
        try:
            raw = self.container.read(SIGNATURE)
        except ValueError as e:
            # Present, but its entry cannot be read: damage to a present
            # signature is present-and-invalid, never absent (SPEC section 6).
            self.signature = "present-and-invalid"
            self.report.add("error", "signature-invalid",
                            "SIGNATURE.json is present but cannot be read: %s" % e)
            return
        except KeyError:
            self.signature = "absent"
            self.report.add("info", "signature-absent",
                            "no SIGNATURE.json: this package is anonymous, which is a "
                            "legitimate state and not an error")
            return
        try:
            sig = json.loads(raw.decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            self.signature = "present-and-invalid"
            self.report.add("error", "signature-invalid",
                            "SIGNATURE.json is not valid JSON: %s" % e)
            return
        if not isinstance(sig, dict):
            self.signature = "present-and-invalid"
            self.report.add("error", "signature-invalid",
                            "SIGNATURE.json is not a JSON object")
            return
        declared = sig.get("manifest_sha256")
        if declared != self.manifest_sha256:
            self.signature = "present-and-invalid"
            self.report.add(
                "error", "signature-invalid",
                "manifest_sha256 is %s but MANIFEST.json hashes to %s: the manifest "
                "changed under an existing signature" % (declared, self.manifest_sha256))
            return
        # This loader does not carry an Ed25519 implementation, so it must not
        # claim the chain verifies. Say exactly what was and was not checked.
        # SPEC section 10 step 4: the state word is exactly `unverified`. A
        # tool comparing these strings is a normal thing to write, so a
        # near-synonym here would defeat the doctrine as surely as collapsing
        # two states would.
        self.signature = "unverified"
        self.report.add(
            "warn", "signature-unverified",
            "chain of %d entry/entries is present and its manifest hash matches, but "
            "this bootstrap loader does NOT implement Ed25519 and has NOT verified the "
            "signatures; use the full reader for a trust verdict"
            % (len(sig["chain"]) if isinstance(sig.get("chain"), list) else 0))

    # -- checklist steps 5, 6, 8 ---------------------------------------
    @staticmethod
    def _node_shape_error(n):
        """What a node needs for this reader to walk it at all, checked BEFORE
        it is walked: the structural minimum the reference core requires too
        (node_id and type strings, an integer `active`, a non-empty versions[]
        of objects with an integer `v` and a files[] of objects). A node that
        fails is dead, with the reason; the package is not refused and the
        reader does not crash (a bit flip turning `active` into `acthve` used
        to end in a TypeError traceback, finding N7b)."""
        def is_int(x):
            return isinstance(x, int) and not isinstance(x, bool)
        if not isinstance(n, dict):
            return "is not a JSON object"
        if not isinstance(n.get("node_id"), str):
            return "no node_id"
        if not isinstance(n.get("type"), str):
            return "no type"
        if not is_int(n.get("active")):
            return "no active"
        vs = n.get("versions")
        if not isinstance(vs, list) or not vs:
            return "no versions array"
        for v in vs:
            if not isinstance(v, dict) or not is_int(v.get("v")):
                return "a version has no v"
            fs = v.get("files")
            if not isinstance(fs, list):
                return "a version has no files[]"
            for f in fs:
                if not isinstance(f, dict):
                    return "a files[] entry is not an object"
        return None

    def _walk_nodes(self):
        for i, n in enumerate(self.manifest["nodes"]):
            bad = self._node_shape_error(n)
            if bad is not None:
                nid = n.get("node_id") if isinstance(n, dict) else None
                nid = nid if isinstance(nid, str) else "<node %d>" % i
                self.nodes.append({
                    "index": i, "node_id": nid, "type": "<malformed>",
                    "active": None, "versions": [], "edges": [], "resolved": None,
                    "status": "dead", "reason": "malformed node: %s" % bad})
                self.report.add("error", "node-dead",
                                "%s: nodes[%d]: %s; the node is dead, the package is "
                                "not" % (nid, i, bad))
                continue
            node = {
                "index": i,
                "node_id": n.get("node_id", "<node %d>" % i),
                "type": n.get("type", "<untyped>"),
                "active": n.get("active"),
                "versions": n.get("versions", []),
                "edges": [e for e in n.get("edges", []) if isinstance(e, dict)]
                         if isinstance(n.get("edges", []), list) else [],
                "resolved": None,
                "status": "ok",
                "reason": "",
            }
            self.nodes.append(node)
            if not isinstance(node["versions"], list) or not node["versions"]:
                node["status"] = "dead"
                node["reason"] = "no versions[]"
                continue

            active = node["active"]
            if not any(v.get("v") == active for v in node["versions"]):
                self.report.add("warn", "version-fallback",
                                "%s: active names v%s, which does not exist"
                                % (node["node_id"], active))

            # Resolve through versions[], never by globbing (SPEC §5).
            candidates = sorted(
                (v for v in node["versions"]
                 if isinstance(v.get("v"), int) and v["v"] <= active),
                key=lambda v: -v["v"])
            for cand in candidates:
                if "compacted" in cand:
                    self.report.add(
                        "info", "version-compacted",
                        "%s v%d was compacted: the record stays, the bytes went"
                        % (node["node_id"], cand["v"]))
                    continue
                problems = self._verify_version(node, cand)
                if not problems:
                    node["resolved"] = cand["v"]
                    if cand["v"] != active:
                        self.report.add(
                            "warn", "version-fallback",
                            "%s: active v%s is unusable, FELL BACK to v%d — %s"
                            % (node["node_id"], active, cand["v"],
                               cand.get("note", "")))
                    break
                for p in problems:
                    self.report.add(*p)
            if node["resolved"] is None:
                node["status"] = "dead"
                node["reason"] = "no usable version"
                continue

            # read-envelope, exercised: every file of the resolved version that
            # starts like an envelope has its FRAME validated, whatever its
            # magic — a profile-defined or newer envelope is checked instead of
            # silently passed over (ruling 4 of 2026-10-13). A broken frame
            # kills the node, like any other damage.
            declared = self._declared_formats(n, next(
                v for v in node["versions"] if v.get("v") == node["resolved"]))
            for f in next(v for v in node["versions"]
                          if v.get("v") == node["resolved"]).get("files", []):
                path = f.get("path", "")
                if path in declared:
                    continue       # a file DECLARED to be in a foreign format
                data = self.blob(path)
                if not is_envelope_magic(data[:4]):
                    continue
                try:
                    read_envelope(data)
                    self.envelopes_validated += 1
                except Exception as e:  # noqa: BLE001
                    node["status"] = "dead"
                    node["reason"] = "envelope-invalid"
                    self.report.add("error", "envelope-invalid",
                                    "%s: %s: %s" % (node["node_id"], path, e))
            if node["status"] == "dead":
                continue

            if not self._is_known_type(node["type"]):
                node["status"] = "skipped"
                node["reason"] = "unknown node type `%s`" % node["type"]
                self.report.add(
                    "warn", "node-skipped-unknown-type",
                    "%s: type `%s` is not one this reader interprets; its bytes are "
                    "verified and extractable, nothing else is lost (law 12)"
                    % (node["node_id"], node["type"]))

            if node["type"] == "core.loader":
                meta = n.get("meta") if isinstance(n.get("meta"), dict) else {}
                if meta.get("form") == "prebuilt":
                    self.report.add(
                        "info", "prebuilt-not-executed",
                        "%s carries a prebuilt binary; it is inert data and this reader "
                        "did NOT execute, load or link it (SPEC §7.1)" % node["node_id"])

    @staticmethod
    def _is_known_type(t):
        # A bootstrap loader interprets no payload, so "known" can only mean
        # "not a surprise": every `core.*` type is its profile's constitution,
        # whichever profile that is, and is never skipped; an `x.*` type is the
        # open frontier and is skipped and reported (law 12). All three
        # bootstrap loaders apply THIS rule — two of them used to carry a table
        # of the core types they had been told about, and the tables had
        # drifted (ruling 2 of 2026-10-13).
        return isinstance(t, str) and t.startswith("core.")

    @staticmethod
    def _declared_formats(node_raw, ver):
        """Paths of this version's files that the node DECLARES to be in a
        defined foreign format (SPEC section 3.18): `meta.payload_format` for
        the payload file, `meta.file_formats` by role. A declaration beats a
        sniff: such a file is not an envelope, whatever its first bytes are."""
        meta = node_raw.get("meta")
        meta = meta if isinstance(meta, dict) else {}
        files = [f for f in ver.get("files", []) if isinstance(f, dict)]
        out = set()
        if isinstance(meta.get("payload_format"), str):
            payload = ver.get("payload_file")
            if payload is None and len(files) == 1:
                payload = files[0].get("path")
            if payload is None:
                roled = [f.get("path") for f in files if f.get("role") == "payload"]
                payload = roled[0] if len(roled) == 1 else None
            if payload is not None:
                out.add(payload)
        roles = meta.get("file_formats")
        if isinstance(roles, dict):
            for f in files:
                if f.get("role") in roles:
                    out.add(f.get("path"))
        return out

    def _verify_version(self, node, ver):
        problems = []
        for f in ver.get("files", []):
            path = f.get("path", "")
            try:
                data = self.blob(path)
            except KeyError:
                problems.append(("error", "file-missing",
                                 "%s v%s: %s is declared in files[] but is not in the "
                                 "container" % (node["node_id"], ver.get("v"), path)))
                continue
            except EntryInvalid as e:
                problems.append(("error", "zip-entry-invalid",
                                 "%s v%s: %s" % (node["node_id"], ver.get("v"), e)))
                continue
            except ValueError as e:
                problems.append(("error", "zip-entry-unsupported",
                                 "%s v%s: %s" % (node["node_id"], ver.get("v"), e)))
                continue
            if "size" in f and len(data) != f["size"]:
                problems.append(("error", "size-mismatch",
                                 "%s v%s: %s declares %s bytes, container holds %d"
                                 % (node["node_id"], ver.get("v"), path,
                                    f["size"], len(data))))
            got = hashlib.sha256(data).hexdigest()
            if got != f.get("sha256"):
                problems.append(("error", "hash-mismatch",
                                 "%s v%s: %s declares sha256 %s, bytes hash to %s"
                                 % (node["node_id"], ver.get("v"), path,
                                    f.get("sha256"), got)))
        return problems

    def _propagate_edges(self):
        by_id = {n["node_id"]: n for n in self.nodes}
        # SPEC section 5: a `requires` edge to a node that is not in nodes[]
        # kills the source exactly as one into a dead node does. One entry
        # per such edge, also on a node already dead for another reason. The
        # node's files were already verified; only its status moves.
        for n in self.nodes:
            for e in n["edges"]:
                if e.get("kind") == "requires" and e.get("to") not in by_id:
                    if n["status"] != "dead":
                        n["status"] = "dead"
                        n["reason"] = "requires `%s`, which is not a node here" % e.get("to")
                    self.report.add(
                        "error", "requires-missing-node",
                        "%s: a `requires` edge to `%s`, which is not a node here, "
                        "kills this node as a dead target would" % (n["node_id"], e.get("to")))
        changed = True
        while changed:
            changed = False
            for n in self.nodes:
                if n["status"] == "dead":
                    continue
                for e in n["edges"]:
                    tgt = by_id.get(e.get("to"))
                    if tgt is not None and tgt["status"] == "dead" \
                            and e.get("kind") == "requires":
                        n["status"] = "dead"
                        n["reason"] = "requires dead node `%s`" % e["to"]
                        self.report.add(
                            "error", "requires-dead-node",
                            "%s: a `requires` edge into dead node `%s` kills this node too"
                            % (n["node_id"], e["to"]))
                        changed = True
        for n in self.nodes:
            for e in n["edges"]:
                tgt = by_id.get(e.get("to"))
                if tgt is None and e.get("kind") == "requires":
                    continue  # reported above as requires-missing-node
                if tgt is None:
                    self.report.add("warn", "edge-dangling",
                                    "%s: edge points at `%s`, which is not a node here"
                                    % (n["node_id"], e.get("to")))
                elif tgt["status"] == "dead" and e.get("kind") == "enhances":
                    self.report.add(
                        "warn", "enhances-dead-node",
                        "%s: an `enhances` edge into dead node `%s` costs one feature "
                        "and nothing else" % (n["node_id"], e["to"]))

    def _check_floating(self):
        declared = set()
        for n in self.nodes:
            for v in n["versions"]:
                for f in v.get("files", []):
                    declared.add(f.get("path"))
        for name in self.container.names():
            if name in (MANIFEST, SIGNATURE) or name in declared:
                continue
            self.report.add("warn", "floating-file",
                            "%s is in the container but reachable from no node version; "
                            '"nothing floats" is broken' % name)


# ---------------------------------------------------------------------------
# The binary envelope — ENVELOPE.layout.txt
# ---------------------------------------------------------------------------

# The seven RESERVED magics of ENVELOPE.layout.txt section 2 and the kind each
# binds. A CONSISTENCY CHECK, not a recogniser: an envelope is recognised by
# its frame (`is_envelope_magic`), and its grammar is found through the
# header's `kind` and the package's `layouts` map. `WKX0`..`WKX9` bind no kind
# and are shared by every profile and extension. tests/run_gate_magic.py keeps
# this table equal to the layout file's and to the other three readers'.
MAGIC_KIND = {
    b"WKFF": "core.field.flow",
    b"WKRP": "core.pose.rest",
    b"WKAC": "core.anim.clip",
    b"WKSK": "core.skeleton",
    b"WKEM": "core.embedding",
    b"WKPC": "core.geom.points",
    b"WKGS": "core.geom.gsplat",
}

_BANNED = {0xC1, 0xC7, 0xC8, 0xC9, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8}

_MAGIC_TAIL = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def is_envelope_magic(magic):
    """`W`, `K`, then two characters each an ASCII capital letter or digit."""
    return (len(magic) == 4 and magic[0:2] == b"WK"
            and magic[2] in _MAGIC_TAIL and magic[3] in _MAGIC_TAIL)


def mp_decode(buf):
    val, off = _mp_read(buf, 0)
    if off != len(buf):
        raise ValueError("%d trailing bytes after the MessagePack value" % (len(buf) - off))
    return val


def _mp_read(b, o):
    # Everything inside MessagePack is BIG-endian. Everything outside it, in
    # every payload section, is little-endian. That inversion is the single
    # most common bug in envelope readers, so it is spelled out here.
    c = b[o]
    o += 1
    if c in _BANNED:
        raise ValueError("format byte 0x%02x is banned in werk headers" % c)
    if c <= 0x7F:
        return c, o
    if c >= 0xE0:
        return c - 256, o
    if 0xA0 <= c <= 0xBF:
        n = c & 0x1F
        return b[o:o + n].decode("utf-8"), o + n
    if 0x90 <= c <= 0x9F:
        return _mp_seq(b, o, c & 0x0F, list)
    if 0x80 <= c <= 0x8F:
        return _mp_seq(b, o, c & 0x0F, dict)
    if c == 0xC0:
        return None, o
    if c == 0xC2:
        return False, o
    if c == 0xC3:
        return True, o
    fixed = {0xCC: (">B", 1), 0xCD: (">H", 2), 0xCE: (">I", 4), 0xCF: (">Q", 8),
             0xD0: (">b", 1), 0xD1: (">h", 2), 0xD2: (">i", 4), 0xD3: (">q", 8),
             0xCA: (">f", 4), 0xCB: (">d", 8)}
    if c in fixed:
        fmt, n = fixed[c]
        return struct.unpack_from(fmt, b, o)[0], o + n
    pfx = {0xD9: (">B", 1, "s"), 0xDA: (">H", 2, "s"), 0xDB: (">I", 4, "s"),
           0xC4: (">B", 1, "b"), 0xC5: (">H", 2, "b"), 0xC6: (">I", 4, "b"),
           0xDC: (">H", 2, "a"), 0xDD: (">I", 4, "a"),
           0xDE: (">H", 2, "m"), 0xDF: (">I", 4, "m")}
    if c in pfx:
        fmt, n, kind = pfx[c]
        ln = struct.unpack_from(fmt, b, o)[0]
        o += n
        if kind == "s":
            return b[o:o + ln].decode("utf-8"), o + ln
        if kind == "b":
            return bytes(b[o:o + ln]), o + ln
        return _mp_seq(b, o, ln, list if kind == "a" else dict)
    raise ValueError("unknown MessagePack format byte 0x%02x" % c)


def _mp_seq(b, o, n, kind):
    if kind is list:
        out = []
        for _ in range(n):
            v, o = _mp_read(b, o)
            out.append(v)
        return out, o
    out = {}
    for _ in range(n):
        k, o = _mp_read(b, o)
        v, o = _mp_read(b, o)
        if not isinstance(k, str):
            raise ValueError("werk header map keys must be strings")
        out[k] = v
    return out, o


def align16(n):
    return (n + 15) // 16 * 16


def read_envelope(data):
    """Every assertion in ENVELOPE.layout.txt §7. Any failure means the node is
    dead: report which assertion, skip the node, load the rest."""
    if len(data) < 16:
        raise ValueError("file is %d bytes; the smallest legal envelope is 16" % len(data))
    magic = bytes(data[0:4])
    if not is_envelope_magic(magic):
        raise ValueError("%r is not an envelope magic (`WK` and two of A-Z or 0-9)"
                         % magic)
    version, header_len = struct.unpack_from("<II", data, 4)
    if 12 + header_len > len(data):
        raise ValueError("header_len %d runs past the end of a %d-byte file"
                         % (header_len, len(data)))
    header = mp_decode(data[12:12 + header_len])
    if header.get("endianness") != "le":
        raise ValueError("header declares endianness %r; werk payloads are always 'le'"
                         % header.get("endianness"))
    expected_kind = MAGIC_KIND.get(magic)
    if expected_kind and header.get("kind") != expected_kind:
        raise ValueError("magic %s implies kind %r but the header says %r"
                         % (magic.decode(), expected_kind, header.get("kind")))
    computed = align16(12 + header_len)
    if header.get("payload_origin") != computed:
        raise ValueError("declared payload_origin %r != computed %d"
                         % (header.get("payload_origin"), computed))
    if computed + header.get("payload_size", -1) != len(data):
        raise ValueError("payload_origin + payload_size != file size %d" % len(data))
    prev_end = computed
    for s in header.get("sections", []):
        off, size = s["offset"], s["size"]
        if off % 16:
            raise ValueError("section %r offset %d is not 16-byte aligned" % (s["name"], off))
        if off < prev_end or off - prev_end > 15:
            raise ValueError("section %r at %d does not follow the previous section "
                             "with only alignment padding" % (s["name"], off))
        if off + size > len(data):
            raise ValueError("section %r runs past the end of the file" % s["name"])
        prev_end = off + size
    if header.get("sections"):
        last = header["sections"][-1]
        if align16(last["offset"] + last["size"]) != computed + header["payload_size"]:
            raise ValueError("the last section does not end where payload_size says it does")
    return magic, version, header


# ---------------------------------------------------------------------------
# Stage 12: summary decode of the two geometry envelopes
#
# `read_envelope` above proves the FRAME is sound. These two functions go one
# step further and interpret the bytes, from the offsets, sizes, dtypes and
# strides the header DECLARES -- never from a struct layout in this file, which
# is the point of a declared section table and the reason a reader written from
# spec/layouts/*.layout.txt agrees with a writer it has never met.
#
# They exist because Python is this format's demo face. A stranger handed a
# .werk and told it contains a Gaussian splat wants two answers immediately --
# where are the points, and what colour are they -- and a reader that can only
# say "the envelope is well formed" makes them write code before they can look.
# ---------------------------------------------------------------------------

#: The degree-0 spherical-harmonic basis constant, 1/(2*sqrt(pi)).
#: spec/layouts/gsplat.layout.txt section 5 defines the whole colour line.
SH_C0 = 0.28209479177387814

_STRUCT_OF = {"u8": "B", "i8": "b", "u16": "<H", "i16": "<h", "u32": "<I",
              "i32": "<i", "u64": "<Q", "i64": "<q", "f32": "<f", "f64": "<d"}
_SIZE_OF = {"u8": 1, "i8": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4,
            "u64": 8, "i64": 8, "f32": 4, "f64": 8}


def _section(header, name):
    for s in header.get("sections", []):
        if s["name"] == name:
            return s
    return None


def read_section(data, sec, first=None):
    """Decode a payload section into a list of rows, using ONLY the declared
    dtype, shape, stride and offset. `first` limits how many rows are decoded,
    because a 281 498-row section does not need to be materialised to be
    summarised."""
    dtype, shape, stride = sec["dtype"], list(sec["shape"]), sec["stride"]
    esz = _SIZE_OF.get(dtype)
    if esz is None:
        raise ValueError("section %r has dtype %r, which this reader does not "
                         "interpret" % (sec["name"], dtype))
    comps = 1 if stride == esz else (shape[-1] if shape else 1)
    rows = shape[0] if shape else 0
    if first is not None:
        rows = min(rows, first)
    fmt = _STRUCT_OF[dtype]
    out = []
    for i in range(rows):
        base = sec["offset"] + i * stride
        vals = [struct.unpack_from(fmt, data, base + c * esz)[0]
                for c in range(comps)]
        out.append(vals[0] if comps == 1 else vals)
    return out


def _fmt3(v):
    return "(" + ", ".join("%.6f" % float(x) for x in v) + ")"


def cmd_points(data, head=5):
    """Summarise a WKPC payload: spec/layouts/points.layout.txt."""
    magic, version, header = read_envelope(data)
    if magic != b"WKPC":
        raise SystemExit("%s is not a WKPC point cloud" % magic.decode())
    count = header["count"]
    print("magic        : WKPC (core.geom.points), grammar version %d" % version)
    print("count        : %d points" % count)
    print("length_unit  : %s" % header.get("length_unit"))
    print("fields       :")
    for f in header.get("fields", []):
        extra = []
        for k in ("unit", "color_space", "value_range"):
            if k in f:
                extra.append("%s=%s" % (k, f[k]))
        print("  %-14s semantic %-14s %s x%d  %s"
              % (f["name"], f["semantic"], f["dtype"], f["components"],
                 " ".join(extra)))
    if "bounds" in header:
        print("bounds (hint): min %s" % _fmt3(header["bounds"]["min"]))
        print("               max %s" % _fmt3(header["bounds"]["max"]))
    pos = _section(header, "position")
    if pos is None or not count:
        print("")
        print("(no position section, or an empty cloud)")
        return 0
    rows = read_section(data, pos, first=min(count, head))
    print("")
    print("first %d position(s):" % len(rows))
    for i, r in enumerate(rows):
        print("  [%d] %s" % (i, _fmt3(r)))
    colsec = _section(header, "color")
    if colsec is not None:
        crows = read_section(data, colsec, first=min(count, head))
        cf = next((f for f in header["fields"] if f["name"] == "color"), {})
        print("first %d colour(s) (%s):" % (len(crows), cf.get("color_space", "?")))
        for i, c in enumerate(crows):
            print("  [%d] %s" % (i, c))
    return 0


def cmd_gsplat(data, head=5):
    """Summarise a WKGS payload: spec/layouts/gsplat.layout.txt.

    Including the DEGRADATION PATH of that file's section 7, executed rather
    than described: positions come from `means` and colours from `sh-dc`, and
    the other four sections are skipped without being parsed. A reader that
    does exactly this is a conformant consumer of the node, not a degraded
    one."""
    magic, version, header = read_envelope(data)
    if magic != b"WKGS":
        raise SystemExit("%s is not a WKGS Gaussian splat" % magic.decode())
    count = header["count"]
    print("magic        : WKGS (core.geom.gsplat), grammar version %d" % version)
    print("count        : %d Gaussians" % count)
    print("sh_degree    : %d  (%d coefficient(s), %s)"
          % (header["sh_degree"], header["sh_coeff_count"],
             header.get("sh_coeff_order")))
    print("quat_order   : %s" % header.get("quat_order"))
    print("scale_space  : %s   opacity_space: %s"
          % (header.get("scale_space"), header.get("opacity_space")))
    print("length_unit  : %s" % header.get("length_unit"))
    if "source_convention" in header:
        print("ingested from: %s  activation %s"
              % (header["source_convention"], header.get("activation")))
    if "bounds" in header:
        print("bounds (hint): min %s" % _fmt3(header["bounds"]["min"]))
        print("               max %s" % _fmt3(header["bounds"]["max"]))
    print("sections     :")
    for sec in header.get("sections", []):
        print("  %-11s offset %-9d size %-11d %s shape %s stride %d"
              % (sec["name"], sec["offset"], sec["size"], sec["dtype"],
                 sec["shape"], sec["stride"]))
    if not count:
        return 0

    means = _section(header, "means")
    dc = _section(header, "sh-dc")
    if means is None or dc is None:
        raise SystemExit("a WKGS must carry both `means` and `sh-dc`")
    n = min(count, head)
    mrows = read_section(data, means, first=n)
    drows = read_section(data, dc, first=n)
    print("")
    print("THE TWO-SECTION PATH (gsplat.layout.txt section 7): position from "
          "`means`, colour")
    print("from `sh-dc` through clamp(0.5 + %.17g*dc, 0, 1). The other four "
          "sections were" % SH_C0)
    print("skipped without being parsed.")
    print("")
    print("  %-3s %-34s %s" % ("i", "position (m)", "linear rgb"))
    for i in range(n):
        rgb = [min(1.0, max(0.0, 0.5 + SH_C0 * c)) for c in drows[i]]
        print("  %-3d %-34s (%.4f, %.4f, %.4f)"
              % (i, _fmt3(mrows[i]), rgb[0], rgb[1], rgb[2]))
    for name in ("scales", "rotations", "opacities"):
        sec = _section(header, name)
        if sec is None:
            continue
        rows = read_section(data, sec, first=n)
        print("")
        print("%s (first %d):" % (name, n))
        for i, r in enumerate(rows):
            if isinstance(r, list):
                print("  [%d] (%s)" % (i, ", ".join("%.6f" % v for v in r)))
            else:
                print("  [%d] %.6f" % (i, r))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_list(pkg):
    print("entity    : %s" % pkg.manifest.get("entity", {}).get("name", "?"))
    print("profile   : %s" % pkg.manifest.get("profile", "?"))
    print("container : %s (declared: %s)"
          % (pkg.form, pkg.manifest.get("container", {}).get("form", "?")))
    print("manifest  : sha256 %s" % pkg.manifest_sha256)
    print("signature : %s" % pkg.signature)
    print()
    print("%-16s %-24s %-7s %-9s %s"
          % ("node_id", "type", "active", "resolved", "status"))
    for n in pkg.nodes:
        print("%-16s %-24s %-7s %-9s %s%s"
              % (n["node_id"], n["type"], n["active"],
                 ("v%d" % n["resolved"]) if n["resolved"] else "-",
                 n["status"], (": " + n["reason"]) if n["reason"] else ""))
    live = sum(1 for n in pkg.nodes if n["status"] == "ok")
    dead = sum(1 for n in pkg.nodes if n["status"] == "dead")
    skip = sum(1 for n in pkg.nodes if n["status"] == "skipped")
    print("\n%d nodes: %d live, %d dead, %d skipped for unknown type"
          % (len(pkg.nodes), live, dead, skip))
    print("%d envelope frame(s) validated" % pkg.envelopes_validated)


def cmd_verify(pkg):
    total = ok = 0
    for n in pkg.nodes:
        if n["resolved"] is None:
            continue
        ver = next(v for v in n["versions"] if v["v"] == n["resolved"])
        for f in ver.get("files", []):
            total += 1
            try:
                data = pkg.blob(f["path"])
            except Exception as e:  # noqa: BLE001
                print("FAIL %s (%s)" % (f["path"], e))
                continue
            got = hashlib.sha256(data).hexdigest()
            if got == f.get("sha256") and len(data) == f.get("size", len(data)):
                ok += 1
                print("PASS %s  %d bytes" % (f["path"], len(data)))
            else:
                print("FAIL %s  declared %s/%s got %s/%d"
                      % (f["path"], f.get("sha256"), f.get("size"), got, len(data)))
    print("\n%d/%d files verified over %d resolved node(s)"
          % (ok, total, sum(1 for n in pkg.nodes if n["resolved"])))
    return ok == total


def cmd_extract(pkg, node_id, out_dir):
    node = next((n for n in pkg.nodes if n["node_id"] == node_id), None)
    if node is None:
        raise SystemExit("no node %r" % node_id)
    if node["resolved"] is None:
        raise SystemExit("node %r has no usable version" % node_id)
    ver = next(v for v in node["versions"] if v["v"] == node["resolved"])
    for f in ver["files"]:
        _reject_unsafe(f["path"])
        target = os.path.join(out_dir, *f["path"].split("/"))
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        with open(target, "wb") as fh:
            fh.write(pkg.blob(f["path"]))
        print("wrote %s" % target)


def selftest():
    vectors = [
        (b"", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
        (b"abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"),
        (b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq",
         "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"),
    ]
    bad = 0
    for data, want in vectors:
        got = hashlib.sha256(data).hexdigest()
        status = "OK " if got == want else "FAIL"
        if got != want:
            bad += 1
        print("%s sha256(%d bytes) -> %s" % (status, len(data), got))
    # The worked MessagePack example from ENVELOPE.layout.txt §4.4, with its
    # arithmetic corrected: that section prints `af` (fixstr length 15) before
    # the 14-byte string "core.pose.rest" and then states header_len = 34 and
    # 2 padding bytes. The correct lead byte is `ae`, the header is 35 bytes and
    # the padding is 1; payload_origin is 48 either way, which is why the slip
    # survives a read-through. Only the illustration is affected — the real
    # WKRP example file is written by an encoder and is correct.
    sample = b"\x82\xaaendianness\xa2le\xa4kind\xaecore.pose.rest"
    got = mp_decode(sample)
    want = {"endianness": "le", "kind": "core.pose.rest"}
    if got == want and len(sample) == 35 and align16(12 + len(sample)) == 48:
        print("OK  messagepack worked example decodes (header_len 35, origin 48)")
    else:
        bad += 1
        print("FAIL messagepack worked example: %r" % (got,))
    print("selftest: %s" % ("OK" if bad == 0 else "FAILED"))
    return bad == 0


def main(argv):
    try:
        return _main(argv)
    except ContainerRefusal as e:
        sys.stderr.write("[error] %s: %s\n" % (e.code, e.message))
        sys.stderr.write("container-scoped refusal: nothing was loaded; "
                         "exit status 2\n")
        return 2
    except Exception as e:  # noqa: BLE001
        # The last line of SPEC section 10.1: what this reader failed to
        # interpret is reported under a code with exit status 2, never as a
        # Python traceback (whose status 1 would be indistinguishable from "a
        # node is dead").
        sys.stderr.write("[error] manifest-structurally-invalid: this reader could "
                         "not interpret the package (%s: %s)\n"
                         % (type(e).__name__, e))
        sys.stderr.write("container-scoped refusal: nothing was loaded; "
                         "exit status 2\n")
        return 2


def _main(argv):
    if "--selftest" in argv:
        return 0 if selftest() else 1
    if len(argv) < 2:
        print(__doc__.strip())
        return 2
    path = argv[1]
    flags = argv[2:]
    try:
        pkg = Package(path)
    except ContainerRefusal as e:
        # SPEC section 10.1: the one scope that comes back empty-handed. One
        # line, under the stable code, and exit status 2.
        sys.stderr.write("[error] %s: %s\n" % (e.code, e.message))
        sys.stderr.write("container-scoped refusal: nothing was loaded; "
                         "exit status 2\n")
        return 2
    except OSError as e:
        sys.stderr.write("[error] not-found: %s\n" % e)
        return 2
    strict = "--strict" in flags

    if "--cat" in flags:
        target = flags[flags.index("--cat") + 1]
        _reject_unsafe(target)
        out = getattr(sys.stdout, "buffer", sys.stdout)
        out.write(pkg.blob(target))
        return 0
    if "--envelope" in flags:
        target = flags[flags.index("--envelope") + 1]
        magic, version, header = read_envelope(pkg.blob(target))
        print("magic          : %s" % magic.decode())
        print("version        : %d" % version)
        print("payload_origin : %d" % header["payload_origin"])
        print("payload_size   : %d" % header["payload_size"])
        for s in header["sections"]:
            print("section %-10s offset %-6d size %-6d dtype %-7s stride %-4d shape %s"
                  % (s["name"], s["offset"], s["size"], s["dtype"], s["stride"], s["shape"]))
        print("\nheader:")
        print(json.dumps(header, indent=2, sort_keys=True, default=str))
        return 0
    if "--points" in flags or "--gsplat" in flags:
        which = "--points" if "--points" in flags else "--gsplat"
        target = flags[flags.index(which) + 1]
        _reject_unsafe(target)
        head = int(flags[flags.index("--head") + 1]) if "--head" in flags else 5
        blob = pkg.blob(target)
        return (cmd_points if which == "--points" else cmd_gsplat)(blob, head)
    if "--extract" in flags:
        node_id = flags[flags.index("--extract") + 1]
        out_dir = flags[flags.index("--out") + 1] if "--out" in flags else "."
        cmd_extract(pkg, node_id, out_dir)
        return 0

    # --strict: 1 when the report holds an `error` entry (SPEC section 10.1's
    # status 1), which includes the hash mismatch a version fallback recovered
    # from: the node is alive, the damage is still damage. Warnings are not
    # promoted.
    def strict_status(good=True):
        bad = (not good or pkg.report.errors() > 0
               or any(n["status"] == "dead" for n in pkg.nodes))
        return 1 if (strict and bad) else 0

    if "--verify" in flags:
        good = cmd_verify(pkg)
        print()
        pkg.report.dump()
        return strict_status(good)
    if "--report" in flags:
        pkg.report.dump()
        print("%d report entries, %d error(s)" % (len(pkg.report.lines), pkg.report.errors()))
        return strict_status()

    cmd_list(pkg)
    return strict_status()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
