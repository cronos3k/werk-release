#!/usr/bin/env python3
"""Assemble testvectors/vectors.json from the two measured runs in build/."""
import hashlib
import io
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(HERE, "build")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def ids(path):
    return [int(l.split()[1]) for l in
            io.open(path, encoding="utf-8").read().splitlines()
            if l.startswith("TOKEN")]


ck = open(os.path.join(HERE, "stories15M.bin"), "rb").read()
dim, hidden, nl, nh, nkv, vs, sl = struct.unpack("<7i", ck[:28])
hs = dim // nh
params = (vs * dim) + nl * dim + nl * dim * dim * 4 + nl * dim + \
         3 * nl * dim * hidden + dim

RUNS = [
    dict(name="once-upon-a-time", prompt="Once upon a time", steps=64,
         out="gen_msvc.txt", err="tok_err.txt",
         file="generate-once-upon-a-time.stdout.txt"),
    dict(name="the-little-robot", prompt="The little robot", steps=32,
         out="gen2.txt", err="gen2.err",
         file="generate-the-little-robot.stdout.txt"),
]

vectors = []
for r in RUNS:
    raw = open(os.path.join(B, r["out"]), "rb").read()
    lf = raw.replace(b"\r\n", b"\n")
    io.open(os.path.join(HERE, r["file"]), "wb").write(lf)
    tid = ids(os.path.join(B, r["err"]))
    vectors.append({
        "vector_id": r["name"],
        "prompt": r["prompt"],
        "steps": r["steps"],
        "temperature": 0.0,
        "decode": "greedy-argmax",
        "argv": ["<the binary you built>", "model/stories15M.bin",
                 "-z", "model/tokenizer.bin", "-t", "0.0",
                 "-n", str(r["steps"]), "-i", r["prompt"]],
        "stdout_file": r["file"],
        "stdout_bytes_lf": len(lf),
        "stdout_sha256_lf": sha(lf),
        "stdout_sha256_crlf": sha(raw),
        "stdout_text": lf.decode("utf-8"),
        "token_ids": tid,
        "token_count": len(tid),
    })

doc = {
    "schema_version": 1,
    "what_this_is":
        "The correctness anchor for this package. Build the runtime in "
        "tools/llama2c/ (see tools/llama2c/BUILD-AND-RUN.md), run each `argv` "
        "below from the extracted package root, take stdout, replace CRLF with "
        "LF, and compare against `stdout_text` or hash it against "
        "`stdout_sha256_lf`. A match means the container, the weights layout, "
        "the tokenizer layout and the whole forward pass are all right. "
        "Nothing weaker proves that: a runtime that reads the weights at the "
        "wrong offsets still emits confident text.",
    "how_to_verify": [
        "1. Build: see tools/llama2c/BUILD-AND-RUN.md section 2. There is no "
        "prebuilt binary in this package and nothing here is executed for you.",
        "2. Run vectors[i].argv with your binary in place of "
        "'<the binary you built>'. The generated text is on stdout; the "
        "'achieved tok/s' line is on stderr and is not part of any vector.",
        "3. Normalise: replace CRLF with LF. run.c writes to a text-mode "
        "stream, so an identical computation emits \\n on POSIX and \\r\\n "
        "through a Windows console. The hash is declared over the LF form; "
        "stdout_sha256_crlf records the raw Windows form of the same bytes so "
        "the normalisation itself is checkable.",
        "4. Compare against stdout_sha256_lf. That is the whole check.",
    ],
    "on_mismatch":
        "A mismatch is diagnostic, not merely a failure, and the three cases "
        "are distinguishable. (a) FLUENT ENGLISH, DIVERGING AFTER N TOKENS: "
        "floating-point reassociation. The forward pass is scalar C but a "
        "vectorising compiler may reassociate the reductions in rmsnorm, "
        "softmax and matmul, and -ffast-math will. Report N and your flags; "
        "this is an arithmetic difference, not a broken reader. (b) FLUENT "
        "ENGLISH, DIFFERENT FROM TOKEN 1: the prompt encoding differs - check "
        "the BOS token and the SentencePiece dummy-prefix space, "
        "spec/layouts/llama2c-tokenizer.layout.txt section 5. (c) GARBAGE FROM "
        "TOKEN 1: the weights are being read at the wrong offsets - check the "
        "two DEAD RoPE tables, spec/layouts/llama2c-checkpoint.layout.txt "
        "section 4.",
    "token_ids_note":
        "token_ids is the stronger anchor because integers have no newline "
        "convention. THE UNMODIFIED run.c DOES NOT PRINT THEM: they were "
        "captured by a two-line instrumentation, which travels beside this file "
        "as tokens_instrumentation.diff, a unified diff against this package's "
        "own tools/llama2c/run.c. Apply it, rebuild, and stderr carries one "
        "'TOKEN <id>' line per step. The first id is always 1 (BOS). Matching "
        "stdout_sha256_lf needs no patching and is sufficient.",
    "model": {
        "config": {"dim": dim, "hidden_dim": hidden, "n_layers": nl,
                   "n_heads": nh, "n_kv_heads": nkv, "vocab_size": vs,
                   "seq_len": sl, "head_size": hs, "kv_dim": (dim * nkv) // nh,
                   "parameters": params},
        "checkpoint_sha256": sha(ck),
        "checkpoint_bytes": len(ck),
    },
    "environment": {
        "platform": "win32",
        "os": "Microsoft Windows 10 Enterprise 10.0.19045 x64",
        "cpu": "AMD Ryzen Threadripper 3970X 32-Core Processor",
        "compiler": "Microsoft (R) C/C++ Optimizing Compiler Version "
                    "19.38.33143 for x64 (Visual Studio 2022 Community)",
        "build_command": "cl /nologo /O2 /Fe:run.exe run.c win.c",
        "binary_bytes": 218624,
        "device": "cpu",
        "note": "No GPU anywhere. A 15 M-parameter f32 model on one core, "
                "measured at 93.75 and 94.51 tokens/s by the runtime's own "
                "stderr line. Recorded because 'it matched' is only a "
                "measurement if you know against what.",
    },
    "vectors": vectors,
}

io.open(os.path.join(HERE, "vectors.json"), "w", encoding="utf-8",
        newline="\n").write(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
print("params", params)
for v in vectors:
    print(v["vector_id"], v["stdout_bytes_lf"], v["stdout_sha256_lf"],
          v["token_count"])
