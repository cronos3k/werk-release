"""werk — Python binding for werk-core, over the C ABI, with zero pip deps.

This is a THIN binding, not a second implementation. Every byte-level decision
— zip framing, hashing, schema validation, Ed25519, version resolution — lives
in the one shared library that C and C++ also use, so the three faces cannot
disagree. If you want a from-scratch Python reader instead, that is
`loaders/werk_read.py`, which ships inside packages and deliberately shares no
code with this.

Requirements: CPython >= 3.8 and the standard library. Nothing else.

Finding the library, in order:
  1. the `path` argument to `load_library()`
  2. $WERK_DLL
  3. beside this file
  4. ../../core/target/{release,debug}/  (a development checkout)

    >>> import werk
    >>> pkg = werk.Package.open("tests/fixtures/crate.werk")
    >>> pkg.entity_name
    'Wooden crate (conformance fixture)'
    >>> pkg.signature_state
    'signed-and-valid'
    >>> [n.node_id for n in pkg.nodes if n.status != 'alive']
    ['x-probe']
    >>> len(pkg.blob("poses/rest.wkrp"))
    560

Damage never raises. A corrupt node is a report entry and a node whose
`status` is `dead`; the rest of the package loads. That is the island rule, and
this binding does not paper over it with an exception.
"""

from __future__ import annotations

import ctypes
import json
import os
import sys
from ctypes import (POINTER, c_char_p, c_int32, c_size_t, c_uint8, c_uint32,
                    c_uint64, c_void_p)

__all__ = ["Package", "Node", "Version", "FileRef", "ReportEntry", "WerkError",
           "load_library", "OPEN_DEFAULT", "OPEN_SKIP_VERIFY",
           "OPEN_SKIP_INTERPRET", "OPEN_SKIP_DERIVED"]

OPEN_DEFAULT = 0
OPEN_SKIP_VERIFY = 1 << 0
OPEN_SKIP_INTERPRET = 1 << 1
OPEN_SKIP_DERIVED = 1 << 2

_STATUS = {
    0: "ok", -1: "not-found", -2: "io", -3: "bad-container", -4: "bad-manifest",
    -5: "no-such-item", -6: "bad-key", -7: "write", -8: "rejected",
    -10: "zip64-unsupported", -11: "zip-entry-unsupported", -12: "zip-entry-invalid",
    -9: "bad-argument",
}
_NODE_STATUS = {0: "alive", 1: "skipped", 2: "dead"}
_SIG_STATE = {0: "absent", 1: "signed-and-valid", 2: "present-and-invalid",
              3: "unverified"}


class WerkError(Exception):
    """Raised only when there is no package to speak of, or when a call was
    refused. Never raised for damage inside a package."""

    def __init__(self, status, detail=""):
        self.status = status
        self.code = _STATUS.get(status, "unknown")
        super().__init__("%s: %s" % (self.code, detail or "(no detail)"))


# ---------------------------------------------------------------------------
# Library loading
# ---------------------------------------------------------------------------

def _candidates():
    env = os.environ.get("WERK_DLL")
    if env:
        yield env
    here = os.path.dirname(os.path.abspath(__file__))
    if sys.platform == "win32":
        names = ["werk.dll"]
    elif sys.platform == "darwin":
        names = ["libwerk.dylib"]
    else:
        names = ["libwerk.so"]
    for n in names:
        yield os.path.join(here, n)
    root = os.path.abspath(os.path.join(here, "..", ".."))
    for profile in ("release", "debug"):
        for n in names:
            yield os.path.join(root, "core", "target", profile, n)


_LIB = None


def load_library(path=None):
    """Load (once) and configure the shared library. Returns the ctypes CDLL."""
    global _LIB
    if _LIB is not None and path is None:
        return _LIB
    tried = []
    for cand in ([path] if path else list(_candidates())):
        if cand and os.path.isfile(cand):
            lib = ctypes.CDLL(cand)
            _configure(lib)
            _LIB = lib
            return lib
        tried.append(cand)
    raise WerkError(-1, "no werk shared library found; tried: %s. Build it with "
                        "`cargo build --release` in core/, or set $WERK_DLL."
                        % ", ".join(str(t) for t in tried))


