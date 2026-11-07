#!/usr/bin/env python3
"""
driver_selfrun.py -- the GAP-COMPLETION round's ADAPTED self-run arm.

WHAT THIS IS, STATED BEFORE ANY RESULT. The self-run round (roundSR) proved a
stranger can BUILD AND RUN a werk package -- with two frontier agentic CLIs
that had a shell. An LM Studio model has no shell. roundOW's answer to that,
for a READING task, was "the model writes one Python program and the harness
runs it". A BUILDING task cannot be squeezed into that shape without changing
what is measured, because the interesting steps are `cl.exe` / `gcc` and an
`argv` line, not Python.

So this arm is ADAPTED, and the adaptation is the thing to be honest about:

  * The model receives, inlined, exactly what roundSR's two agents said
    unblocked them and nothing more: the zip entry listing, `README.txt`, the
    complete `MANIFEST.json`, `tools/llama2c/BUILD-AND-RUN.md`, the complete
    source of the embedded tool (`run.c`, `win.c`, `win.h`), its `tool.json`
    and run config, both layout grammars for the two foreign binary formats,
    and the package's own test vectors.
  * The model emits ONE bash script: extract, compile, invoke, and whatever
    verification it wants. It also states, in the script's own output, what it
    PREDICTS the run will produce.
  * THE HARNESS EXECUTES THAT SCRIPT. Errors come back as feedback, same loop,
    same caps.

**On the "never auto-execute" doctrine.** That doctrine is about a package's
shipped binaries: a werk package carries source and never a prebuilt artifact,
so that nothing inside a file anyone hands you runs without a human deciding
it should. This harness is that human's proxy: the source it compiles is
`run.c`, which roundSR already established is byte-identical to llama2.c
upstream and which is committed in this repository and has been read; the
script that compiles it is statically screened for network use and for paths
outside the run directory, is written to disk before it runs, and is committed
with the run. A supervised harness compiling reviewed source is not the same
act as a reader auto-executing a stranger's binary, and this file is where the
distinction is recorded rather than assumed. What CANNOT be claimed from this
arm is the roundSR claim: this is not an unsupervised stranger.

Grade: do the temperature-0 outputs match the vectors the package carries?
`grade_selfrun.py` decides that from the bytes.

Usage:
  python driver_selfrun.py --model <id> --fixture <selfrun.werk> --rundir <dir>
                           --context <tokens> [--max-iters 8] [--max-wall 2700]
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

API = os.environ.get("WERK_API", "http://127.0.0.1:1234/v1")
REQ_TIMEOUT = 1800
PROG_TIMEOUT = 1800
FEEDBACK_CAP = 12000

SYS = """\
You are a systems programmer working on a Windows machine that has Git Bash \
(so: bash, plus the usual POSIX tools), Python 3, and a C compiler toolchain. \
You cannot run anything yourself. You write ONE complete bash script; a harness \
runs it for you in a directory that contains exactly one other thing, the file \
named in the task, and shows you its stdout, stderr and exit code. Then you may \
revise.

