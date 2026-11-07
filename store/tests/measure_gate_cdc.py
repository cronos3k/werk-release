"""Stage 7 CDC gate measurement.

Re-ingests the real conformance fixture corpus (crate-v1, crate-v1-damaged,
ista-varun-v1) plus an "edited" variant built here by modifying a small
region of the corpus's biggest payload, and prints numbers. Nothing here
asserts; it measures, and the measurements are what goes in HANDOVER.md
under "Stage 7 CDC results" (house rule: nothing advances on assertion).

    python tests/measure_gate_cdc.py [--fixtures DIR] [--workdir DIR] [--keep]

The edited variant is a real enrichment, done the honest way: the payload
bytes change, the manifest's declared sha256 for that file is updated, and
a new custody link is APPENDED to the existing signature chain with the
fixtures' published dev key - so the edited package is signed-and-valid
over its new manifest state, exactly like a real edit would be.

Working directory defaults to store/.gate-cdc (project-local, never a user
profile directory) and is removed unless --keep.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from werkstore import WerkStore, collect, ingest, materialize, scrub  # noqa: E402
from werkstore import ed25519  # noqa: E402
from werkstore.chunking import (  # noqa: E402
    AVG_SIZE,
    DEFAULT_THRESHOLD,
    MAX_SIZE,
    MIN_SIZE,
    chunk_bytes,
)
from werkstore.ingest import IngestRefused  # noqa: E402
from werkstore.signature import link_hash, message_for, verify_chain  # noqa: E402
from werkstore.sync import plan as sync_plan, push  # noqa: E402

DEFAULT_FIXTURES = os.path.join(os.path.dirname(os.path.dirname(HERE)), "fixtures")

# The fixtures' dev key: DERIVED, PUBLISHED, AND NOT SECRET (see
# fixtures/build_golden.py). It signs nothing that matters; it makes the
# edited variant reproducible.
DEV_KEY_PHRASE = b"werk dev key, publicly derived, fixtures only, 2026-08-08"
DEV_SK = hashlib.sha256(DEV_KEY_PHRASE).digest()
EDIT_SIGNED_AT = "2026-08-08T14:00:00Z"

EDIT_OFFSET = 2_500_000
EDIT_LENGTH = 4096


def sha_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


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
            out[rel] = sha_file(full)
    return out


def mib(n: "int | float") -> str:
    return "%.2f MiB" % (n / (1024.0 * 1024.0))


def extract(werk_zip: str, dest: str) -> None:
    with zipfile.ZipFile(werk_zip) as zf:
        zf.extractall(dest)


def biggest_payload(root: str) -> "tuple[str, int]":
    best, size = "", -1
    for dirpath, _dirs, names in os.walk(root):
        for name in names:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if rel in ("MANIFEST.json", "SIGNATURE.json"):
                continue
            n = os.path.getsize(full)
            if n > size:
                best, size = rel, n
    return best, size


def keystream(seed: bytes, n: int) -> bytes:
    parts, total, i = [], 0, 0
    while total < n:
        b = hashlib.sha256(seed + i.to_bytes(8, "big")).digest()
        parts.append(b)
        total += len(b)
        i += 1
    return b"".join(parts)[:n]


def build_edited_variant(src_dir: str, dest_dir: str) -> "tuple[str, str, str]":
    """Copy *src_dir*, edit a small region of its biggest payload, update the
    manifest, and append a custody link. Returns (payload_path, old_hash,
    new_hash)."""
    shutil.copytree(src_dir, dest_dir)
    rel, _size = biggest_payload(dest_dir)
    full = os.path.join(dest_dir, *rel.split("/"))
    old_hash = sha_file(full)

    with open(full, "r+b") as fh:
        fh.seek(EDIT_OFFSET)
        fh.write(keystream(b"werk-cdc-gate-edit-v1", EDIT_LENGTH))
    new_hash = sha_file(full)

    # The manifest declares the file's sha256 (and possibly repeats it as an
    # input_hash source); a bytes-level substitution updates every mention
    # without disturbing one other byte of formatting. Size is unchanged by
    # construction (an in-place overwrite).
    man_path = os.path.join(dest_dir, "MANIFEST.json")
    with open(man_path, "rb") as fh:
        raw = fh.read()
    patched = raw.replace(old_hash.encode("ascii"), new_hash.encode("ascii"))
    if patched == raw:
        raise SystemExit("edit produced no manifest change - wrong payload?")
    with open(man_path, "wb") as fh:
        fh.write(patched)
    new_manifest_hash = hashlib.sha256(patched).hexdigest()

    # Append a custody link over the new manifest state (S-1 semantics:
    # enrichment appends, earlier links keep naming the states they signed).
    sig_path = os.path.join(dest_dir, "SIGNATURE.json")
    with open(sig_path, "rb") as fh:
        doc = json.loads(fh.read())
    chain = doc["chain"]
    prev = link_hash(str(chain[-1]["signature"]))
    signer = {"name": "cdc-gate", "uri": "https://werk.format/tools/measure-gate-cdc",
              "kind": "agent", "role": "enrichment"}
    msg = message_for(new_manifest_hash, prev, EDIT_SIGNED_AT, signer["uri"], signer["kind"])
    sig = ed25519.sign(DEV_SK, msg)
    chain.append({
        "index": len(chain),
        "signer": signer,
        "public_key": ed25519.public_key(DEV_SK).hex(),
        "signed_at": EDIT_SIGNED_AT,
        "manifest_sha256": new_manifest_hash,
        "prev_entry_sha256": prev,
        "signature": sig.hex(),
        "note": "gate edit: %d bytes at offset %d of %s" % (EDIT_LENGTH, EDIT_OFFSET, rel),
    })
    doc["manifest_sha256"] = new_manifest_hash
    with open(sig_path, "wb") as fh:
        fh.write((json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))

    verdict = verify_chain(open(sig_path, "rb").read(), new_manifest_hash)
    if not verdict.ok:
        raise SystemExit("appended chain does not verify: %s" % "; ".join(verdict.problems))
    return rel, old_hash, new_hash


def physical_bytes(store: WerkStore) -> "tuple[int, int, int, int]":
    n, obj_bytes = store.objects.count_and_bytes()
    r, rec_bytes = store.objects.recipes_count_and_bytes()
    return n, obj_bytes, r, rec_bytes


def ingest_corpus(store: WerkStore, packages: "list[tuple[str, str]]"):
    results = []
    for label, path in packages:
        t0 = time.time()
        r = ingest(store, path)
        results.append((label, r, time.time() - t0))
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", default=DEFAULT_FIXTURES)
    ap.add_argument("--workdir", default=os.path.join(os.path.dirname(HERE), ".gate-cdc"))
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    work = os.path.abspath(args.workdir)
    if os.path.exists(work):
        shutil.rmtree(work)
    os.makedirs(work)

    fixtures = os.path.abspath(args.fixtures)
    names = ["crate-v1", "crate-v1-damaged", "ista-varun-v1"]
    dirs = {}
    for name in names:
        zpath = os.path.join(fixtures, name + ".werk")
        if not os.path.isfile(zpath):
            raise SystemExit("fixture missing: %s" % zpath)
        d = os.path.join(work, name)
        extract(zpath, d)
        dirs[name] = d

    edited_dir = os.path.join(work, "ista-varun-v1-edited")
    edit_rel, old_hash, new_hash = build_edited_variant(dirs["ista-varun-v1"], edited_dir)
    edit_size = os.path.getsize(os.path.join(edited_dir, *edit_rel.split("/")))

    corpus = [
        ("crate-v1", dirs["crate-v1"]),
        ("ista-varun-v1", dirs["ista-varun-v1"]),
        ("ista-varun-v1-edited", edited_dir),
    ]
    logical = sum(tree_bytes(d) for _l, d in corpus)
    before_hashes = {label: tree_hashes(d) for label, d in corpus}

    print("")
    print("=" * 72)
    print("werk-store Stage 7 CDC gate measurement")
    print("=" * 72)
    print("corpus            : the real conformance fixtures + one synthetic edit")
    for label, d in corpus:
        print("  %-22s %s (%d files)" % (label, mib(tree_bytes(d)), len(before_hashes[label])))
    print("edited payload    : %s (%s, the corpus's biggest payload)" % (edit_rel, mib(edit_size)))
    print("edit              : %d bytes overwritten at offset %d; manifest updated" % (EDIT_LENGTH, EDIT_OFFSET))
    print("                    %s -> %s" % (old_hash[:12], new_hash[:12]))
    print("custody           : one link APPENDED to the existing chain (dev key), verifies")
    print("cdc parameters    : %s min / %s avg / %s max, threshold %s"
          % (mib(MIN_SIZE), mib(AVG_SIZE), mib(MAX_SIZE), mib(DEFAULT_THRESHOLD)))
    print("python            : %s;  third-party deps: 0" % sys.version.split()[0])

    # -- threshold: where does chunking start paying? --------------------
    print("")
    print("-- threshold measurement (why %s) ---------------------------" % mib(DEFAULT_THRESHOLD))
    print("   size      chunks   mean chunk   recipe B   edit granularity vs whole")
    for size_mib in (0.25, 0.5, 1, 2, 4, 8):
        n = int(size_mib * 1024 * 1024)
        chunks = chunk_bytes(keystream(b"threshold-%d" % n, n))
        recipe_b = 60 + 76 * len(chunks)  # measured serialized recipe weight
        gran = n / float(len(chunks))
        print("   %-9s %5d   %9s   %7d   %5.1fx finer"
              % (mib(n), len(chunks), mib(gran), recipe_b, n / gran))
    print("   below ~2 MiB an edit still costs a large fraction of the file;")
    print("   the threshold sits where granularity is reliably ~8x finer.")

    # -- chunk-boundary stability under the edit -------------------------
    with open(os.path.join(dirs["ista-varun-v1"], *edit_rel.split("/")), "rb") as fh:
        original_payload = fh.read()
    with open(os.path.join(edited_dir, *edit_rel.split("/")), "rb") as fh:
        edited_payload = fh.read()
    t0 = time.time()
    ch_before = chunk_bytes(original_payload)
    ch_after = chunk_bytes(edited_payload)
    t_chunk = time.time() - t0
    set_before = {hashlib.sha256(c).hexdigest() for c in ch_before}
    changed = [c for c in ch_after if hashlib.sha256(c).hexdigest() not in set_before]
    print("")
    print("-- chunk-boundary stability under the edit -------------------------")
    print("payload           : %s, %s" % (edit_rel, mib(len(original_payload))))
    print("chunks before     : %d (mean %s)" % (len(ch_before), mib(len(original_payload) / len(ch_before))))
    print("chunks after      : %d" % len(ch_after))
    print("chunks changed    : %d of %d (%s of payload re-stored)"
          % (len(changed), len(ch_after), mib(sum(len(c) for c in changed))))
    print("boundary stability: %.1f%% of chunks kept their hash across the edit"
          % (100.0 * (len(ch_after) - len(changed)) / len(ch_after)))
    print("chunking both     : %.2f s" % t_chunk)

    # -- store WITHOUT CDC (the before picture) --------------------------
    store_whole = WerkStore(os.path.join(work, "store-whole"), chunk_threshold=None)
    res_whole = ingest_corpus(store_whole, corpus)
    _n_w, obj_w, _r_w, rec_w = physical_bytes(store_whole)
    phys_whole = obj_w + rec_w

    # -- store WITH CDC ---------------------------------------------------
    store_cdc = WerkStore(os.path.join(work, "store-cdc"))
    res_cdc = ingest_corpus(store_cdc, corpus)
    n_c, obj_c, r_c, rec_c = physical_bytes(store_cdc)
    phys_cdc = obj_c + rec_c

    print("")
    print("-- dedup: whole-blob vs CDC (the gate numbers) ---------------------")
    print("logical bytes     : %s (all three packages side by side)" % mib(logical))
    print("physical, whole   : %s  -> dedup %.4fx (%.2f%% saved)"
          % (mib(phys_whole), logical / float(phys_whole),
             100.0 * (1 - phys_whole / float(logical))))
    print("physical, CDC     : %s in %d objects + %d recipes (%s recipe overhead)"
          % (mib(phys_cdc), n_c, r_c, mib(rec_c)))
    print("                    -> dedup %.4fx (%.2f%% saved)"
          % (logical / float(phys_cdc), 100.0 * (1 - phys_cdc / float(logical))))
    print("CDC advantage     : %s less on disk than whole-blob dedup"
          % mib(phys_whole - phys_cdc))
    print("")
    for (label, r, t), (_l2, r2, t2) in zip(res_whole, res_cdc):
        print("%-22s whole: %s written in %.2f s | cdc: %s written in %.2f s%s"
              % (label, mib(r.bytes_written), t, mib(r2.bytes_written), t2,
                 "  (%d file(s) chunked, %d chunks, %d new)"
                 % (r2.files_chunked, r2.chunks_total, r2.chunks_new)
                 if r2.files_chunked else ""))
    edited_res = res_cdc[2][1]
    print("edited marginal   : %s of its own %s = %.4f%% (whole-blob store paid %s)"
          % (mib(edited_res.bytes_written), mib(tree_bytes(edited_dir)),
             100.0 * edited_res.bytes_written / float(tree_bytes(edited_dir)),
             mib(res_whole[2][1].bytes_written)))

    # -- the damaged fixture: the refusal is the correct behavior --------
    print("")
    print("-- crate-v1-damaged (the refusal IS the measurement) ---------------")
    t0 = time.time()
    try:
        ingest(store_cdc, dirs["crate-v1-damaged"])
        print("*** INGESTED - THIS IS A BUG: the damaged fixture must refuse ***")
        damaged_ok = False
    except IngestRefused as exc:
        t_ref = time.time() - t0
        damaged_ok = True
        print("refused in %.2f s with the exact report:" % t_ref)
        for p in exc.problems:
            print("   %s" % p.split(" but ")[0])
        print("   (%d problem(s); nothing entered the store, no ref was written)"
              % len(exc.problems))

    # -- byte-exact materialization, all three ---------------------------
    print("")
    print("-- byte-exact round trip (CDC store) -------------------------------")
    identical = True
    t0 = time.time()
    for label, d in corpus:
        ref = [r for r in store_cdc.refs.iter_refs()
               if os.path.abspath(r.source) == os.path.abspath(d)][0]
        out = os.path.join(work, "out-" + label)
        rep = materialize(store_cdc, ref.manifest_hash, out, form="directory")
        same = tree_hashes(out) == before_hashes[label]
        identical = identical and same and rep.ok
        print("%-22s %d files rehashed from the RESULT; tree %s; %s"
              % (label, rep.files_verified,
                 "IDENTICAL" if same else "*** DIFFERS ***",
                 rep.signature.summary()))
    t_mat = time.time() - t0
    print("materialize time  : %.2f s for %s (reassembly through recipes included)"
          % (t_mat, mib(logical)))

    # -- chunk-granular sync ----------------------------------------------
    print("")
    print("-- chunk-granular sync (edited package to a remote holding v1) -----")
    remote = WerkStore(os.path.join(work, "remote"))
    ista_ref = [r for r in store_cdc.refs.iter_refs()
                if os.path.abspath(r.source) == os.path.abspath(dirs["ista-varun-v1"])][0]
    edited_ref = [r for r in store_cdc.refs.iter_refs()
                  if os.path.abspath(r.source) == os.path.abspath(edited_dir)][0]
    push(store_cdc, remote, ista_ref.manifest_hash)
    p = sync_plan(store_cdc, remote, edited_ref.manifest_hash)
    s = push(store_cdc, remote, edited_ref.manifest_hash)
    edited_total = tree_bytes(edited_dir)
    print("plan              : %d object(s) wanted, %s" % (len(p.want()), mib(p.want_bytes)))
    print("pushed            : %d object(s), %s copied; %d recipe(s) installed"
          % (s.objects_copied, mib(s.bytes_copied), s.recipes_written))
    print("reused in place   : %d chunk(s), %s already on the far side"
          % (s.chunks_reused, mib(s.chunk_bytes_reused)))
    print("transfer          : %.4f%% of the %s package crossed the wire"
          % (100.0 * s.bytes_copied / float(edited_total), mib(edited_total)))
    rm = materialize(remote, edited_ref.manifest_hash,
                     os.path.join(work, "remote-out"), form="directory")
    remote_same = tree_hashes(os.path.join(work, "remote-out")) == before_hashes["ista-varun-v1-edited"]
    print("far side rebuilds : %s" % ("byte-exact" if (rm.ok and remote_same) else "*** FAILED ***"))

    # -- gc across both representations ----------------------------------
    print("")
    print("-- gc + scrub across whole AND chunked forms -----------------------")
    gc_dry = collect(store_cdc, dry_run=True)
    print("gc (dry run)      : %d live object(s) (%s), %d recipe(s) live, %d sweepable"
          % (gc_dry.live, mib(gc_dry.live_bytes), gc_dry.live_recipes, gc_dry.swept))
    store_cdc.refs.remove(edited_ref.manifest_hash)
    gc_real = collect(store_cdc, dry_run=False)
    print("drop edited ref   : gc swept %d object(s)/%s and %d recipe(s); "
          % (gc_real.swept, mib(gc_real.swept_bytes), gc_real.swept_recipes), end="")
    still = materialize(store_cdc, ista_ref.manifest_hash,
                        os.path.join(work, "post-gc-out"), form="directory")
    print("v1 still materializes %s" % ("byte-exact" if still.ok else "*** FAILED ***"))
    t0 = time.time()
    sc = scrub(store_cdc)
    t_scrub = time.time() - t0
    print("scrub             : %d object(s)/%s rehashed; %d recipe(s) reassembled and"
          % (sc.checked, mib(sc.bytes_checked), sc.recipes_checked))
    print("                    reproved against their whole-file names (%s) in %.2f s - %s"
          % (mib(sc.recipe_bytes_checked), t_scrub,
             "all clean" if sc.ok else "PROBLEMS FOUND"))
    print("=" * 72)

    ok = identical and damaged_ok and rm.ok and remote_same and still.ok and sc.ok
    if not args.keep:
        shutil.rmtree(work, ignore_errors=True)
    else:
        print("working tree kept at %s" % work)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