def _configure(lib):
    def sig(name, restype, *argtypes):
        fn = getattr(lib, name)
        fn.restype = restype
        fn.argtypes = list(argtypes)
        return fn

    sig("werk_version", c_char_p)
    sig("werk_profile", c_char_p)
    sig("werk_last_error", c_char_p)
    sig("werk_open", c_int32, c_char_p, c_uint32, POINTER(c_void_p))
    sig("werk_close", None, c_void_p)

    for n in ("werk_entity_name", "werk_entity_uuid", "werk_package_profile",
              "werk_manifest_sha256", "werk_signature_detail"):
        sig(n, c_char_p, c_void_p)
    sig("werk_manifest_bytes", POINTER(c_uint8), c_void_p, POINTER(c_size_t))
    sig("werk_signature_state", c_int32, c_void_p)

    sig("werk_report_count", c_int32, c_void_p)
    sig("werk_report_errors", c_int32, c_void_p)
    sig("werk_report_version", c_int32, c_void_p, c_int32)
    for n in ("werk_report_severity", "werk_report_code", "werk_report_node",
              "werk_report_path", "werk_report_message"):
        sig(n, c_char_p, c_void_p, c_int32)

    sig("werk_node_count", c_int32, c_void_p)
    sig("werk_node_index", c_int32, c_void_p, c_char_p)
    for n in ("werk_node_id", "werk_node_type", "werk_node_status_reason"):
        sig(n, c_char_p, c_void_p, c_int32)
    for n in ("werk_node_status", "werk_node_active", "werk_node_resolved",
              "werk_version_count"):
        sig(n, c_int32, c_void_p, c_int32)

    sig("werk_version_number", c_int32, c_void_p, c_int32, c_int32)
    for n in ("werk_version_note", "werk_version_epistemic",
              "werk_version_created", "werk_version_input_hash"):
        sig(n, c_char_p, c_void_p, c_int32, c_int32)
    sig("werk_file_count", c_int32, c_void_p, c_int32, c_int32)
    for n in ("werk_file_path", "werk_file_sha256", "werk_file_role",
              "werk_file_media_type"):
        sig(n, c_char_p, c_void_p, c_int32, c_int32, c_int32)
    sig("werk_file_size", c_uint64, c_void_p, c_int32, c_int32, c_int32)

    sig("werk_blob", c_int32, c_void_p, c_char_p, POINTER(POINTER(c_uint8)),
        POINTER(c_size_t))
    sig("werk_verify", c_int32, c_void_p)
    sig("werk_write_zip", c_int32, c_void_p, c_char_p)
    sig("werk_materialize_dir", c_int32, c_void_p, c_char_p)
    sig("werk_sign", c_int32, c_void_p, c_char_p, c_char_p, c_char_p, c_char_p,
        c_char_p, c_char_p, c_char_p)
    sig("werk_strip_signature", c_int32, c_void_p)
    sig("werk_stage_file", c_int32, c_void_p, c_char_p, POINTER(c_uint8), c_size_t)
    sig("werk_add_node", c_int32, c_void_p, c_char_p)
    sig("werk_append_version", c_int32, c_void_p, c_char_p, c_char_p)


def _s(raw):
    return raw.decode("utf-8", "replace") if raw else ""


def _b(text):
    return (text or "").encode("utf-8")


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------

class FileRef:
    __slots__ = ("path", "sha256", "size", "role", "media_type")

    def __init__(self, path, sha256, size, role, media_type):
        self.path, self.sha256, self.size = path, sha256, size
        self.role, self.media_type = role or None, media_type or None

    def __repr__(self):
        return "FileRef(%r, %d bytes)" % (self.path, self.size)


class Version:
    __slots__ = ("v", "note", "epistemic", "created", "input_hash", "files")

    def __init__(self, v, note, epistemic, created, input_hash, files):
        self.v, self.note, self.epistemic = v, note, epistemic
        self.created, self.input_hash, self.files = created, input_hash or None, files

    def __repr__(self):
        return "Version(v=%d, %s, %d file(s))" % (self.v, self.epistemic, len(self.files))


class Node:
    __slots__ = ("node_id", "type", "status", "status_reason", "active",
                 "resolved", "versions")

    def __init__(self, node_id, type_, status, reason, active, resolved, versions):
        self.node_id, self.type, self.status = node_id, type_, status
        self.status_reason, self.active, self.resolved = reason, active, resolved
        self.versions = versions

    @property
    def resolved_version(self):
        """The Version actually usable after any reported fallback, or None."""
        if self.resolved is None:
            return None
        return next((v for v in self.versions if v.v == self.resolved), None)

    def __repr__(self):
        return "Node(%r, %s, %s)" % (self.node_id, self.type, self.status)


