#!/usr/bin/env python3
"""run_gate_reference.py -- GATE REFERENCE: the reference agrees with itself.

    python tests/run_gate_reference.py

Every clause here exists because the statement it checks was once false in
this repository and nothing noticed. Each was found by somebody writing a
werk writer from the specification alone (the ArtCraft integration, 2026-10),
and each is recorded in docs/RULINGS-2026-10-13.md, ruling 8, with its finding.

  bytes         every text file under spec/ and loaders/ is LF in this working
                tree, the builders' guard against a translated tree works, and
                every spec and loader file embedded in every pinned fixture is
                byte-identical to the repository's file of the same path
                (F-AC-6: three CRLF working-tree files, reported clean by git,
                behind two failing "rebuild is identical" clauses)
  example       the worked signature covers the worked manifest as it is now
                (F-AC-1: the example manifest failed the schema it illustrates;
                the schema half is core/tests/profiles.rs)
  canonical     the Python `canon()` reproduces the printed canonical-JSON
                vector, non-ASCII included (F-AC-2: it escaped non-ASCII, the
                Rust core did not)
  capabilities  each loader states its capabilities in one line; every name is
                in the enum of both manifest schemas; every fixture manifest
                declares exactly that list for the loader it carries (F-AC-4:
                the list existed in nine places and they disagreed)
  codes         every code the core can emit, and every report code the core
                and the Python loader print over every pinned fixture, is in
                the closed table of SPEC.md section 10 (S-19 / S-20, and the
                core reporting a deflated entry as `file-missing`). NOT held
                for the Rust and C loaders, which do not print report lines in
                the `[severity] code` form at all: open, see the results file
  formats       every format definition this repository owns passes the
                definition checker, and every pinned fixture that carries a
                `formats` map has its definitions checked twice: by
                tools/format_def.py, which DECODES each vector, and by the
                reference core, which re-hashes the printed inputs
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate_common as G                                        # noqa: E402
from fixture_pin import load_record, pin                       # noqa: E402
sys.path.insert(0, os.path.join(G.ROOT, "tools"))
sys.path.insert(0, os.path.join(G.ROOT, "pipeline"))
import spec_sha256 as S                                        # noqa: E402
from loader_caps import loader_capabilities                    # noqa: E402
from common import canon                                       # noqa: E402

CANON_VALUE = {"note": "a→b", "n": 1, "tab": "x\ty", "name": "Größe"}
CANON_SHA = "13a2906649470c284a45bc33763ca934e41edd18e32e764443acfd4aba11baa6"


def tree(*tops):
    out = {}
    for top in tops:
        for base, _dirs, names in os.walk(os.path.join(G.ROOT, top)):
            for name in names:
                if name.endswith(".pyc"):
                    continue
                full = os.path.join(base, name)
                with open(full, "rb") as fh:
                    out[os.path.relpath(full, G.ROOT).replace(os.sep, "/")] = fh.read()
    return out


def spec_codes():
    """The codes of the closed table in SPEC.md section 10."""
    text = open(os.path.join(G.ROOT, "spec", "SPEC.md"), encoding="utf-8").read()
    at = text.index("**The codes are a closed vocabulary")
    block = text[at:text.index("**Exit status", at)]
    found = set()
    for line in block.splitlines():
        if line.startswith("| `"):
            found.update(re.findall(r"`([a-z0-9]+(?:-[a-z0-9]+)+)`", line.split("|")[1]))
    return found


def main():
    gate = G.Gate("REFERENCE")
    record = load_record()
    fixtures = record["fixtures"] if "fixtures" in record else record
    # mini-v1-historical is the frozen package the recorded trials ran on
    # (earlier spec and loaders, kept byte for byte so they stay checkable);
    # it is pinned in fixtures.json but is not held to THIS spec and loaders.
    FROZEN = {"mini-v1-historical"}
    keys = sorted(k for k in fixtures if not k.startswith("_") and k not in FROZEN)

    # ---- bytes -------------------------------------------------------------
    repo = tree("spec", "loaders")
    bad = S.translated_text(repo)
    texts = [p for p in repo if p.endswith(S.TEXT_SUFFIXES)]
    gate.check("bytes: spec/ and loaders/ text is LF", not bad,
               "%d text file(s), no carriage return in any" % len(texts),
               "carriage returns in: %s" % ", ".join(bad))
    p = subprocess.run(["git", "ls-files", "--eol", "spec", "loaders"], cwd=G.ROOT,
                       capture_output=True, text=True)
    if p.returncode == 0 and p.stdout.strip():
        crlf = [l.split("\t")[-1] for l in p.stdout.splitlines()
                if "w/crlf" in l or "w/mixed" in l or "i/crlf" in l]
        gate.check("bytes: git agrees (index and working tree)", not crlf,
                   "%d tracked file(s), none CRLF in the index or the working tree"
                   % len(p.stdout.splitlines()), "CRLF: %s" % ", ".join(crlf))
    else:
        gate.record("bytes: git agrees (index and working tree)", "SKIP",
                    "git is not available here")
    probe = {"spec/SPEC.md": repo["spec/SPEC.md"].replace(b"\n", b"\r\n")}
    try:
        S.spec_sha256_of_files(probe)
        refused = False
    except SystemExit as e:
        refused = "REFUSING TO BUILD" in str(e)
    gate.check("bytes: a builder refuses a translated tree", refused,
               "spec_sha256_of_files() exits naming the file when a spec text file is CRLF")

    stale, embedded, packages = [], 0, 0
    for key in keys:
        r = pin(key)
        if not r.ok:
            gate.record("fixture pinned: %s" % key, "FAIL", r.detail)
            continue
        if not zipfile.is_zipfile(r.path):
            continue
        packages += 1
        with zipfile.ZipFile(r.path) as z:
            for name in z.namelist():
                if name.startswith(("spec/", "loaders/")) and name in repo:
                    embedded += 1
                    if z.read(name) != repo[name]:
                        stale.append("%s:%s" % (key, name))
    gate.check("bytes: fixtures carry THIS spec and THESE loaders", not stale,
               "%d embedded spec/loader files in %d pinned fixtures, every one "
               "byte-identical to the repository's" % (embedded, packages),
               "%d differ, e.g. %s" % (len(stale), ", ".join(stale[:4])))

    # Base-doctrine keys of `meta` must be admitted by every CLOSED meta block
    # of a reference schema, or the doctrine is unwritable in that profile.
    lacking = []
    for name in ("manifest.schema.json", "manifest.image.schema.json"):
        schema = json.loads(repo["spec/schemas/" + name].decode("utf-8"))
        for key, d in schema["$defs"].items():
            if key.endswith("Meta") and key != "loaderMeta" and isinstance(d, dict) \
                    and d.get("additionalProperties") is False:
                for want in ("payload_format", "file_formats", "contained_formats",
                             "modified_by"):
                    if want not in d.get("properties", {}):
                        lacking.append("%s#%s.%s" % (name, key, want))
    gate.check("bytes: closed meta blocks admit the base-doctrine keys", not lacking,
               "payload_format, file_formats, contained_formats and modified_by are "
               "properties of every closed node-meta block of both reference schemas",
               "missing: %s" % ", ".join(lacking))

    # ---- example -----------------------------------------------------------
    ex = os.path.join(G.ROOT, "spec", "examples")
    msha = G.sha256_file(os.path.join(ex, "MANIFEST.example.json"))
    with open(os.path.join(ex, "SIGNATURE.example.json"), encoding="utf-8") as fh:
        sig = json.load(fh)
    gate.check("example: the worked signature covers the worked manifest",
               sig.get("manifest_sha256") == msha, "manifest_sha256 %s" % msha[:16],
               "SIGNATURE.example.json says %s, the manifest hashes to %s"
               % (str(sig.get("manifest_sha256"))[:16], msha[:16]))

    # ---- canonical JSON ----------------------------------------------------
    got = canon(CANON_VALUE)
    got = got if isinstance(got, bytes) else got.encode("utf-8")
    gate.check("canonical: Python canon() reproduces the printed vector",
               hashlib.sha256(got).hexdigest() == CANON_SHA,
               "%d bytes, sha256 %s (MINI-SPECS section 3)" % (len(got), CANON_SHA[:16]),
               "%d bytes %r hash to %s" % (len(got), got, hashlib.sha256(got).hexdigest()))

    # ---- capabilities ------------------------------------------------------
    enums = []
    for name in ("manifest.schema.json", "manifest.image.schema.json"):
        with open(os.path.join(G.ROOT, "spec", "schemas", name), encoding="utf-8") as fh:
            enums.append(set(json.load(fh)["$defs"]["loaderMeta"]["properties"]
                             ["capabilities"]["items"]["enum"]))
    gate.check("capabilities: the two schemas admit the same names", enums[0] == enums[1],
               "%d names in each" % len(enums[0]),
               "differ by %s" % sorted(enums[0] ^ enums[1]))
    declared = {}
    for name in ("werk_read.py", "werk_read.rs", "werk_read.c"):
        try:
            caps = loader_capabilities(repo["loaders/" + name])
        except ValueError as e:
            gate.record("capabilities: %s states them" % name, "FAIL", str(e))
            continue
        declared["loaders/" + name] = caps
        gate.check("capabilities: %s states them" % name, set(caps) <= enums[0],
                   " ".join(caps), "not in the schema enum: %s"
                   % sorted(set(caps) - enums[0]))
    py = re.search(r"^CAPABILITIES = \[(.*?)\]", repo["loaders/werk_read.py"].decode("utf-8"),
                   re.M | re.S)
    py_const = re.findall(r'"([a-z-]+)"', py.group(1)) if py else None
    gate.check("capabilities: werk_read.py's constant is its line",
               py_const == declared.get("loaders/werk_read.py"),
               "CAPABILITIES == the WERK-LOADER-CAPABILITIES line",
               "constant %s, line %s" % (py_const, declared.get("loaders/werk_read.py")))
    wrong, seen = [], 0
    for key in keys:
        path = os.path.join(G.ROOT, fixtures[key]["path"]) if isinstance(fixtures[key], dict) \
            and "path" in fixtures[key] else None
        if not path or not zipfile.is_zipfile(path):
            continue
        with zipfile.ZipFile(path) as z:
            manifest = json.loads(z.read("MANIFEST.json"))
            for node in manifest["nodes"]:
                if node["type"] != "core.loader":
                    continue
                for ver in node["versions"]:
                    entry = ver.get("meta", node.get("meta", {})).get("entrypoint")
                    meta = ver.get("meta") or node.get("meta") or {}
                    if entry in z.namelist() and meta.get("form") == "source":
                        seen += 1
                        if meta.get("capabilities") != loader_capabilities(z.read(entry)):
                            wrong.append("%s:%s" % (key, node["node_id"]))
    gate.check("capabilities: every fixture declares its loaders' own list",
               seen > 0 and not wrong,
               "%d core.loader node versions in the pinned fixtures, each declaring "
               "exactly the list its embedded loader states" % seen,
               "%d of %d disagree: %s" % (len(wrong), seen, ", ".join(wrong[:5])))

    # ---- codes ---------------------------------------------------------------
    table = spec_codes()
    src = open(os.path.join(G.ROOT, "core", "src", "report.rs"), encoding="utf-8").read()
    core_codes = set(re.findall(r'Code::\w+ => "([a-z0-9-]+)"', src))
    gate.check("codes: every code the core can emit is in SPEC section 10",
               core_codes and core_codes <= table,
               "%d core codes, all among the %d of the closed table"
               % (len(core_codes), len(table)),
               "not in the table: %s" % sorted(core_codes - table))
    readers = G.readers(gate)
    for reader in readers:
        if reader[0] in ("rs", "c"):
            # OPEN, and said here rather than passed vacuously: the Rust and C
            # loaders do not print `[severity] code` report lines on --verify.
            # They print per-file words of their own (SHA256-MISMATCH, MISSING,
            # SIZE-MISMATCH) and a summary, and name a table code only for the
            # refusals ruling 9 unified (zip64-unsupported, zip-entry-unsupported,
            # zip-entry-invalid, envelope-invalid, unsupported-profile). A clause
            # that "passed" on zero codes would be a claim nobody measured.
            continue
        printed = set()
        for key in keys:
            path = os.path.join(G.ROOT, fixtures[key]["path"])
            if os.path.isfile(path):
                _rc, out = G.verify(reader, path)
                printed |= {c for _s, c in G.codes(out)}
        gate.check("codes: %s prints only codes of the table" % reader[0],
                   bool(printed) and printed <= table,
                   "%d distinct code(s) over %d fixtures: %s"
                   % (len(printed), len(keys), " ".join(sorted(printed)) or "-"),
                   "not in the table: %s" % sorted(printed - table))

    # ---- formats -------------------------------------------------------------
    defs = sorted(p for p in repo if p.startswith("spec/formats/") and p.endswith(".md"))
    rc, out = G.run([sys.executable, os.path.join(G.ROOT, "tools", "format_def.py"),
                     "--check"] + [os.path.join(G.ROOT, d) for d in defs])
    gate.check("formats: the repository's definitions check", rc == 0 and bool(defs),
               "%d definition(s): %s" % (len(defs), " ".join(os.path.basename(d) for d in defs)),
               out.strip()[-300:])
    carrying = []
    for key in keys:
        path = os.path.join(G.ROOT, fixtures[key]["path"])
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as z:
                if json.loads(z.read("MANIFEST.json")).get("formats"):
                    carrying.append((key, path))
    core = next((r for r in readers if r[0] == "core"), None)
    for key, path in carrying:
        rc, out = G.run([sys.executable, os.path.join(G.ROOT, "tools", "format_def.py"),
                         "--check-package", path])
        line = ""
        if core:
            _rc, cout = G.verify(core, path)
            m = re.search(r"^formats\s*:\s*(.+)$", cout, re.M)
            line = m.group(1) if m else "the core printed no formats line"
        agree = bool(re.match(r"[1-9]\d* definition", line)) and "format-" not in \
            " ".join(c for _s, c in G.codes(cout if core else ""))
        gate.check("formats: %s carries checkable definitions" % key,
                   rc == 0 and (agree or not core),
                   "tools/format_def.py: every vector decoded and compared; core: %s" % line,
                   (out.strip()[-200:] + " | core: " + line))
    gate.check("formats: a fixture exercises the mechanism", bool(carrying),
               "%d pinned fixture(s) with a `formats` map: %s"
               % (len(carrying), " ".join(k for k, _p in carrying)))
    return gate.finish()


if __name__ == "__main__":
    sys.exit(main())
