#!/usr/bin/env python3
"""
driver.py -- the GAP-COMPLETION round harness.

DERIVED FROM `gauntlet/roundOW/driver.py`, byte-for-byte except for the three
changes listed here. Those changes are legal because this is a NEW round: the
open-weights POST-FIX arm refused to change the harness mid-experiment, and
filed the encoding fix (S-SFX-4) for "the next round". This is that round.

  GF-1  A THIRD context packer, `pack_context_gsplat_mini()` (--task-kind
        gsplatmini). The mini packer exists because the round-1 task on
        `mini-v1.werk` must fit 35k tokens; the splat task cannot, because it
        needs TWO complete layout grammars (gsplat + points) on top of the
        envelope, and the 36 KB MANIFEST of a 30 MB fixture. Its size is
        MEASURED and recorded, not budgeted down: Gregor's ruling for this
        round is "it may exceed 35k -- record the size, these models load
        >= 64k".

  GF-2  S-SFX-4 APPLIED. Generated programs are now run with
        PYTHONIOENCODING=utf-8 and PYTHONUTF8=1 in their environment. In the
        post-fix arm `qwen3.8-4B` opened the container correctly and then died
        eight times printing a `U+2717`; that was a harness defect scored as a
        model failure. Recorded as a harness change so no cross-round
        comparison silently attributes a delta to it.

  GF-3  A generated program may now write files with non-ASCII names/content
        without the harness console echo dying -- already fixed in roundOW's
        `say()`, kept.

Everything else -- no tools, one complete program per turn, 8 feedback
iterations or 45 minutes, static isolation screening, harness-measured wall
clock, artifact grading -- is unchanged. The original docstring follows.

---------------------------------------------------------------------------

driver.py -- the open-weights gauntlet harness (OPERATIVE PROTOCOL).

Standard library only: urllib + subprocess + json + zipfile. No pip, no SDK.

WHY THIS SHAPE. The first harness written for this round (kept beside this one
as `driver_toolloop.py`, and discarded before any task was graded) gave the
model four tools and an agentic loop, mirroring the cross-vendor round's CLIs.
Gregor's ruling superseded it: LM Studio models are not CLI agents, they are
"just LLMs sitting in the void", and a tool-call loop measures the served chat
template's tool support at least as much as it measures the model. So:

  1. EVERYTHING THE MODEL MAY READ IS INLINED IN THE PROMPT. One context
     package per task, built by `pack_context()` from inside the .werk file
     itself and nothing else: README.txt, the complete MANIFEST.json, the
     complete zip entry listing (name, size, offset, method, CRC), the spec/
     files, and bounded hex dumps of the binary heads the task needs. This is
     why maximum context is mandatory. Binaries are not inlined whole -- the
     model's PROGRAM runs against the real .werk on disk, so it needs the
     structure, not the bytes.
  2. THE LOOP IS ERROR FEEDBACK, NOT TOOLS. The model emits one complete
     Python program; this harness extracts it, runs it in the isolated run
     directory against the real fixture, and feeds stdout + stderr + traceback
     back for a revision. Cap: 8 feedback iterations or 45 minutes per task.
  3. THE HARNESS MEASURES TIME. Nothing self-reported is timed
     (cross-vendor finding: 2.2x-11x self-report inflation).
  4. ISOLATION IS ENFORCED HERE. Generated programs are statically screened
     for network use and for absolute paths outside the run directory, and are
     run with cwd = the run directory. A refusal is fed back as an error and
     costs the model an iteration; it is not a crash.

CONTEXT PRIORITY ORDER (applied when the package does not fit the model's
loaded context; recorded per run in run.json as `included` / `omitted`):

    1  README.txt                     the file's own entry point
    2  MANIFEST.json                  complete
    3  the zip entry listing          complete, all entries
    4  spec/README.md
    5  spec/MINI-SPECS.md
    6  task-relevant layouts          ENVELOPE + the layouts for the payloads
                                      this task must decode
    7  hex dumps of the relevant binary heads (2048 B each, hex+ASCII), kept
       next to the layouts that describe them
    8  spec/SPEC.md
    9  conventions-map.json, facets.json, SIGNATURE.json, LICENSE
   10  spec/schemas/*                 manifest.schema.json first
   11  everything else textual inside the package

The package is a STRICT PREFIX of that order: the first item that does not fit
the budget ends the package, so "what this model received" is always
expressible as "the first N items of the documented order" rather than an
arbitrary subset. loaders/ is never inlined -- the 0/N-loaders metric would be
meaningless if the harness pasted the loaders in.

Budget = --package-ctx * 3.0 chars/token * --budget-frac (default 0.62); the
rest of the window is left for the program, the feedback and the revisions.
--package-ctx is pinned to ONE value for the whole round so that every model
receives the IDENTICAL package and a size comparison is not confounded by a
context difference; it defaults to --context. The API's reported prompt_tokens
is recorded per run, so the chars/token heuristic is checkable after the fact.

LOADED CONTEXT IS MEASURED, NOT ASSUMED. `prefill_probe.py` times a prefill of
known size against whatever is loaded. On this box (RTX 4090, 24 GB) a 30B-A3B
Q4 model *loads* at its full 262144 but prefills at 293 tok/s because the KV
cache does not fit; the same model at 65536 prefills at 1881 tok/s. The largest
context that does not collapse is what gets loaded, and both numbers are
recorded.

Usage:
  python driver.py --model <id> --task <prompt.txt> --fixture <x.werk>
                   --rundir <dir> --context <tokens> [--quant Q] [--max-iters 8]
                   [--max-wall 2700] [--budget-frac 0.62] [--package-ctx 131072]
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile

API = "http://127.0.0.1:1234/v1"
REQ_TIMEOUT = 1800
PROG_TIMEOUT = 900          # a generated program gets 15 minutes
FEEDBACK_CAP = 12000        # chars of program output fed back
HEX_HEAD_BYTES = 2048       # bytes of each relevant binary head, hex-dumped
CHARS_PER_TOKEN = 3.0       # measured 4.5 on prose; JSON/hex is denser. The real
                            # prompt_tokens is recorded from the API for every run.

SYS = """\
You are a systems programmer. You write one complete, self-contained Python 3 \
program that solves the task below, and you write it in full every time.

