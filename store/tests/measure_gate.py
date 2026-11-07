"""Stage 7 gate measurement.

Runs the whole store against a real asset pair and prints numbers. Nothing
here asserts; it measures, and the measurements are what goes in HANDOVER.md
(house rule: nothing advances on assertion).

    python tests/measure_gate.py [--corpus DIR] [--workdir DIR] [--keep]

Default corpus: the splat-foley bronze-bell soundpack - real photogrammetry
GLB, real JPEG texture set, real rendered views, real recorded WAVs. If it is
not present the script falls back to the synthetic fixture and says so, and
the number is then worth exactly what a generated corpus is worth.

Working directory defaults to store/.gate (project-local, never a user
profile directory) and is removed unless --keep.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import mkwerk  # noqa: E402

from werkstore import WerkStore, collect, ingest, materialize, scrub  # noqa: E402
from werkstore.diff import diff_stored  # noqa: E402
from werkstore.sync import plan as sync_plan, push  # noqa: E402


def tree_bytes(root: str) -> int:
    total = 0
    for dirpath, _dirs, names in os.walk(root):
        for name in names:
            total += os.path.getsize(os.path.join(dirpath, name))
    return total


def tree_hashes(root: str) -> "dict[str, str]":
    out = {}
    for dirpath, _dirs, names in os.walk(root):
        for name in names:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            h = hashlib.sha256()
            with open(full, "rb") as fh:
                while True:
                    chunk = fh.read(1 << 20)
                    if not chunk:
                        break
                    h.update(chunk)
            out[rel] = h.hexdigest()
    return out


def mib(n: int) -> str:
    return "%.2f MiB" % (n / (1024.0 * 1024.0))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=mkwerk.DEFAULT_CORPUS)
    ap.add_argument("--workdir", default=os.path.join(os.path.dirname(HERE), ".gate"))
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    work = os.path.abspath(args.workdir)
    if os.path.exists(work):
        shutil.rmtree(work)
    os.makedirs(work)

    real = mkwerk.corpus_available(args.corpus)
    src1 = os.path.join(work, "pkg-v1")
    src2 = os.path.join(work, "pkg-v2")

    t0 = time.time()
    if real:
        h1 = mkwerk.make_from_corpus(src1, args.corpus, "v1")
        h2 = mkwerk.make_from_corpus(src2, args.corpus, "v2")
        corpus_label = "splat-foley bronze-bell soundpack (real production assets)"
    else:
        h1 = mkwerk.make_synthetic(src1, "v1")
        h2 = mkwerk.make_synthetic(src2, "v2")
        corpus_label = "SYNTHETIC fixture (real corpus not present on this machine)"
    t_build = time.time() - t0

    logical1, logical2 = tree_bytes(src1), tree_bytes(src2)
    before1, before2 = tree_hashes(src1), tree_hashes(src2)

    store = WerkStore(os.path.join(work, "store"))

    t0 = time.time()
    r1 = ingest(store, src1)
    t_ingest1 = time.time() - t0
    n1, phys1 = store.objects.count_and_bytes()

    t0 = time.time()
    r2 = ingest(store, src2)
    t_ingest2 = time.time() - t0
    n2, phys2 = store.objects.count_and_bytes()

    # Materialize both, directory form, and compare against the ORIGINALS.
    out1 = os.path.join(work, "out-v1")
    out2 = os.path.join(work, "out-v2")
    t0 = time.time()
    m1 = materialize(store, h1, out1, form="directory")
    m2 = materialize(store, h2, out2, form="directory")
    t_mat = time.time() - t0
    identical = tree_hashes(out1) == before1 and tree_hashes(out2) == before2

    # Zip form, store mode, preview-first.
    zip_path = os.path.join(work, "v1.werk")
    t0 = time.time()
    mz = materialize(store, h1, zip_path, form="zip")
    t_zip = time.time() - t0

    # Sync to a second store: what does the far side actually have to move?
    remote = WerkStore(os.path.join(work, "remote"))
    p1 = sync_plan(store, remote, h1)
    s1 = push(store, remote, h1)
    p2 = sync_plan(store, remote, h2)
    s2 = push(store, remote, h2)
    remote_ok = materialize(remote, h2, os.path.join(work, "remote-out"), form="directory").ok

    d = diff_stored(store, h1, h2)

    t0 = time.time()
    sc = scrub(store)
    t_scrub = time.time() - t0
    gc = collect(store, dry_run=True)

    print("")
    print("=" * 72)
    print("werk-store Stage 7 gate measurement")
    print("=" * 72)
    print("corpus            : %s" % corpus_label)
    print("python            : %s" % sys.version.split()[0])
    print("third-party deps  : 0")
    print("")
    print("-- the pair --------------------------------------------------------")
    print("v1 manifest       : %s" % h1)
    print("v2 manifest       : %s" % h2)
    print("v1 on disk        : %s (%d files)" % (mib(logical1), len(before1)))
    print("v2 on disk        : %s (%d files)" % (mib(logical2), len(before2)))
    print("built in          : %.2f s" % t_build)
    print("")
    print("-- dedup (the gate number) -----------------------------------------")
    logical = logical1 + logical2
    print("logical bytes     : %s (both packages materialized side by side)" % mib(logical))
    print("physical bytes    : %s (%d objects in the store)" % (mib(phys2), n2))
    print("dedup ratio       : %.4fx" % (logical / float(phys2)))
    print("space saved       : %.2f%%" % (100.0 * (1 - phys2 / float(logical))))
    print("")
    print("v1 ingest         : %d new objects, %s written, %.2f s"
          % (r1.objects_new, mib(r1.bytes_written), t_ingest1))
    print("v2 ingest         : %d new objects, %s written; %d deduped, %s NOT written, %.2f s"
          % (r2.objects_new, mib(r2.bytes_written), r2.objects_deduped,
             mib(r2.bytes_deduped), t_ingest2))
    print("v2 marginal cost  : %.4f%% of its own %s"
          % (100.0 * r2.bytes_written / float(max(1, logical2)), mib(logical2)))
    print("store after v1    : %d objects, %s" % (n1, mib(phys1)))
    print("store after v2    : %d objects, %s" % (n2, mib(phys2)))
    print("")
    print("-- byte-identity round trip ----------------------------------------")
    print("v1 materialized   : %d files, %d rehashed from the RESULT and matched"
          % (m1.files_written, m1.files_verified))
    print("v2 materialized   : %d files, %d rehashed from the RESULT and matched"
          % (m2.files_written, m2.files_verified))
    print("tree comparison   : %s"
          % ("IDENTICAL to the originals" if identical else "*** DIFFERS ***"))
    print("v1 signature      : %s" % m1.signature.summary())
    print("v2 signature      : %s" % m2.signature.summary())
    print("materialize time  : %.2f s for %s" % (t_mat, mib(logical)))
    print("")
    print("-- zip form (store mode, preview-first) ----------------------------")
    print("archive           : %s" % mib(mz.total_size_bytes))
    print("preview prefix    : %s (%.3f%% of the archive carries the browsable tier)"
          % (mib(mz.preview_prefix_bytes),
             100.0 * mz.preview_prefix_bytes / float(max(1, mz.total_size_bytes))))
    print("verified          : %d entries rehashed from inside the archive" % mz.files_verified)
    print("written in        : %.2f s" % t_zip)
    print("")
    print("-- node-version sync to an empty remote ----------------------------")
    print("v1 plan           : %d objects wanted, %s" % (len(p1.want()), mib(p1.want_bytes)))
    print("v1 pushed         : %d objects, %s" % (s1.objects_copied, mib(s1.bytes_copied)))
    print("v2 plan           : %d objects wanted, %s; %d already present, %s"
          % (len(p2.want()), mib(p2.want_bytes), p2.have_objects, mib(p2.have_bytes)))
    print("v2 pushed         : %d objects, %s copied; %s skipped"
          % (s2.objects_copied, mib(s2.bytes_copied), mib(s2.bytes_skipped)))
    needed = [n for n in p2.versions if n.needed]
    for n in needed:
        print("   needed         : %s@%d - %s" % (n.node_id, n.v, n.note))
    print("transfer saving   : %.2f%% of v2's bytes did not cross"
          % (100.0 * s2.bytes_skipped / float(max(1, s2.bytes_skipped + s2.bytes_copied))))
    print("far side rebuilds : %s" % ("byte-exact" if remote_ok else "*** FAILED ***"))
    print("")
    print("-- manifest-aware diff ---------------------------------------------")
    print("nodes added       : %d" % len(d.nodes_added))
    print("versions added    : %d" % len(d.versions_added))
    print("files added       : %d" % sum(1 for f in d.files if f.kind == "added"))
    print("changelog         : %d work note(s), all pre-written by the author"
          % len(d.changelog))
    for v in d.changelog:
        print("   %s@%d  %s" % (v.node_id, v.v, v.note))
    print("")
    print("-- integrity -------------------------------------------------------")
    print("scrub             : %d objects, %s rehashed in %.2f s - %s"
          % (sc.checked, mib(sc.bytes_checked), t_scrub,
             "all match their own names" if sc.ok else "PROBLEMS FOUND"))
    print("gc (dry run)      : %d live (%s), %d sweepable (%s)"
          % (gc.live, mib(gc.live_bytes), gc.swept, mib(gc.swept_bytes)))
    print("=" * 72)

    if not args.keep:
        shutil.rmtree(work, ignore_errors=True)
    else:
        print("working tree kept at %s" % work)
    return 0 if identical and sc.ok and remote_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