Rules of this environment:
  * Reply with ONE fenced ```bash block containing the ENTIRE script. No \
diffs, no fragments, no "rest unchanged".
  * There is NO network. Everything must come from inside the file.
  * The script must not need any input and must print what it finds.
  * Compilers available: `gcc` (mingw-w64) may or may not be on PATH; MSVC's \
`cl.exe` may or may not be on PATH. Probe for what exists rather than assuming, \
and say in your output which one you used.
  * Before you build, PRINT WHAT YOU PREDICT the finished program will output, \
and where inside the file you got that prediction from. Then run it and compare.

When the script does everything the task asks and you are satisfied with its \
output, reply with the single line TASK COMPLETE and nothing else.
"""

TASK = """\
TASK

Here is a file: selfrun-v1.werk (in your working directory). Working only from
that file: make the language model it contains run and produce text, and verify
your result against whatever correctness information the file provides. Report
what you did.

You may read anything inside the file. You may not search the web or read
anything outside the file.

HARD CONSTRAINTS (isolation)

1. The ONLY permitted input is selfrun-v1.werk and its contents.
2. Do not read, list, glob or search any directory outside your own working
   directory.
3. Do not search the web and do not fetch any URL.
4. Recognising the format or the program from prior knowledge does NOT license
   using remembered details. Derive every rule from the file itself. If you
   need something you cannot find inside the file, REPORT that you need it.
5. Do not modify selfrun-v1.werk. Work on copies.

REPORTING

Your script must print: which files inside the package you used and which one
unblocked you; the exact build command and the exact runner invocation; what
you PREDICTED the output would be and where in the package that prediction came
from; the actual output; and the verification verdict against the package's own
correctness information, with the digests you computed.
"""


def hexdump(data, base=0):
    out = []
    for off in range(0, len(data), 16):
        chunk = data[off:off + 16]
        hx = " ".join("%02x" % b for b in chunk)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        out.append("%08x  %-47s  |%s|" % (base + off, hx, asc))
    return "\n".join(out)


def pack(fixture):
    z = zipfile.ZipFile(fixture)
    infos = z.infolist()
    T = lambda n: z.read(n).decode("utf-8", "replace")
    listing = ["%-62s %10s %12s %10s %s" % ("name", "size", "offset", "crc32", "method")]
    for i in infos:
        listing.append("%-62s %10d %12d %10s %s"
                       % (i.filename, i.file_size, i.header_offset,
                          "%08x" % (i.CRC & 0xffffffff), i.compress_type))
    items = [
        ("README.txt", T("README.txt")),
        ("ZIP ENTRY LISTING (all %d entries)" % len(infos), "\n".join(listing)),
        ("tools/llama2c/BUILD-AND-RUN.md (complete)", T("tools/llama2c/BUILD-AND-RUN.md")),
        ("tools/llama2c/tool.json", T("tools/llama2c/tool.json")),
        ("tools/llama2c-testvector-run.config.json", T("tools/llama2c-testvector-run.config.json")),
        ("tools/llama2c/win.h (complete)", T("tools/llama2c/win.h")),
        ("tools/llama2c/win.c (complete)", T("tools/llama2c/win.c")),
        ("tools/llama2c/run.c (complete)", T("tools/llama2c/run.c")),
        ("spec/layouts/llama2c-checkpoint.layout.txt (complete)",
         T("spec/layouts/llama2c-checkpoint.layout.txt")),
        ("spec/layouts/llama2c-tokenizer.layout.txt (complete)",
         T("spec/layouts/llama2c-tokenizer.layout.txt")),
        ("testvectors/vectors.json (complete)", T("testvectors/vectors.json")),
        ("testvectors/generate-once-upon-a-time.stdout.txt",
         T("testvectors/generate-once-upon-a-time.stdout.txt")),
        ("testvectors/generate-the-little-robot.stdout.txt",
         T("testvectors/generate-the-little-robot.stdout.txt")),
        ("HEX DUMP -- first 256 bytes of model/stories15M.bin",
         hexdump(z.read("model/stories15M.bin")[:256])),
        ("HEX DUMP -- first 256 bytes of model/tokenizer.bin",
         hexdump(z.read("model/tokenizer.bin")[:256])),
    ]
    # WHAT IS CUT, and the evidence for cutting it. `MANIFEST.json` (32 681 B),
    # `recipe/recipe.json` and `provenance/provenance.json` are NOT inlined.
    # roundSR recorded, for BOTH successful agents, `opened MANIFEST.json: no`
    # and `opened anything under spec/: no`; what unblocked both was
    # `tools/llama2c/BUILD-AND-RUN.md`. Inlining 33 KB that neither agent used
    # would cost a third of the window this model has to think in, and on this
    # box that window is the binding constraint (see the results file's serving
    # table). The cut is stated here and in run.json's `items` rather than left
    # as silence, which is S-GF-1's lesson. It does mean this arm exercises the
    # BUILD-AND-RUN path and not the manifest -- exactly what roundSR's own
    # verdict said its task exercised.
    head = ("===== CONTEXT PACKAGE =====\n"
            "Everything below was extracted from INSIDE the file named in the task and\n"
            "from nowhere else. You cannot read the file yourself, so this is what you\n"
            "have. The bundled reader programs under loaders/ were deliberately NOT\n"
            "included. The two large binaries appear only as hex heads; your script\n"
            "runs against the real file and can read every byte itself.\n"
            "Items: %d.\n" % len(items))
    body = "".join("\n\n===== %s =====\n%s\n" % (t, b) for t, b in items)
    return head + body, [t for t, _ in items]


def chat(model, messages, max_tokens=16384, temperature=0.2):
    payload = {"model": model, "messages": messages, "temperature": temperature,
               "max_tokens": max_tokens, "stream": False}
    req = urllib.request.Request(API + "/chat/completions",
                                 data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=REQ_TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


CODE_RE = re.compile(r"```(?:bash|sh|shell)?\s*\n(.*?)```", re.S)
NET = re.compile(r"\b(curl|wget|pip\s+install|npm\s+i|git\s+clone|nc\s|ssh\s|scp\s)\b")
ABS_OUT = re.compile(r"(?:[A-Za-z]:[\\/]|/(?:mnt|usr/local/src|etc|home)/)[^\s\"';|)]*")
ALLOW_ABS = re.compile(r"^(?:[A-Za-z]:[\\/](?:Program Files|Windows|msys64|mingw64|ProgramData)|"
                       r"/(?:usr|etc|mingw64|c/Program Files))", re.I)


def extract(text):
    best = None
    for m in CODE_RE.finditer(text or ""):
        b = m.group(1)
        if best is None or len(b) > len(best):
            best = b
    return best


def screen(src, root):
    m = NET.search(src)
    if m:
        return ("REFUSED BY THE HARNESS: your script uses %r, which reaches the network or a "
                "package index. There is none. Everything must come from the file." % m.group(0))
    for m in ABS_OUT.finditer(src):
        lit = m.group(0)
        if ALLOW_ABS.match(lit):
            continue          # a toolchain location is not a data path
        probe = lit
        mm = re.match(r"^/([a-zA-Z])/(.*)$", probe)
        if mm:
            probe = mm.group(1).upper() + ":\\" + mm.group(2)
        try:
            rp = os.path.realpath(probe)
        except Exception:
            continue
        if not (rp == root or rp.startswith(root + os.sep)):
            return ("REFUSED BY THE HARNESS: your script contains the absolute path %r, which is "
                    "outside the working directory. Use relative paths for everything that is "
                    "data." % lit)
    return None


def clip(s, cap=FEEDBACK_CAP):
    if len(s) <= cap:
        return s
    h = cap // 2
    return s[:h] + "\n...[%d chars elided by the harness]...\n" % (len(s) - cap) + s[-h:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--fixture", required=True)
    ap.add_argument("--rundir", required=True)
    ap.add_argument("--context", type=int, required=True)
    ap.add_argument("--quant", default="")
    ap.add_argument("--label", default="")
    ap.add_argument("--max-iters", type=int, default=8)
    ap.add_argument("--max-wall", type=int, default=2700)
    ap.add_argument("--max-tokens", type=int, default=16384)
    ap.add_argument("--api", default="",
                    help="OpenAI-compatible base URL for a non-localhost endpoint.")
    args = ap.parse_args()
    global API
    if args.api:
        API = args.api.rstrip("/")

    rundir = os.path.realpath(args.rundir)
    hdir = os.path.join(rundir, "_harness")
    os.makedirs(hdir, exist_ok=True)
    logf = open(os.path.join(hdir, "stdout.log"), "w", encoding="utf-8")

    def say(s):
        try:
            print(s, flush=True)
        except UnicodeEncodeError:
            enc = sys.stdout.encoding or "ascii"
            print(s.encode(enc, "replace").decode(enc, "replace"), flush=True)
        logf.write(s + "\n"); logf.flush()

    pkg, items = pack(args.fixture)
    with open(os.path.join(hdir, "context_package.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(pkg)
    say("model=%s ctx=%d package=%d chars items=%d" % (args.model, args.context, len(pkg), len(items)))

    messages = [{"role": "system", "content": SYS},
                {"role": "user", "content": TASK + "\n\n" + pkg}]
    t0 = time.monotonic()

    preflight_s, pf_tokens = None, None
    try:
        tp = time.monotonic()
        rp = chat(args.model, messages, max_tokens=1)
        preflight_s = round(time.monotonic() - tp, 1)
        pf_tokens = (rp.get("usage") or {}).get("prompt_tokens")
        say("preflight: prompt_tokens=%s cold prefill=%.1fs (%.0f tok/s)"
            % (pf_tokens, preflight_s, (pf_tokens or 0) / max(preflight_s, .001)))
    except Exception as e:
        say("preflight failed: %s" % e)

    it, outcome, detail, first_clean, no_code = 0, "unknown", "", None, 0
    history, prompt_tokens, truncations = [], None, 0
    # HARNESS DEFECT, FOUND AND FIXED MID-ARM; THE FIRST RUN WAS DISCARDED
    # BECAUSE OF IT. `subprocess.run(["bash", ...])` from a Windows Python
    # resolves "bash" against the WINDOWS PATH, which on this box finds WSL's
    # bash first -- a Linux userland with no gcc, no cl.exe and no access to
    # either. The first run's script probed `command -v cl` then
    # `command -v gcc`, found neither, and printed "No suitable compiler
    # found"; its `ls -la` shows `root root` and `drwxrwxrwx`, which is how the
    # defect was identified. Scoring that as a model failure would be exactly
    # the S-OW-5 error. The default is now the MSYS2 bash that actually has the
    # toolchain on its PATH, and the resolved interpreter is in run.json.
    bash = os.environ.get("GF_BASH", "C:/msys64/usr/bin/bash.exe")
    if not os.path.exists(bash):
        bash = "bash"

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
            outcome, detail = "api-error", "HTTP %s: %s" % (e.code, e.read().decode("utf-8", "replace")[:800])
            say("!! " + detail); break
        except Exception as e:
            outcome, detail = "api-error", str(e); say("!! " + detail); break

        ch = r["choices"][0]
        content = ch["message"].get("content") or ""
        if prompt_tokens is None:
            prompt_tokens = (r.get("usage") or {}).get("prompt_tokens")
        if ch.get("finish_reason") == "length":
            truncations += 1
        say("\n--- iteration %d (%.0fs, finish=%s, %d chars) ---"
            % (it, time.monotonic() - t0, ch.get("finish_reason"), len(content)))
        say(content[:800])
        messages.append({"role": "assistant", "content": content})

        if re.match(r"^\s*TASK COMPLETE\s*$", content, re.I) or \
           (first_clean is not None and re.search(r"\bTASK COMPLETE\b", content) and extract(content) is None):
            outcome, detail = "model-finished", "declared TASK COMPLETE after a clean run"
            break

        src = extract(content)
        if src is None:
            no_code += 1
            if no_code >= 3:
                outcome, detail = "no-program", "3 replies with no ```bash block"; break
            messages.append({"role": "user", "content":
                             "I did not find a ```bash block. Reply with ONE fenced ```bash block "
                             "containing the entire script, or the single line TASK COMPLETE."})
            continue
        no_code = 0

        for p in (os.path.join(rundir, "solution.sh"),
                  os.path.join(hdir, "solution.iter%d.sh" % it)):
            with open(p, "w", encoding="utf-8", newline="\n") as f:
                f.write(src)

        ref = screen(src, rundir)
        if ref:
            say("  >> %s" % ref)
            history.append({"iter": it, "exit": None, "refused": ref})
            messages.append({"role": "user", "content": ref + "\nRevise and send the whole script again."})
            continue

        say("  >> running solution.sh (%d chars) with %s" % (len(src), bash))
        t1 = time.monotonic()
        cenv = dict(os.environ)
        cenv["PYTHONIOENCODING"] = "utf-8"
        cenv["PYTHONUTF8"] = "1"
        try:
            p = subprocess.run([bash, "solution.sh"], cwd=rundir, capture_output=True,
                               timeout=PROG_TIMEOUT, env=cenv)
            out = p.stdout.decode("utf-8", "replace")
            err = p.stderr.decode("utf-8", "replace")
            rc = p.returncode
        except subprocess.TimeoutExpired as e:
            out = (e.stdout or b"").decode("utf-8", "replace")
            err = "TIMEOUT: killed after %d s" % PROG_TIMEOUT
            rc = -9
        dt = time.monotonic() - t1
        say("  << exit=%d in %.1fs stdout=%dB stderr=%dB" % (rc, dt, len(out), len(err)))
        say("  " + out[:1500].replace("\n", "\n  "))
        if err:
            say("  STDERR: " + err[:1000].replace("\n", "\n  "))
        history.append({"iter": it, "exit": rc, "secs": round(dt, 1),
                        "stdout_bytes": len(out), "stderr_bytes": len(err)})
        with open(os.path.join(hdir, "run.iter%d.stdout.txt" % it), "w", encoding="utf-8") as f:
            f.write(out)
        with open(os.path.join(hdir, "run.iter%d.stderr.txt" % it), "w", encoding="utf-8") as f:
            f.write(err)
        if rc == 0 and first_clean is None:
            first_clean = it

        verb = ("ran and exited 0 in %.1f s" % dt) if rc == 0 else \
               ("FAILED with exit code %d after %.1f s" % (rc, dt))
        tail = ("If this does everything the task asks, reply with the single line TASK COMPLETE. "
                "Otherwise send the whole revised script in one ```bash block."
                if rc == 0 else "Send the whole corrected script in one ```bash block.")
        messages.append({"role": "user", "content":
                         "Your script %s. Here is exactly what it printed.\n\n"
                         "--- stdout ---\n%s\n--- stderr ---\n%s\n\n%s"
                         % (verb, clip(out), clip(err), tail)})

    wall = time.monotonic() - t0
    say("\n=== outcome=%s (%s) iters=%d first_clean_run=%s wall=%.1fs ==="
        % (outcome, detail, it, first_clean, wall))
    with open(os.path.join(hdir, "transcript.json"), "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=1)
    row = {"model": args.model, "quant": args.quant, "context": args.context,
           "task": "selfrun-adapted", "kind": "selfrun", "label": args.label,
           "protocol": "inline-context + HARNESS-EXECUTED bash + error-feedback",
           "harness": "roundGF/driver_selfrun.py",
           "outcome": outcome, "detail": detail, "iterations": it,
           "first_clean_run": first_clean, "wall_s": round(wall, 1),
           "preflight_s": preflight_s, "prompt_tokens": prompt_tokens or pf_tokens,
           "package_chars": len(pkg), "items": items, "bash": bash,
           "truncated_replies": truncations, "runs": history, "rundir": rundir}
    with open(os.path.join(hdir, "run.json"), "w", encoding="utf-8") as f:
        json.dump(row, f, indent=1)
    say(json.dumps({k: v for k, v in row.items() if k != "runs"}))
    logf.close()


if __name__ == "__main__":
    main()