Rules of this environment:
  * Your program will be run as `python solution.py` in a directory that \
contains exactly one other thing: the file named in the task. It has no \
network. Only the Python standard library is installed.
  * You cannot run commands yourself and you cannot look at anything. \
Everything you are allowed to see has already been extracted from inside that \
file and is pasted below the task.
  * Reply with ONE fenced ```python block containing the ENTIRE program. No \
diffs, no fragments, no "rest unchanged". If you want to explain something, \
put it in comments inside the program or in one short paragraph before the \
block.
  * Your program must print its findings to stdout. It must not require any \
input.

After each attempt you will be shown exactly what your program printed and any \
traceback it produced, and you may revise. When the program does everything the \
task asks and you are satisfied with its output, reply with the single line \
TASK COMPLETE and nothing else.
"""


# --------------------------------------------------------------------------
# context package
# --------------------------------------------------------------------------

TEXT_EXT = (".md", ".json", ".txt", ".py", ".rs", ".c", ".h", ".layout", ".hex")


def is_text(name):
    return name.endswith(TEXT_EXT) or os.path.basename(name) in ("LICENSE", "README")


def hexdump(data, base=0):
    out = []
    for off in range(0, len(data), 16):
        chunk = data[off:off + 16]
        hx = " ".join("%02x" % b for b in chunk)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        out.append("%08x  %-47s  |%s|" % (base + off, hx, asc))
    return "\n".join(out)


def sections(text, pattern):
    """Split a spec document into (heading, body) by a heading regex."""
    marks = [(m.start(), m.group(0).strip()) for m in re.finditer(pattern, text, re.M)]
    out = []
    for i, (s, h) in enumerate(marks):
        e = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        out.append((h, text[s:e]))
    return out


def pick(text, pattern, wanted):
    """Keep only the numbered sections in `wanted`, in document order.

    GF-4 -- BUG FIX, and the bug is a finding (S-GF-1). roundOW's version was

        n = re.match(r"^[#\\s]*(\\d+)\\.", h)

    which anchors at the start of the WHOLE matched heading. A MINI-SPECS
    heading is `## 5. zip`, so it matched. A layout-grammar heading is three
    lines --

        ------------------------------------------------------------
        3. The header map
        ------------------------------------------------------------

    -- and `.strip()` leaves it starting with a dash, so `re.match` failed for
    EVERY section of EVERY .layout.txt file and `pick` returned the empty
    string. The caller still emitted the `===== FILE
    spec/layouts/ENVELOPE.layout.txt -- SECTIONS 0 to 7 ONLY =====` banner and
    still counted the item as INCLUDED, so nothing in the package header, the
    console output or `run.json` said anything was missing. Verified against
    the committed `gauntlet/roundOW/context_package.mini.txt`: the envelope
    banner is followed by one synthesized title line and then the next banner.
    Searching for the number inside the heading BLOCK instead of at its start
    fixes it."""
    got, keep = sections(text, pattern), []
    for h, body in got:
        n = re.search(r"^\s*#*\s*(\d+)\.", h, re.M)
        if n and int(n.group(1)) in wanted:
            keep.append(body)
    return "".join(keep)


# MINI-SPECS sections, by number:
#   1 bit/byte  2 UTF-8  3 JSON  4 MessagePack  5 zip  6 CRC-32  7 DEFLATE
#   8 PNG  9 WAV  10 GLB  11 SHA-256  12 Ed25519  13 what werk does not use
# ENVELOPE.layout sections:
#   0 governing rules  1 file structure  2 magic  3 header map
#   4 the MessagePack subset  5 payload sections  6 dtypes  7 reference reader
#   8 decisions
MS_H = r"^##\s+\d+\..*$"
EN_H = r"^-{20,}\n\d+\..*\n-{20,}$"


def pack_context_mini(fixture, budget_chars):
    """The <35k-token package: the same idea as pack_context, but every spec
    document is cut to the sections this task actually needs, because the
    interesting question is how many tokens of specification the format needs
    in order to be implementable at all."""
    z = zipfile.ZipFile(fixture)
    infos = z.infolist()
    T = lambda n: z.read(n).decode("utf-8", "replace")

    listing = ["%-50s %9s %11s %9s %s" % ("name", "size", "offset", "crc32", "method")]
    for i in infos:
        listing.append("%-50s %9d %11d %9s %s"
                       % (i.filename, i.file_size, i.header_offset,
                          "%08x" % (i.CRC & 0xffffffff), i.compress_type))

    ms = T("spec/MINI-SPECS.md")
    en = T("spec/layouts/ENVELOPE.layout.txt")
    blocks = [
        ("README.txt", "FILE README.txt", T("README.txt")),
        ("MANIFEST.json", "FILE MANIFEST.json (complete)", T("MANIFEST.json")),
        ("<zip listing>", "ZIP ENTRY LISTING (all %d entries: name, uncompressed size, "
         "local-header offset, CRC-32, compression method; 0 = store)" % len(infos),
         "\n".join(listing)),
        ("MINI-SPECS 1,2,3,5,6,11", "FILE spec/MINI-SPECS.md -- SECTIONS 1, 2, 3, 5, 6 and 11 "
         "ONLY (bit/byte order, UTF-8, JSON, zip, CRC-32, SHA-256). Sections 4, 7-10, "
         "12, 13 were cut to fit the context budget.",
         pick(ms, MS_H, {1, 2, 3, 5, 6, 11})),
        ("ENVELOPE 0-7", "FILE spec/layouts/ENVELOPE.layout.txt -- SECTIONS 0 to 7 ONLY "
         "(the whole normative grammar; section 8, the decision log, was cut).",
         "werk binary envelope - layout grammar v1\n" + pick(en, EN_H, {0, 1, 2, 3, 4, 5, 6, 7})),
        ("spec/layouts/restposes.layout.txt", "FILE spec/layouts/restposes.layout.txt (complete)",
         T("spec/layouts/restposes.layout.txt")),
        # S-OW-3, added for the POST-FIX arm: the worked, annotated hex decode
        # of exactly this envelope kind. It is in the package's own spec/ tree.
        ("spec/examples/restposes.example.hex.txt",
         "FILE spec/examples/restposes.example.hex.txt (complete) -- a worked, "
         "annotated byte-by-byte decode of a WKRP envelope",
         T("spec/examples/restposes.example.hex.txt")),
    ]
    for name in ("geometry/game.glb", "audio/sfx/crate-impact-hard-surface.wav",
                 "poses/rest.wkrp", "x/splat-foley/segments/seg_00.png"):
        try:
            data = z.read(name)[:256]
        except KeyError:
            continue
        blocks.append(("hex:" + name,
                       "HEX DUMP -- first %d bytes of %s (hex+ASCII, 16 B/line)" % (len(data), name),
                       hexdump(data)))
    blocks += [
        ("MINI-SPECS 9,10", "FILE spec/MINI-SPECS.md -- SECTIONS 9 and 10 (WAV, GLB)",
         pick(ms, MS_H, {9, 10})),
        ("MINI-SPECS 12", "FILE spec/MINI-SPECS.md -- SECTION 12 (Ed25519)",
         pick(ms, MS_H, {12})),
        ("MINI-SPECS 8", "FILE spec/MINI-SPECS.md -- SECTION 8 (PNG)", pick(ms, MS_H, {8})),
        ("spec/README.md", "FILE spec/README.md (complete)", T("spec/README.md")),
        ("spec/conventions-map.json", "FILE spec/conventions-map.json", T("spec/conventions-map.json")),
        ("SIGNATURE.json", "FILE SIGNATURE.json", T("SIGNATURE.json")),
        ("LICENSE", "FILE LICENSE", T("LICENSE")),
    ]
    return _assemble(blocks, budget_chars)


# gsplat.layout sections, by number:
#   0 what this payload is  1 fixed prefix  2 header keys  3 payload sections
#   4 coefficient-major  5 from coefficients to a colour  6 ingesting a PLY
#   7 degradation into a point cloud (NORMATIVE)  8 what a reader MUST check
#   9 decisions
# points.layout sections, by number:
#   0 design question  1 fixed prefix  2 header keys  3 payload sections
#   4 the field entry  5 the semantic registry  6 what a reader MUST check
#   7 ingesting a PLY  8 decisions
LY_H = r"^-{20,}\n\d+\..*\n-{20,}$"


def pack_context_gsplat_mini(fixture, budget_chars):
    """The splat-task package: the same construction as `pack_context_mini`,
    aimed at `gsplat-v1.werk`'s task instead of `mini-v1.werk`'s.

    What the task needs that the round-1 task does not: the ENVELOPE grammar,
    BOTH payload grammars (WKGS and WKPC -- the task's "positions and colours"
    exist in both, and the normative relationship between them is
    gsplat.layout section 7), the MessagePack mini-spec (a WKGS header is
    MessagePack, a manifest is not), and the worked hex decodes that S-OW-3
    put in the spec tree. Section 9/8 decision logs are cut; nothing normative
    is."""
    z = zipfile.ZipFile(fixture)
    infos = z.infolist()
    T = lambda n: z.read(n).decode("utf-8", "replace")

    listing = ["%-58s %10s %12s %10s %s" % ("name", "size", "offset", "crc32", "method")]
    for i in infos:
        listing.append("%-58s %10d %12d %10s %s"
                       % (i.filename, i.file_size, i.header_offset,
                          "%08x" % (i.CRC & 0xffffffff), i.compress_type))

    ms = T("spec/MINI-SPECS.md")
    en = T("spec/layouts/ENVELOPE.layout.txt")
    gs = T("spec/layouts/gsplat.layout.txt")
    pc = T("spec/layouts/points.layout.txt")

    blocks = [
        ("README.txt", "FILE README.txt", T("README.txt")),
        ("MANIFEST.json", "FILE MANIFEST.json (complete)", T("MANIFEST.json")),
        ("<zip listing>", "ZIP ENTRY LISTING (all %d entries: name, uncompressed size, "
         "local-header offset, CRC-32, compression method; 0 = store)" % len(infos),
         "\n".join(listing)),
        ("MINI-SPECS 1,2,3,4,5,6,11",
         "FILE spec/MINI-SPECS.md -- SECTIONS 1, 2, 3, 4, 5, 6 and 11 ONLY "
         "(bit/byte order, UTF-8, JSON, MessagePack, zip, CRC-32, SHA-256). "
         "Sections 7-10, 12 and 13 were cut: this task decodes no DEFLATE, no "
         "PNG, no WAV and no GLB.",
         pick(ms, MS_H, {1, 2, 3, 4, 5, 6, 11})),
        ("ENVELOPE 0-7", "FILE spec/layouts/ENVELOPE.layout.txt -- SECTIONS 0 to 7 ONLY "
         "(the whole normative grammar; section 8, the decision log, was cut).",
         "werk binary envelope - layout grammar v1\n" + pick(en, EN_H, {0, 1, 2, 3, 4, 5, 6, 7})),
        ("gsplat.layout 0-8", "FILE spec/layouts/gsplat.layout.txt -- SECTIONS 0 to 8 "
         "(everything normative, including section 5 'from coefficients to a colour' "
         "and section 7, the NORMATIVE degradation into a point cloud; section 9, the "
         "decision log, was cut).",
         'werk gaussian splat - layout grammar v1  (magic "WKGS")\n'
         + pick(gs, LY_H, {0, 1, 2, 3, 4, 5, 6, 7, 8})),
        ("points.layout 0-7", "FILE spec/layouts/points.layout.txt -- SECTIONS 0 to 7 "
         "(everything normative; section 8, the decision log, was cut).",
         'werk point cloud - layout grammar v1  (magic "WKPC")\n'
         + pick(pc, LY_H, {0, 1, 2, 3, 4, 5, 6, 7})),
        # S-OW-3: the worked, annotated hex decodes. WKGS is the one this task
        # needs; WKEM is included as the SECOND worked example of the same
        # envelope, because S-OW-3's finding was about the RUNG between a
        # grammar and a decoder, not about one payload kind.
        ("spec/examples/gsplat.example.hex.txt",
         "FILE spec/examples/gsplat.example.hex.txt (complete) -- a worked, annotated "
         "byte-by-byte decode of a small WKGS envelope",
         T("spec/examples/gsplat.example.hex.txt")),
    ]
    for name in ("splats/plush.wkgs", "points/plush-dc.wkpc"):
        try:
            data = z.read(name)[:HEX_HEAD_BYTES]
        except KeyError:
            continue
        blocks.append(("hex:" + name,
                       "HEX DUMP -- first %d bytes of %s (hex+ASCII, 16 B/line)"
                       % (len(data), name),
                       hexdump(data)))
    blocks += [
        ("semantics/semantics.json", "FILE semantics/semantics.json", T("semantics/semantics.json")),
        ("spec/conventions-map.json", "FILE spec/conventions-map.json", T("spec/conventions-map.json")),
    ]
    # WHAT WAS CUT, and why it is a cut rather than an omission. With GF-4
    # fixed the three layout grammars are actually present, and they are 62 000
    # characters between them; the complete package is 213 737 characters and
    # ~95 000 tokens, which no model on this box can be SERVED at speed. The
    # cut list is the items the splat task cannot use: MINI-SPECS 12 (Ed25519
    # -- the task does not ask for the signature and every previous round's
    # models either declined it or raised a false alarm), the WKEM worked hex
    # example (a second worked example of an envelope kind this file does not
    # contain), LICENSE, SIGNATURE.json, spec/README.md, recipe/recipe.json,
    # provenance/provenance.json, and the hex head of the INPUT .splat (the
    # task decodes the werk payloads, not the ingested original). Nothing
    # normative to the three task clauses is cut, and the cut is recorded in
    # run.json's `omitted` field as an explicit list rather than as silence --
    # which is exactly the failure S-GF-1 names.
    # NOTE: tools/ is NOT inlined. Task 3 asks the model to identify the
    # embedded tools and quote their source; the whole point is that its
    # PROGRAM reads them out of the file. Inlining them would answer task 3 in
    # the prompt. loaders/ is not inlined either, for roundOW's reason.
    return _assemble(blocks, budget_chars)


def _assemble(blocks, budget_chars):
    parts, included, omitted, used, full = [], [], [], 0, False
    for key, title, body in blocks:
        chunk = "\n\n===== %s =====\n%s\n" % (title, body)
        if full or used + len(chunk) > budget_chars:
            full = True
            omitted.append(key)
            continue
        parts.append(chunk)
        included.append(key)
        used += len(chunk)
    header = (
        "===== CONTEXT PACKAGE =====\n"
        "Everything below was extracted from INSIDE the file named in the task and\n"
        "from nowhere else. You cannot read the file yourself, so this is what you\n"
        "have. The bundled reader programs under loaders/ were deliberately NOT\n"
        "included. Binary payloads appear only as short hex heads; your program will\n"
        "run against the real file and can read every byte itself.\n"
        "Included: %d of %d items%s.\n"
        % (len(included), len(blocks),
           "" if not omitted else "; omitted for the context budget: " + ", ".join(omitted)))
    return header + "".join(parts), included, omitted, {"chars": used + len(header)}


def pack_context(fixture, task_kind, budget_chars):
    """Return (package_text, included, omitted, stats)."""
    z = zipfile.ZipFile(fixture)
    infos = z.infolist()
    names = [i.filename for i in infos]

    listing = ["%-58s %10s %12s %10s %s" % ("name", "size", "offset", "crc32", "method")]
    for i in infos:
        listing.append("%-58s %10d %12d %10s %s"
                       % (i.filename, i.file_size, i.header_offset,
                          "%08x" % (i.CRC & 0xffffffff), i.compress_type))
    listing = "\n".join(listing)

    if task_kind == "gsplat":
        prio_layouts = ["spec/layouts/ENVELOPE.layout.txt",
                        "spec/layouts/gsplat.layout.txt",
                        "spec/layouts/points.layout.txt"]
        bin_pref = (".wkgs", ".wkpc", ".wkrp", ".splat", ".ply")
    else:
        prio_layouts = ["spec/layouts/ENVELOPE.layout.txt"]
        bin_pref = (".glb", ".wav", ".png", ".wkrp")

    blocks = []          # (key, title, body)
    def add(key, title, body):
        blocks.append((key, title, body))

    def filetext(n):
        return z.read(n).decode("utf-8", "replace")

    if "README.txt" in names:
        add("README.txt", "FILE README.txt", filetext("README.txt"))
    add("MANIFEST.json", "FILE MANIFEST.json (complete)", filetext("MANIFEST.json"))
    add("<zip listing>", "ZIP ENTRY LISTING (all %d entries: name, uncompressed size, "
        "local-header offset, CRC-32, compression method; method 0 = store)" % len(infos), listing)
    for n in ("spec/README.md", "spec/MINI-SPECS.md"):
        if n in names:
            add(n, "FILE " + n, filetext(n))
    for n in prio_layouts:
        if n in names:
            add(n, "FILE " + n, filetext(n))
    # hex heads of the binaries this task must decode (kept next to their layouts)
    bins = [i for i in infos if i.filename.lower().endswith(bin_pref)]
    seen_ext = {}
    chosen = []
    for i in bins:
        e = os.path.splitext(i.filename)[1].lower()
        seen_ext[e] = seen_ext.get(e, 0) + 1
        if seen_ext[e] <= (3 if task_kind == "gsplat" else 2):
            chosen.append(i)
    for i in chosen:
        data = z.read(i.filename)[:HEX_HEAD_BYTES]
        add("hex:" + i.filename,
            "HEX DUMP -- first %d bytes of %s (entry is %d bytes; hex+ASCII, 16 B/line)"
            % (len(data), i.filename, i.file_size),
            hexdump(data))

    for n in ("spec/SPEC.md", "spec/conventions-map.json", "spec/facets.json",
              "SIGNATURE.json", "LICENSE"):
        if n in names:
            add(n, "FILE " + n, filetext(n))

    rest = [n for n in names
            if is_text(n) and n not in [b[0] for b in blocks]]
    rest.sort(key=lambda n: (0 if n == "spec/schemas/manifest.schema.json" else
                             1 if n.startswith("spec/schemas/") else 2, n))
    for n in rest:
        if n.startswith("loaders/"):
            continue        # the bundled readers are deliberately NOT inlined
        add(n, "FILE " + n, filetext(n))

    # STRICT PREFIX of the priority order: the first item that does not fit ends
    # the package. No cherry-picking small low-priority items over a large
    # high-priority one -- what a model received is then exactly "the first N of
    # the documented order", which is a describable quantity.
    parts, included, omitted = [], [], []
    used = 0
    full = False
    for key, title, body in blocks:
        chunk = "\n\n===== %s =====\n%s\n" % (title, body)
        if full or used + len(chunk) > budget_chars:
            full = True
            omitted.append(key)
            continue
        parts.append(chunk)
        included.append(key)
        used += len(chunk)

    header = (
        "===== CONTEXT PACKAGE =====\n"
        "Everything below was extracted from INSIDE the file named in the task and\n"
        "from nowhere else. You cannot read the file yourself, so this is what you\n"
        "have. The bundled reader programs under loaders/ were deliberately NOT\n"
        "included. Binary payloads are present only as hex heads; your program will\n"
        "run against the real file and can read all of their bytes itself.\n"
        "Included: %d of %d text items%s.\n"
        % (len(included), len(blocks),
           "" if not omitted else "; omitted for context budget: " + ", ".join(omitted)))
    return header + "".join(parts), included, omitted, {"chars": used + len(header)}


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------

def chat(model, messages, max_tokens=16384, temperature=0.2):
    payload = {"model": model, "messages": messages, "temperature": temperature,
               "max_tokens": max_tokens, "stream": False}
    req = urllib.request.Request(API + "/chat/completions",
                                 data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=REQ_TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


# --------------------------------------------------------------------------
# program extraction and screening
# --------------------------------------------------------------------------

CODE_RE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S)
NET_IMPORT = re.compile(r"\b(?:import|from)\s+(urllib|socket|http|requests|ftplib|"
                        r"smtplib|telnetlib|xmlrpc|asyncio\.streams)\b")
ABS_OUT = re.compile(r"""["']((?:[A-Za-z]:[\\/])|(?:/(?:mnt|usr|etc|home|tmp)/))[^"']*["']""")


def extract_program(text):
    best = None
    for m in CODE_RE.finditer(text or ""):
        body = m.group(1)
        if best is None or len(body) > len(best):
            best = body
    if best is None:
        return None
    return best


def screen(src, root):
    if NET_IMPORT.search(src):
        return "REFUSED BY THE HARNESS: your program imports a networking module. " \
               "There is no network and none is permitted. Everything must come from the file."
    for m in ABS_OUT.finditer(src):
        lit = m.group(0)[1:-1]
        probe = lit
        mm = re.match(r"^/([a-zA-Z])/(.*)$", probe)
        if mm:
            probe = mm.group(1).upper() + ":\\" + mm.group(2)
        try:
            rp = os.path.realpath(probe)
        except Exception:
            continue
        if not (rp == root or rp.startswith(root + os.sep)):
            return ("REFUSED BY THE HARNESS: your program contains the absolute path %r, "
                    "which is outside the working directory. Use relative paths only." % lit)
    return None


def clip(s, cap=FEEDBACK_CAP):
    if len(s) <= cap:
        return s
    half = cap // 2
    return s[:half] + "\n...[%d chars elided by the harness]...\n" % (len(s) - cap) + s[-half:]


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--task", required=True)
    ap.add_argument("--fixture", required=True)
    ap.add_argument("--rundir", required=True)
    ap.add_argument("--context", type=int, required=True)
    ap.add_argument("--quant", default="")
    ap.add_argument("--label", default="")
    ap.add_argument("--task-kind", default="",
                    choices=["", "round1", "gsplat", "mini", "gsplatmini"])
    ap.add_argument("--max-iters", type=int, default=8)
    ap.add_argument("--max-wall", type=int, default=2700)
    ap.add_argument("--budget-frac", type=float, default=0.62)
    ap.add_argument("--package-ctx", type=int, default=0,
                    help="context length the PACKAGE budget is computed from. Defaults to "
                         "--context. Set to a fixed value so that every model receives the "
                         "identical package regardless of its own window.")
    ap.add_argument("--max-tokens", type=int, default=16384)
    args = ap.parse_args()

    rundir = os.path.realpath(args.rundir)
    hdir = os.path.join(rundir, "_harness")
    os.makedirs(hdir, exist_ok=True)
    logf = open(os.path.join(hdir, "stdout.log"), "w", encoding="utf-8")

    def say(s):
        # The console on this host is cp1252 and a model is free to emit any
        # code point it likes. `nvidia/nemotron-3-nano-4b` emitted U+2011
        # (non-breaking hyphen) in its first reply and the harness died with a
        # UnicodeEncodeError -- scoring a HARNESS defect as a model failure,
        # which is exactly what S-OW-5 warns about. The log file is UTF-8 and
        # keeps every character; only the console echo degrades.
        try:
            print(s, flush=True)
        except UnicodeEncodeError:
            enc = (sys.stdout.encoding or "ascii")
            print(s.encode(enc, "replace").decode(enc, "replace"), flush=True)
        logf.write(s + "\n")
        logf.flush()

    kind = args.task_kind or ("gsplat" if "gsplat" in os.path.basename(args.task).lower() else "round1")
    pctx = args.package_ctx or args.context
    budget = int(pctx * CHARS_PER_TOKEN * args.budget_frac)
    if kind == "mini":
        pkg, included, omitted, stats = pack_context_mini(args.fixture, budget)
    elif kind == "gsplatmini":
        pkg, included, omitted, stats = pack_context_gsplat_mini(args.fixture, budget)
    else:
        pkg, included, omitted, stats = pack_context(args.fixture, kind, budget)
    task_text = open(args.task, "r", encoding="utf-8").read()
    with open(os.path.join(hdir, "context_package.txt"), "w", encoding="utf-8") as f:
        f.write(pkg)

    say("model=%s ctx=%d package_ctx=%d budget=%d chars package=%d chars included=%d omitted=%d"
        % (args.model, args.context, pctx, budget, stats["chars"], len(included), len(omitted)))
    if omitted:
        say("omitted: %s" % ", ".join(omitted))

    messages = [{"role": "system", "content": SYS},
                {"role": "user", "content": task_text + "\n\n" + pkg}]

    t0 = time.monotonic()

    # PREFLIGHT. One request for a single token, so the cost is the prefill of
    # the context package and nothing else. It measures two things that must be
    # in the record: how many tokens the package actually is (the chars/token
    # heuristic above is only a guess) and what one cold prefill costs on this
    # box. Every model is loaded fresh before its run, so this number is
    # comparable across models. It is inside the wall clock, and `wall_s` minus
    # `preflight_s` is reported too.
    preflight_s, pf_tokens = None, None
    try:
        tp = time.monotonic()
        rp = chat(args.model, messages, max_tokens=1)
        preflight_s = round(time.monotonic() - tp, 1)
        pf_tokens = (rp.get("usage") or {}).get("prompt_tokens")
        say("preflight: prompt_tokens=%s cold prefill=%.1fs (%.0f tok/s), chars/token=%.2f"
            % (pf_tokens, preflight_s, (pf_tokens or 0) / max(preflight_s, 0.001),
               len(messages[1]["content"]) / max(pf_tokens or 1, 1)))
        if pf_tokens and pf_tokens > args.context:
            say("!! WARNING: the package does not fit the loaded context "
                "(%d > %d). The server will truncate." % (pf_tokens, args.context))
    except Exception as e:
        say("preflight failed: %s" % e)

    it = 0
    outcome, detail = "unknown", ""
    first_clean = None
    prompt_tokens = None
    truncations = 0
    no_code = 0
    history = []

    while True:
        if it >= args.max_iters:
            outcome, detail = "iteration-cap", "used all %d feedback iterations" % args.max_iters
            break
        if time.monotonic() - t0 > args.max_wall:
            outcome, detail = "wall-cap", "hit the %d s wall cap" % args.max_wall
            break
        it += 1
        try:
            r = chat(args.model, messages, max_tokens=args.max_tokens)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:800]
            outcome, detail = "api-error", "HTTP %s: %s" % (e.code, body)
            say("!! " + detail)
            break
        except Exception as e:
            outcome, detail = "api-error", str(e)
            say("!! " + detail)
            break

        ch = r["choices"][0]
        content = ch["message"].get("content") or ""
        fin = ch.get("finish_reason")
        if prompt_tokens is None:
            prompt_tokens = (r.get("usage") or {}).get("prompt_tokens")
        if fin == "length":
            truncations += 1
        say("\n--- iteration %d (%.0fs, finish=%s, %d chars) ---" %
            (it, time.monotonic() - t0, fin, len(content)))
        say(content[:800])
        messages.append({"role": "assistant", "content": content})

        if re.match(r"^\s*TASK COMPLETE\s*$", content, re.I) or \
           (first_clean is not None and re.search(r"\bTASK COMPLETE\b", content) and
                extract_program(content) is None):
            outcome, detail = "model-finished", "declared TASK COMPLETE after a clean run"
            break

        src = extract_program(content)
        if src is None:
            no_code += 1
            if no_code >= 3:
                outcome, detail = "no-program", "3 replies with no ```python block"
                break
            messages.append({"role": "user", "content":
                             "I did not find a ```python block. Reply with ONE fenced ```python "
                             "block containing the entire program, or the single line TASK COMPLETE."})
            continue
        no_code = 0

        with open(os.path.join(rundir, "solution.py"), "w", encoding="utf-8", newline="\n") as f:
            f.write(src)
        with open(os.path.join(hdir, "solution.iter%d.py" % it), "w", encoding="utf-8", newline="\n") as f:
            f.write(src)

        ref = screen(src, rundir)
        if ref:
            say("  >> %s" % ref)
            history.append({"iter": it, "exit": None, "refused": ref})
            messages.append({"role": "user", "content": ref + "\nRevise and send the whole program again."})
            continue

        say("  >> running solution.py (%d chars)" % len(src))
        t1 = time.monotonic()
        try:
            # GF-2 / S-SFX-4: the child gets a UTF-8 stdout. Without this a
            # program that is otherwise correct dies on a cp1252 console the
            # moment it prints a check mark, and the round records a model
            # failure that is the harness's.
            cenv = dict(os.environ)
            cenv["PYTHONIOENCODING"] = "utf-8"
            cenv["PYTHONUTF8"] = "1"
            p = subprocess.run([sys.executable, "solution.py"], cwd=rundir,
                               capture_output=True, timeout=PROG_TIMEOUT, env=cenv)
            out = p.stdout.decode("utf-8", "replace")
            err = p.stderr.decode("utf-8", "replace")
            rc = p.returncode
        except subprocess.TimeoutExpired as e:
            out = (e.stdout or b"").decode("utf-8", "replace")
            err = "TIMEOUT: killed after %d s" % PROG_TIMEOUT
            rc = -9
        dt = time.monotonic() - t1
        say("  << exit=%d in %.1fs  stdout=%dB stderr=%dB" % (rc, dt, len(out), len(err)))
        say("  " + (out[:1200].replace("\n", "\n  ")))
        if err:
            say("  STDERR: " + err[:800].replace("\n", "\n  "))
        history.append({"iter": it, "exit": rc, "secs": round(dt, 1),
                        "stdout_bytes": len(out), "stderr_bytes": len(err)})

        if rc == 0 and first_clean is None:
            first_clean = it

        if rc == 0:
            fb = ("Your program ran and exited 0 in %.1f s. Here is exactly what it printed.\n\n"
                  "--- stdout ---\n%s\n--- stderr ---\n%s\n\n"
                  "If this does everything the task asks, reply with the single line TASK COMPLETE. "
                  "Otherwise send the whole revised program in one ```python block."
                  % (dt, clip(out), clip(err, 2000)))
        else:
            fb = ("Your program FAILED with exit code %d after %.1f s.\n\n"
                  "--- stdout ---\n%s\n--- stderr ---\n%s\n\n"
                  "Send the whole corrected program in one ```python block."
                  % (rc, dt, clip(out, 4000), clip(err)))
        messages.append({"role": "user", "content": fb})

    wall = time.monotonic() - t0
    say("\n=== outcome=%s (%s) iters=%d first_clean_run=%s wall=%.1fs ==="
        % (outcome, detail, it, first_clean, wall))

    with open(os.path.join(hdir, "transcript.json"), "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=1)
    row = {"model": args.model, "quant": args.quant, "context": args.context,
           "task": os.path.basename(args.task), "kind": kind, "label": args.label,
           "protocol": "inline-context + error-feedback",
           "harness": "roundGF/driver.py (roundOW/driver.py + GF-1 gsplatmini packer "
                      "+ GF-2 PYTHONIOENCODING=utf-8 per S-SFX-4)", "outcome": outcome,
           "detail": detail, "iterations": it, "first_clean_run": first_clean,
           "wall_s": round(wall, 1), "preflight_s": preflight_s,
           "wall_s_excl_preflight": round(wall - (preflight_s or 0), 1),
           "prompt_tokens": prompt_tokens or pf_tokens,
           "package_ctx": pctx, "package_chars": stats["chars"],
           "included": included,
           "omitted": omitted, "truncated_replies": truncations,
           "runs": history, "rundir": rundir}
    with open(os.path.join(hdir, "run.json"), "w", encoding="utf-8") as f:
        json.dump(row, f, indent=1)
    say(json.dumps({k: v for k, v in row.items() if k != "runs"}))
    logf.close()


if __name__ == "__main__":
    main()