class ReportEntry:
    __slots__ = ("severity", "code", "node_id", "version", "path", "message")

    def __init__(self, severity, code, node_id, version, path, message):
        self.severity, self.code = severity, code
        self.node_id, self.version = node_id or None, version
        self.path, self.message = path or None, message

    def __str__(self):
        bits = ["[%s] %s" % (self.severity, self.code)]
        if self.node_id:
            bits.append("node=%s" % self.node_id)
        if self.version is not None:
            bits.append("v=%d" % self.version)
        if self.path:
            bits.append("path=%s" % self.path)
        return " ".join(bits) + ": " + self.message

    __repr__ = __str__


# ---------------------------------------------------------------------------
# Package
# ---------------------------------------------------------------------------

class Package:
    """An open werk package. Use as a context manager, or call close()."""

    def __init__(self, handle, lib, origin):
        self._h = handle
        self._lib = lib
        self.origin = origin

    # -- lifecycle ------------------------------------------------------
    @classmethod
    def open(cls, path, flags=OPEN_DEFAULT, library=None):
        lib = load_library(library)
        h = c_void_p()
        rc = lib.werk_open(_b(str(path)), c_uint32(flags), ctypes.byref(h))
        if rc != 0:
            raise WerkError(rc, _s(lib.werk_last_error()))
        return cls(h, lib, str(path))

    def close(self):
        if self._h:
            self._lib.werk_close(self._h)
            self._h = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def __del__(self):
        try:
            self.close()
        except Exception:  # noqa: BLE001 - interpreter teardown
            pass

    def _check(self, rc):
        if rc < 0:
            raise WerkError(rc, _s(self._lib.werk_last_error()))
        return rc

    # -- facts ----------------------------------------------------------
    @property
    def entity_name(self):
        return _s(self._lib.werk_entity_name(self._h))

    @property
    def entity_uuid(self):
        return _s(self._lib.werk_entity_uuid(self._h))

    @property
    def profile(self):
        return _s(self._lib.werk_package_profile(self._h))

    @property
    def manifest_sha256(self):
        return _s(self._lib.werk_manifest_sha256(self._h))

    @property
    def manifest_bytes(self):
        n = c_size_t(0)
        p = self._lib.werk_manifest_bytes(self._h, ctypes.byref(n))
        if not p:
            return b""
        return bytes(ctypes.cast(p, POINTER(c_uint8 * n.value)).contents)

    @property
    def manifest(self):
        """MANIFEST.json parsed. The BYTES are the authority for hashing; this
        is a convenience for reading."""
        return json.loads(self.manifest_bytes.decode("utf-8"))

    @property
    def signature_state(self):
        """'absent' | 'signed-and-valid' | 'present-and-invalid' | 'unverified'
        (a chain in an algorithm the library does not implement). Three states,
        never two — collapsing the last two would defeat the doctrine."""
        return _SIG_STATE.get(self._lib.werk_signature_state(self._h), "unknown")

    @property
    def signature_detail(self):
        return _s(self._lib.werk_signature_detail(self._h))

    # -- graph ----------------------------------------------------------
    @property
    def nodes(self):
        lib, h = self._lib, self._h
        out = []
        for n in range(lib.werk_node_count(h)):
            versions = []
            for v in range(lib.werk_version_count(h, n)):
                files = [
                    FileRef(_s(lib.werk_file_path(h, n, v, f)),
                            _s(lib.werk_file_sha256(h, n, v, f)),
                            int(lib.werk_file_size(h, n, v, f)),
                            _s(lib.werk_file_role(h, n, v, f)),
                            _s(lib.werk_file_media_type(h, n, v, f)))
                    for f in range(lib.werk_file_count(h, n, v))
                ]
                versions.append(Version(
                    lib.werk_version_number(h, n, v),
                    _s(lib.werk_version_note(h, n, v)),
                    _s(lib.werk_version_epistemic(h, n, v)),
                    _s(lib.werk_version_created(h, n, v)),
                    _s(lib.werk_version_input_hash(h, n, v)),
                    files))
            resolved = lib.werk_node_resolved(h, n)
            out.append(Node(
                _s(lib.werk_node_id(h, n)),
                _s(lib.werk_node_type(h, n)),
                _NODE_STATUS.get(lib.werk_node_status(h, n), "unknown"),
                _s(lib.werk_node_status_reason(h, n)),
                lib.werk_node_active(h, n),
                None if resolved < 0 else resolved,
                versions))
        return out

    def node(self, node_id):
        i = self._lib.werk_node_index(self._h, _b(node_id))
        if i < 0:
            raise WerkError(-5, "no node %r" % node_id)
        return self.nodes[i]

    @property
    def report(self):
        lib, h = self._lib, self._h
        out = []
        for i in range(lib.werk_report_count(h)):
            ver = lib.werk_report_version(h, i)
            out.append(ReportEntry(
                _s(lib.werk_report_severity(h, i)),
                _s(lib.werk_report_code(h, i)),
                _s(lib.werk_report_node(h, i)),
                None if ver < 0 else ver,
                _s(lib.werk_report_path(h, i)),
                _s(lib.werk_report_message(h, i))))
        return out

    @property
    def errors(self):
        """Count of ERROR-severity report entries. 0 means everything the
        package claims about itself holds."""
        return self._lib.werk_report_errors(self._h)

    # -- bytes ----------------------------------------------------------
    def blob(self, path):
        data = POINTER(c_uint8)()
        n = c_size_t(0)
        self._check(self._lib.werk_blob(self._h, _b(path), ctypes.byref(data),
                                        ctypes.byref(n)))
        if n.value == 0:
            return b""
        return bytes(ctypes.cast(data, POINTER(c_uint8 * n.value)).contents)

    def extract(self, node_id, out_dir):
        """Write a node's resolved-version files under out_dir. Returns paths."""
        node = self.node(node_id)
        ver = node.resolved_version
        if ver is None:
            raise WerkError(-5, "node %r has no usable version" % node_id)
        written = []
        for f in ver.files:
            target = os.path.join(out_dir, *f.path.split("/"))
            os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
            with open(target, "wb") as fh:
                fh.write(self.blob(f.path))
            written.append(target)
        return written

    # -- write ----------------------------------------------------------
    def verify(self):
        return self._lib.werk_verify(self._h)

    def write_zip(self, dest):
        self._check(self._lib.werk_write_zip(self._h, _b(str(dest))))
        return dest

    def materialize_dir(self, dest):
        return self._check(self._lib.werk_materialize_dir(self._h, _b(str(dest))))

    # -- custody --------------------------------------------------------
    def sign(self, secret_key_hex, name, uri, kind="human", role="", note="",
             signed_at=None):
        if signed_at is None:
            import datetime
            signed_at = datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ")
        self._check(self._lib.werk_sign(
            self._h, _b(secret_key_hex), _b(name), _b(uri), _b(kind), _b(role),
            _b(note), _b(signed_at)))
        return self.signature_state

    def strip_signature(self):
        self._check(self._lib.werk_strip_signature(self._h))
        return self.signature_state

    # -- mutation -------------------------------------------------------
    def stage_file(self, path, data):
        buf = (c_uint8 * len(data)).from_buffer_copy(data) if data else None
        ptr = ctypes.cast(buf, POINTER(c_uint8)) if data else None
        self._check(self._lib.werk_stage_file(self._h, _b(path), ptr, c_size_t(len(data))))

    def add_node(self, spec):
        """spec is the dict documented in include/werk.h. Stage the payload
        bytes with stage_file() first; sha256 and size are computed for you."""
        self._check(self._lib.werk_add_node(self._h, _b(json.dumps(spec))))

    def append_version(self, node_id, spec):
        """Returns the new version number. `active` moves to it."""
        return self._check(
            self._lib.werk_append_version(self._h, _b(node_id), _b(json.dumps(spec))))

    def __repr__(self):
        return "<werk.Package %r: %d nodes, signature %s>" % (
            self.entity_name, self._lib.werk_node_count(self._h), self.signature_state)


def library_version():
    lib = load_library()
    return _s(lib.werk_version())


def _main(argv):
    if len(argv) < 2:
        print(__doc__.strip())
        return 2
    with Package.open(argv[1]) as p:
        print("library    : werk-core %s" % library_version())
        print("entity     : %s (%s)" % (p.entity_name, p.entity_uuid))
        print("profile    : %s" % p.profile)
        print("manifest   : sha256 %s" % p.manifest_sha256)
        print("signature  : %s" % p.signature_state)
        print()
        for n in p.nodes:
            print("  %-16s %-24s active=%s resolved=%s %s"
                  % (n.node_id, n.type, n.active,
                     n.resolved if n.resolved is not None else "-", n.status))
        print()
        for e in p.report:
            print(e)
        print("\n%d report entries, %d error(s)" % (len(p.report), p.errors))
        return 1 if p.errors else 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
