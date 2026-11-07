# Stage DSV4 results — a frontier open-weights model, served by us, on our own hardware

**Author:** the DeepSeek-V4-Flash gauntlet agent.
**Owns for this wave:** `gauntlet/roundDS/` and this file. Nothing else. Another
agent is working in `gauntlet/` concurrently (`roundGF/`); `HANDOVER.md` and
`ROADMAP.md` are not touched by this agent, per `results/README.md` §2.

**Date:** bring-up 2026-08-09, runs 2026-08-10.
**Population:** open-weights, **frontier class** — same protocol as
`results/STAGE-OPENWEIGHTS-RESULTS.md` and `results/STAGE-SPECFIX-OW-RESULTS.md`,
*not* the agentic-CLI protocol of the cross-vendor round.

---

## 0a. Headline

| | |
|---|---|
| Model | **DeepSeek-V4-Flash-0731**, 284B total / 13B active MoE, **MXFP4** (its publisher's native format — zero requantisation loss) |
| Served by | **our own `llama-server`**, llama.cpp **b10333** compiled for sm_70, on **8× Tesla V100** — no vendor API, no LM Studio |
| Loaded context | **1 048 576 — the model's full nominal maximum, no KV-forced reduction** |
| Throughput | prefill **215–257 tok/s**; decode **26.3 tok/s** short, **18.75 tok/s** at ~40k depth |
| Bring-up cost | download **7 h 09 min** at 6.2 MB/s (WAN-limited); build ~25 min; **both shards re-hashed and matched the publisher's digests** |
| **Round-1 crate task** | **PASS** — both payloads byte-exact, reproduced in a clean directory |
| **Splat task** (spec-forcing) | **the package is servable here** (54 889 tokens, 70 GiB spare) where roundGF could not serve it at all; **clauses 1 and 3 pass, clause 2 fails on one sub-test** — grader `FAIL`, see S-DS-6 |
| **Envelope task** | **decoded** — `pose_count: 2` and both pose entries correct, where roundOW's best model fabricated a quaternion. First run of this task with the grammar actually in the package |
| **Adapted self-run** | **FAIL** — grade B 0 / 2, no binary; build died one `-I` short, and its own redirection hid the error |
| Spec fixes demonstrated in use | **S-OW-1** (`werk-sig/1` built to spec, Ed25519 from scratch), **S-OW-2** (`payload_file` honoured), **§12.2** (`unverified`, **0 false tampering alarms in 4 runs**) |
| **New spec/fixture bugs found** | **1 real one — S-DS-7**, a wrong `input_hash` in `mini-v1.werk` that has been punishing correct readers for as long as the fixture has existed |
| Runs discarded ungraded, harness defect, kept | **1** (S-DS-5) |
| Instrument defects found | **3** — S-DS-5 (extractor), S-DS-6 (grader), S-DS-8 (the envelope task carries its own answer key) |
| Findings | **S-DS-1 … S-DS-8** |

**The one-sentence version.** The empty corner of the capability-by-provenance
grid is filled — a frontier model that is also a file on a disk reads the format
byte-exact and decodes both of its custom binaries — and the round's three
sharpest results are not about the model at all: **the specification's travelling
weight is affordable and the invoice is in VRAM; the spec fixes the weak
implementers ignored are read and used by a strong one; and the two things
actually wrong here were a fixture and two instruments.**

---

## 0. Why this row exists

The rounds so far cover two corners and leave the interesting one empty:

| | commercial API | open weights |
|---|---|---|
| **frontier capability** | cross-vendor round (OpenAI, Moonshot), agentic CLI | **empty — this round** |
| **small / local** | — | open-weights round + post-fix arm (4B–30B), LM Studio |

The open-weights round's verdict was that implementer diversity is "materially
reduced ... **not** extended downward". The complementary gap is upward: every
*frontier* implementer tested so far was somebody else's hosted model behind
somebody else's API. A format whose premise is that a stranger can read the file
decades from now wants at least one data point where the reader is **both**
frontier-capable **and** a file on a disk that we loaded ourselves.

So: no vendor API, no LM Studio. Our GPUs, our build of `llama-server`, our
weights, our port.

---

## 1. Bring-up

### 1.1 Host selection — measured, both candidates checked

Two lab hosts were reachable; neither needed powering on (confirmed by Gregor,
who pinged both).

| | **<lab-gpu-host>** (<lan-ip>) | **v100** (<lan-ip>) |
|---|---|---|
| GPUs | 2× RTX 3090, 4× RTX A5000, 1× A6000, 1× Quadro RTX 8000 | **8× Tesla V100-SXM2-32GB** |
| total VRAM | ~240 GB | **256 GB** |
| **free** VRAM | **188 856 MiB (~198 GB)** — two A5000s hold a running vLLM vision service (PID 4173351/4173352, 21 GB each, port 8102) | **257 416 MiB (~270 GB)**, **zero competing tenants** |
| compute capability | 8.6 / 8.6 / 7.5 (RTX 8000) | 7.0 (Volta) uniformly |
| CUDA toolkit present | `/usr/local/cuda-12.6` | `~/cuda12` = **12.8.61** |
| driver | — | 580.173.02 (CUDA 13.0 capable) |
| free disk | 4.4 T on `/` | 795 G on `/` (ext4), 2.8 T on `/media/gregor/m4tx` (**ntfs3 — see §1.5**) |
| system RAM | 503 G | 503 G |

**v100 chosen.** More free VRAM, uniform topology, and — decisive — **no
competing tenant**, so nothing this round does can degrade the vLLM vision
service on <lab-gpu-host>. <lab-gpu-host> remains the fallback. The Volta caveats were checked, not
assumed: no BF16 and no FP8 tensor cores, which matters for nothing here because
llama.cpp dequantises MXFP4 through the **DP4A** path
(`mmq_get_dp4a_tile_x_sizes(GGML_TYPE_MXFP4, …)` in `ggml/src/ggml-cuda/mmq.cuh`),
available since sm_61. The MMA tile constant next to it is commented "Blackwell";
the DP4A fallback is what Volta uses.

### 1.2 Model and quant — computed against measured free VRAM

Nothing matching DeepSeek-V4 existed on either box before this round
(`find` over `/mnt/sda1`, `/mnt/sdc1`, `/home` on <lab-gpu-host> and `/media`, `/home` on
v100: the only hit was an empty 12 KB HF-cache stub,
`~/.cache/huggingface/hub/models--deepseek-ai--DeepSeek-V4-Flash/refs/main`, with
no blobs). It had to be downloaded.

Base model: **`deepseek-ai/DeepSeek-V4-Flash-0731`** — `DeepseekV4ForCausalLM`,
**284B total / 13B active**, MoE with 256 routed + 1 shared expert, 6 experts per
token, 43 layers, hidden 4096, vocab 129 280, `max_position_embeddings`
1 048 576 with YaRN (factor 16, original max 65 536). Latent/compressed attention
(q_lora_rank 1024, o_lora_rank 1024, kv heads 1, head_dim 512). Weights are
published **FP8 with FP4 expert dtype** — i.e. the experts are natively 4-bit.

Quant candidates, sizes measured from the HF API rather than quoted:

| repo | quant | bytes |
|---|---|---:|
| `ggml-org/DeepSeek-V4-Flash-0731-GGUF` | **MXFP4** | **154 991 539 328** (2 shards) |
| `ggml-org/…` | Q2_K | 117.3 GB |
| `ggml-org/…` | Q2_K_S | 98.6 GB |
| `unsloth/DeepSeek-V4-Flash-0731-GGUF` | UD-IQ4_XS / UD-IQ4_NL | 136.7 GB |
| `unsloth/…` | UD-Q3_K_M | 98.8 GB |
| `unsloth/…` | UD-IQ3_XXS | 104.2 GB |

**MXFP4 chosen.** It is the *native* format of the published experts, so it is
the only option on the list that costs **zero requantisation loss**; and 155 GB
of weights inside 270 GB of free VRAM leaves ~110 GB for KV cache and compute
buffers, which is what Gregor's instruction to spend the headroom on "a bigger
quant AND max context" asks for. The smaller K-quants would have downloaded
faster and been strictly worse; bartowski's note that MXFP4 "does not quantize
properly into other K-quants" is a further argument against requantising a
frontier model for a row that is *about* frontier capability.

Pinned by publisher digest, verified after download (§1.6):

```
DeepSeek-V4-Flash-0731-MXFP4-00001-of-00002.gguf          5 250 752 B
  sha256 b413152cfc2e1b14d07dbe53191cf1691030e25cc38f2730c4726f4a29057345
DeepSeek-V4-Flash-0731-MXFP4-00002-of-00002.gguf    154 986 288 576 B
  sha256 342f3acc1921bedf9913bc3059128aa19b6dc29b1d554d4e4db5e57ab9c0fd88
```

### 1.3 Serving stack — which of the three, and why

The instruction's preference order was (a) llama.cpp `llama-server` built or
downloaded on the box, (b) Gregor's `cronos3k/llama-cpp-python-standalone`,
(c) LM Studio headless as a last resort.

**(a) was used, built from source.** Reasons, in order:

* There is **no prebuilt Linux CUDA release asset**. `b10333`'s asset list has
  ubuntu x64 (CPU), arm64, s390x, vulkan, sycl, rocm and openvino builds, and
  CUDA only for Windows. A CUDA build on Linux is a source build or nothing.
* Volta needs **CUDA 12.x**: CUDA 13 dropped sm_70, and the box's driver
  advertises 13.0 while `~/cuda12` is 12.8.61. A generic binary would not have
  helped anyway.
* `deepseek4` is a *new architecture* — upstream PR #24162, merged 29 June 2026,
  adding `LLM_ARCH_DEEPSEEK4` and `src/models/deepseek4.cpp`. Both pre-existing
  checkouts on the lab boxes predate the fixes that followed it (v100's
  `~/llama.cpp` is April 2026 and has no `deepseek4` at all; <lab-gpu-host>'s
  `~/llamacpp-cuda` is 1 July 2026 and has the file but not the August APE
  fix). A current build was required, not optional.

**(b) was not used, and the reason is size, not doubt.**
`/mnt/sda1/AI/llama-cpp-python-standalone` is present on <lab-gpu-host>.  It is a Python
binding layer over llama.cpp; it does not remove the need for a current
CUDA-enabled llama.cpp built for sm_70, it adds a binding on top of one. For a
155 GB model split over eight GPUs, the thing that has to be right is the
llama.cpp build, and `llama-server` already exposes the OpenAI-compatible `/v1`
the harness speaks. Using the standalone here would have added a layer without
changing what is proven. **Recorded as a deliberate choice so it can be
revisited**, not as a failure of the repo.

**(c) LM Studio was not used at all.** That is the point of the round: the
open-weights round measured LM Studio's serving stack as much as it measured
models (S-OW-5, two serving-stack failures). This row is served by a binary we
compiled.

### 1.4 The build

```
host    v100
source  ggml-org/llama.cpp, tag b10333 == commit 08659901c (2026-08-09)
        checked out as a git WORKTREE at <user-home>/dsv4/llamacpp-dsv4
        so Gregor's own ~/llama.cpp working tree is untouched
toolkit ~/cuda12/bin/nvcc, CUDA 12.8.61; gcc 11.4.0; cmake 3.x from ~/.local/bin
cmake   -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=70 -DLLAMA_CURL=OFF
        -DCMAKE_BUILD_TYPE=Release -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_TESTS=OFF
        -DCMAKE_EXE_LINKER_FLAGS=-L$HOME/cuda12/targets/x86_64-linux/lib
        -DCMAKE_SHARED_LINKER_FLAGS=-L$HOME/cuda12/targets/x86_64-linux/lib
build   cmake --build build -j 40      (96 cores available)
result  build/bin/llama-server, version 10333 (08659901c), 8/8 V100s detected
```

**One real build failure, and it was ours, not upstream's.** The first configure
omitted the CUDA library path and every dependent target failed to link with
`undefined reference to cudaGetErrorString@libcudart.so.12`: `libggml-cuda.so`
itself built fine, but `ld` could not find the `libcudart.so.12` *file* while
resolving that shared library's own `DT_NEEDED`, so the versioned symbol
references could not be checked. Adding
`-L$HOME/cuda12/targets/x86_64-linux/lib` to both linker-flag variables fixed
it. Recorded because it is exactly the class of thing that gets mis-reported as
"the model does not work on this hardware".

### 1.5 The storage trap, recorded because it cost an hour

The first download and the first build both went to `/media/gregor/m4tx`, which
is **`ntfs3`**, and both were lost. The failure mode is nasty: `curl` wrote,
`df` correctly showed the volume filling (860 G → 864 G), the writing processes
held valid open file descriptors on the right paths — and `ls` and `find` showed
the directory as **empty**, so no progress could be verified. Shortly after, the
mount began returning `Input/output error` on `rm` and `mv`, and the build tree
on the same volume became unreadable mid-compile.

Both were restarted on **ext4** (`<user-home>/dsv4`, 795 G free) and behaved
normally from then on. **Do not put a multi-hour download or a build tree on the
ntfs3 mount on v100.**

### 1.6 The download

No prebuilt fast path was available: single-stream `curl` from
`huggingface.co` measured **3.5–4.2 MB/s** on both boxes, and `hf download`
(huggingface_hub 1.15/1.8, Xet) was slower still in a 90 s probe. Eight parallel
range requests against the resolved CDN URL measured **~6.4 MB/s aggregate** —
i.e. the WAN link, not HF, is the ceiling (~50 Mbit/s).

So the fetch is a small resumable parallel-range script, `~/pget.sh` on v100:
24 byte-ranges in flight, each `curl -r`, append-and-resume per part from the
part file's current size, then `cat` in order and check the total size against
the publisher's byte count before deleting the parts.

| | |
|---|---|
| destination | `<user-home>/dsv4/` (ext4) |
| sustained rate | **6.17–6.35 MB/s** measured over 3 and 4 minute windows |
| total bytes | **154 991 539 328**, assembled and size-checked |
| wall clock | **16:34 → 23:43 = 7 h 09 min** |
| digests | both shards **re-hashed on the box after assembly and matched the publisher's LFS oids** — `b413152c…` and `342f3acc…` (§1.2) |

**Not downloaded:** the DSpark speculative-decoding module
(`dspark-DeepSeek-V4-Flash-0731-MXFP4.gguf`, 10.8 GB, ~1.9× decode speedup per
upstream PR #25784). At 6 MB/s it costs another ~30 minutes of the same link the
main weights are using, and the round's numbers are wall-clock-comparable
without it. Recorded as available headroom, not as something tried and rejected.

### 1.7 Port

Checked free on v100 before binding (`ss -ltn`: only 22, 53, 111, 139, 445, 631,
3350, 3389 were listening). **8123** chosen, 8124/8125 confirmed free as
fallbacks. None of the reserved lab ports (8100/8101/8102/8200/8500/8502/8506/
8510/8511/8514) is touched, and 8102 — the <lab-gpu-host> vLLM vision service — is on a
different host entirely and was never contacted.

### 1.8 The harness, and the bug this round inherited and did not keep

`roundDS/driver.py` began as a byte copy of `roundOW/driver.py` plus one flag.
While it was waiting for the weights, the gap-completion round (commit
`b91aced`, `gauntlet/roundGF/`) filed **S-GF-1**: `pick()`'s section selector was

```python
n = re.match(r"^[#\s]*(\d+)\.", h)
```

which anchors at the start of the whole stripped heading. `MINI-SPECS`
headings look like `## 5. zip` and matched. A **layout-grammar heading is three
lines** with rules of dashes above and below, so the stripped heading starts
with a dash, `re.match` failed for **every section of every `.layout.txt`**, and
`pick()` returned the empty string — while the caller still emitted the
`===== FILE spec/layouts/ENVELOPE.layout.txt -- SECTIONS 0 to 7 ONLY =====`
banner and still counted the item as **INCLUDED**. Nothing in the package
header, the console or `run.json` said anything was missing.

**`roundDS/driver.py` was therefore rebased onto `roundGF/driver.py`** — which
carries the fix (GF-4), plus GF-2 (`PYTHONIOENCODING=utf-8` for generated
programs, per S-SFX-4) and the `gsplatmini` packer — and the two roundDS changes
were re-applied on top: **DS-1** the `--api` flag, **DS-2** the `selfrun` packer.

Measured effect on this round's own packages, before and after the fix:

| package | chars before | chars after | layout sections actually present |
|---|---:|---:|---:|
| `mini` (round-1 task **and** envelope task) | 103 573 | **127 814** | **0 → 8** |
| `gsplatmini` (splat task) | — | 166 642 | **25** |
| `selfrun` (adapted arm) | 92 990 | 92 990 | n/a — its two grammars are inlined whole, never section-picked |

Verified by grepping the packed text: the mini package now contains `WKRP`, the
envelope grammar and its `header map` section; the gsplatmini package contains
`WKGS`, `WKPC` and the envelope.

**This is why this round's envelope row matters beyond the model.** Every
envelope-task run in the open-weights round and the post-fix arm was scored
against a package that did not contain the envelope grammar at all — the models
were asked to implement a binary format from a banner announcing a grammar that
had been silently replaced by nothing. The 0/2 stands as a measurement of *that*
package. **The row below is the first envelope run for which the implementer
actually received the grammar**, and it is labelled as such rather than compared
straight across.

The 35 000-token package budget is consequently exceeded, deliberately and per
roundGF's ruling for this round ("it may exceed 35k — record the size"). The
true token counts are the API's own `prompt_tokens`, recorded per run in §2.

### 1.9 Serving parameters, loaded context, and the sanity check

```
systemd-run --user --unit=dsv4-server --collect bash -c '
  export LD_LIBRARY_PATH=$HOME/cuda12/targets/x86_64-linux/lib:$LD_LIBRARY_PATH
  export CUDA_DEVICE_ORDER=PCI_BUS_ID
  <user-home>/dsv4/llamacpp-dsv4/build/bin/llama-server \
    -m <user-home>/dsv4/DeepSeek-V4-Flash-0731-MXFP4-00001-of-00002.gguf \
    --host 0.0.0.0 --port 8123 -ngl 99 -c 1048576 --parallel 1 \
    --jinja --reasoning-format none --alias DeepSeek-V4-Flash-0731 \
    > <user-home>/dsv4/server.log 2>&1'
```

A **`systemd-run --user` transient unit**, per the house pattern, so closing the
SSH session does not kill the server. Only shard 1 is named: llama.cpp follows
`split.no`/`split.count` in the GGUF metadata and opens shard 2 itself.

**Loaded context: 1 048 576 — the model's full nominal maximum, with no
KV-cache-forced reduction.** This was measured, not assumed, and it took two
loads:

| loaded `n_ctx` | VRAM in use, summed over 8 GPUs | free VRAM left |
|---:|---:|---:|
| 524 288 | 169 166 MiB (165 GiB) | 88 250 MiB (86 GiB) |
| **1 048 576** | **185 564 MiB (181 GiB)** | **71 852 MiB (70 GiB)** |

Doubling the window cost 16 398 MiB, so the KV cache for the whole 1 M window is
about **33 GiB** — far below the naive `43 layers × (512 + 512) × 2 B` = 86 KB/token
estimate (which would have been 92 GB), because `deepseek4` is a
latent/compressed-attention model with a 128-token sliding window on most layers
(`deepseek4.attention.sliding_window = 128`, `attention.compress_ratios` alternating
4/128). **The first load at 524 288 was the conservative attempt; it fit with
room, so the second load took the model's whole native window.** 1 048 576 is
~24× the largest package this round sends.

Two flags are worth naming because they are the difference between measuring
the model and measuring the serving stack:

* **`--reasoning-format none`.** DeepSeek-V4-Flash is a reasoning model. With
  llama.cpp's default under `--jinja`, the thinking channel is split out into
  `reasoning_content` and `content` can come back **empty** — which is exactly
  S-OW-5(a), the failure that cost `glm-4.7-flash` its first attempt in the
  open-weights round. Set to `none`, the whole reply including the `<think>`
  block lands in `content`, the harness's `extract_program()` finds the fenced
  block, and no model is scored a non-answerer for a serving default.
* **`--parallel 1`**, plus this being the only client of the endpoint: **one
  request in flight at any moment**, Gregor's standing order.

**Model load time: 54 s** (the weights were still in page cache from the
download; 503 GB of RAM on the box). A cold load off disk reads at ~150 MB/s
measured, i.e. ~17 min.

**Sanity check, from the Windows box over the LAN:**

```
GET  /v1/models   -> id "DeepSeek-V4-Flash-0731"
POST /v1/chat/completions, 19-token prompt, 300 tokens out
  -> 13.2 s wall, predicted 26.3 tok/s
```

| | |
|---|---|
| exact model id | **`DeepSeek-V4-Flash-0731`** |
| quant | **MXFP4** (`general.file_type` 38), 284B total / 13B active, 256 experts + 1 shared, 6 used per token, 43 layers |
| loaded context | **1 048 576** |
| decode | **26.3 tok/s** |
| endpoint | `http://<lan-ip>:8123/v1`, LAN, no API key |

---

## 2. The runs

### 2.0 Protocol, and the one thing about it that is not comparable

`gauntlet/roundDS/run_one.sh`, `roundDS/driver.py` (§1.8), **serial — one
request in flight at any moment**, `--parallel 1`, artifact grading by
`roundOW/grade.py` and `roundGF/grade_gsplat.py`, **8 feedback iterations or
2 700 s**, generation cap **16 384 tokens**, `--package-ctx 131072`. Those are
roundOW's and roundGF's numbers, unchanged, so the caps are comparable.

**What is NOT comparable, and it is the harness's fault rather than the
model's: the generation cap is the binding constraint here, not the iteration
cap.** Decode was measured at **26.3 tok/s on a short prompt and 18.75 tok/s at
~40 000 tokens of context depth** (llama.cpp's own `tg_3s`). A full
16 384-token reply therefore costs **~875 s**, so the 2 700 s wall admits about
**three replies, not eight**. Every run below ends on `wall-cap`, and the
iteration counts are not evidence that the model ran out of ideas. This is a
real, quantified property of self-hosting a 284B model on Volta, and it is
recorded rather than fixed mid-round by raising a cap.

### 2.1 Round-1 crate task — `PROMPT-round1task-mini.txt` on `mini-v1.werk`

**PASS.** Graded by artifact, then reproduced in a clean directory containing
only the fixture.

| | |
|---|---|
| fixture | `gauntlet/roundOW/mini-v1.werk`, `f7bdcc85…0947e9837` |
| package | **127 814 chars, 18 of 18 items, nothing omitted** |
| package, the model's own tokenizer | **39 351 `prompt_tokens`** (3.31 chars/token) |
| cold prefill of the package | **165.4 s, 238 tok/s** |
| iterations | **4** (cap 8) |
| first clean run | **iteration 2** |
| wall | **2 991.2 s**, of which 165.4 s preflight |
| outcome | `wall-cap` |
| **grade A — artifact hashes** | **matched = 2, mismatched = 0, unmatched = 0** |
| **grade B — clean re-run** | **reproduced, matched = 2** |

```
game.glb          eee8b3cbc87703fc… == declared   [geometry/game.glb]
crate-impact.wav  1e634f03aebdb0ee… == declared   [audio/sfx/crate-impact-hard-surface.wav]
```

**The same two digests as rounds 1–3, the cross-vendor round, the open-weights
round and its post-fix arm** — now produced by a self-hosted frontier
open-weights model.

**Iteration by iteration**, because the shape matters more than the pass:

| iter | reply | program | result |
|---:|---|---:|---|
| 1 | 48 594 chars, `finish=stop` | 14 141 chars | `exit 1` — `KeyError` from `zf.read(path)` on a path it had assembled rather than read |
| 2 | 17 827 chars, `finish=stop` | 14 655 chars | **`exit 0`, 11 957 B of stdout, both payloads written byte-exact** |
| 3 | 64 381 chars, **`finish=length`** | — | **no program extracted** — the reply was cut mid-fence |
| 4 | 64 513 chars, **`finish=length`** | — | **no program extracted** — same |

**Iterations 3 and 4 produced nothing, and not because the model had nothing to
say.** It had `exit 0` and correct digests in front of it and was doing exactly
what the protocol asks — auditing its own work. Its iteration-3 reasoning opens:

> "The program ran but there are issues: 1. It read `loaders/` files … during
> hash verification … but the report says 'We did not read the loaders/ source
> files' which is false. We need to correct the report. … we should be honest in
> report."

It then spent the rest of its budget re-emitting the whole 14 kB program with
the correction, hit 16 384 tokens mid-block, and the harness — correctly —
found no closed ```` ```python ```` fence. Twice. **The model was penalised two
iterations for volunteering an honesty fix to its own report.** That is S-DS-3.

**Three things this program did that no previous open-weights model did.**

1. **It implemented Ed25519 from scratch** — `point_decompress`, `point_add`,
   `point_double`, `point_mul`, `point_eq`, `ed25519_verify` — in pure Python,
   with no library.
2. **It built the signed message correctly.** `build_message()` emits the six
   fields `werk-sig/1`, `manifest_sha256`, `prev_entry_sha256`, `signed_at`,
   `signer.uri`, `signer.kind`, LF-joined, exactly as `MINI-SPECS` §12.1
   specifies. **The S-OW-1 spec fix was read and used.**
3. **It resolved `primary.sound` through `payload_file` and `role`,** not
   through `files[0]`:

   ```python
   if f.get('role') == 'best' or f['path'].endswith('.wav'):
       if 'payload_file' in ver:
           if f['path'] == ver['payload_file']:
   ```

   **The S-OW-2 fix was read and used**, and the WAV came out rather than the
   descriptor.

**And its signature verdict was `unverified`, not `present-and-invalid`.** Its
own curve arithmetic had a bug (`not enough values to unpack (expected 4, got
2)`), it said so, and it declined to render a verdict it had not earned. **Zero
false tampering alarms** — the behaviour `MINI-SPECS` §12.2 was written to
produce, now demonstrated by a model whose failure was in the primitive rather
than in the knowledge.

**One thing it wanted and could not get**, in its own words in `REPORT.md`:

> "We wanted the definition of `spec_sha256` (what exactly it hashes) … We could
> not get them from the file (the relevant section was not in the context we
> had). We attempted to derive it by hashing `spec/` files in various orders;
> result: unverified."

That is **S-DS-4**, and it is the same shape as S-OW-1: a field the manifest
declares, whose construction rule lives in a document that does not fit the
travelling budget.

### 2.2 Splat task — the cell that was "not servable", and the attempt that was not a result

`gauntlet/roundGF/PROMPT-gsplattask.txt` **byte-identical**, on
`fixtures/gsplat-v1.werk` (`ede0aee6…`), through roundGF's `gsplatmini` packer,
at roundGF's caps.

#### 2.2.1 The hardware result, which is independent of the model's

roundGF's coverage matrix records the local-model spec-forcing cell as
**"not servable — a 65 775-token package on a 24 GB card"**, with three of five
rostered models never run for that reason and a fourth measured collapsing
13.7× (3 751 → 274 tok/s) when the KV cache stopped fitting.

Measured here:

| | roundGF, 24 GB card | **this round, 8× V100** |
|---|---|---|
| package | 166 642 chars | **166 642 chars — the same package** |
| package, model's own tokenizer | 55 376 – 65 775 tokens | **54 889 `prompt_tokens`** |
| servable? | **no** for 3 of 5 models | **yes** |
| cold prefill of it | 274 tok/s (collapsed) on the one 30B that was probed | **255.6 s at 215 tok/s**, no collapse |
| VRAM headroom while serving it | none | **70 GiB spare** on top of 144 GiB of weights |

**The constraint roundGF hit was hardware, and it is now quantified from the
other side.** 54 889 tokens of travelling specification is not an unreasonable
amount of context — it is an unreasonable amount of context *on 24 GB*. The
price the format pays for carrying its own specification is payable; it is
payable in VRAM, and the invoice is about 200 GB if you also want a frontier
implementer. That belongs in the paper next to the property.

#### 2.2.2 Attempt 1 — HARNESS-CORRUPTED, NOT GRADED, and kept

`_discarded-splat-harness-corrupted/`. Recorded rather than scored, exactly as
S-OW-5 requires and as roundGF did with its own two discarded runs.

| iter | reply | extracted | result |
|---:|---|---:|---|
| 1 | 66 433 chars, `finish=length` | 3 161 chars (a stub from an earlier fence) | `exit 0`, **0 B stdout** |
| 2 | 22 979 chars, **`finish=stop`** | 18 441 chars | `exit 1` — `SyntaxError: unterminated string literal, line 488` |
| 3 | 70 230 chars, `finish=length` | 937 chars | `exit 1` |
| 4 | 22 269 chars, **`finish=stop`** | 18 084 chars | `exit 1` — **the identical 178-byte SyntaxError** |

Outcome `wall-cap`, 4 iterations, wall 2 969.5 s.

**The two complete replies were destroyed by the harness, and it is provable
from the committed transcript.** `extract_program()`, inherited unchanged from
`roundOW`, ended a fenced block at the **first** ```` ``` ```` anywhere in the
reply — including one inside a Python string literal. The splat task asks the
model to write a `REPORT.md` **quoting the embedded tools' source**, so its
program builds markdown and contains a line appending a literal triple-backtick.
Re-running both extractors over the *same stored reply*:

```
old regex -> 18 441 chars, ends '...report_lines.append("' , SyntaxError line 488
new regex -> 21 924 chars, PARSES
```

**The model wrote a syntactically valid program and the harness handed it back a
SyntaxError that is indistinguishable from its own defect** — twice, identically.
That is **S-DS-5**. Fixed as **DS-3** (a closing fence must start its own line),
regression-checked against the ordinary case and against every reply already on
disk — the round-1 pass is unaffected — and the splat task re-run fresh.

**No pass rate is reported for attempt 1 and none is implied.**

#### 2.2.3 The retry — the first open-weights model to decode the splat payload

Fresh run, DS-3 in place, everything else identical.

| | |
|---|---|
| outcome | **`model-finished`** — declared TASK COMPLETE after a clean run |
| iterations | **2** |
| **first clean run** | **iteration 1** |
| wall | **507.5 s** |
| artifacts | `REPORT.md`, 154 983 chars |

**Grade, by `roundGF/grade_gsplat.py` unmodified**, which derives ground truth
from the fixture itself every time rather than hard-coding it:

```
ground truth: count=281498  point[0] pos = -0.06007473 1.62525749 0.93507129  col = 39 19 6

 1  integrity: sha-256 named and a verification verdict : True
 2  point count 281498 present                          : True
    point[0] position triple present                    : True
    point[0] colour triple present                      : False
 3  tools named    : werk-gsplat True, werk-pointcloud True, splat-to-ply True
    tool paths     : all True
    source quoted  : all True

VERDICT (clauses 2 and 3, the spec-forcing ones): FAIL
```

**Clause 3 is a clean, unambiguous pass** — all three embedded tools named, all
three paths correct, and a verbatim ≥40-character line of each tool's real
source quoted. **Clause 1 passes.** The count `281498` is right, and it is right
**twice, independently**: the program decoded it from the WKGS envelope *and*
from the WKPC point cloud and cross-checked them —

> `Point count: 281498 (from WKGS), 281498 (from WKPC)`
> `First 100 points match between WKGS-derived and WKPC: True`

The first point's position is exact. **This is the first open-weights run in any
round that actually decoded a werk binary envelope** rather than fabricating
values (roundOW's `qwen3-coder-30b` printed
`71554213196777853550592.0000` for a quaternion) or never opening the file
(roundGF's two attempts).

**The single failing sub-test, stated precisely and not argued away.** The
grader looks for the colour triple `39 19 6`. The report gives, under a column
it labels `rgb_linear` and a heading *"linear sRGB, from WKGS DC band"*:

| | reported | × 255 | ground truth |
|---|---|---|---|
| r | 0.152941 | 39.0000 | 39 |
| g | 0.074510 | 19.0001 | 19 |
| b | 0.023529 | 5.9999 | 6 |

The uint8 form appears nowhere in the artifact. So the model recovered the
**identical values** and stopped one quantisation step short of WKPC's storage
representation — the grader itself performs that quantisation when it derives
ground truth ("colours recomputed from sh-dc: 281498 / 281498 match").

**Two readings, and this agent does not get to pick.** Either (a) "the colours
it contains" means the bytes WKPC contains, the model did not produce them, and
`FAIL` stands; or (b) the task asks for the colours and the model produced them
in the linear-float form `gsplat.layout` §5 defines, and the grader is testing a
storage representation rather than a value. **Filed as S-DS-6 for Gregor's
ruling. The grader's verdict as run — FAIL — is what is recorded in the tables,
and the grader was not modified after seeing the result.**

### 2.3 Envelope task — the roundOW `0 / 2` row, re-run with the grammar actually present

`gauntlet/roundOW/PROMPT-envelopetask-mini.txt`, unchanged, on `mini-v1.werk`.
**This is the first run of this task in any round where the package contained the
envelope grammar** (§1.8).

| | |
|---|---|
| package | 127 814 chars, 18 of 18 items, **39 337 `prompt_tokens`** |
| cold prefill | **165.2 s, 238 tok/s** |
| **first clean run** | **iteration 1** |
| artifacts | `REPORT.md`, 15 174 chars |

**It decoded the envelope.** From the program's own output:

```
file: poses/rest.wkrp      magic: WKRP     envelope version: 1
kind: core.pose.rest
pose_count: 2        contact_count: 7      trials: 4096
floor_normal: [0.0, 1.0, 0.0]   settle_epsilon_m: 0.0005   merge_angle_deg: 5.0

pose 0: (1.000000, 0.000000, 0.000000, 0.000000)  contacts[0:4)  p=0.620000  area=0.250000
pose 1: (0.707107, 0.707107, 0.000000, 0.000000)  contacts[4:7)  p=0.380000  area=0.105000
    contact 0: (-0.250000, 0.000000, -0.250000)   …
```

Every value checks out against the package's own annotated hex decode —
including the raw little-endian float bytes `52 b8 1e 3f` = 0.62 and
`00 00 80 3e` = 0.25. **`pose_count: 2` is exactly what roundOW's strongest
model failed to report**, having instead fabricated
`71554213196777853550592.0000` for a quaternion component.

#### 2.3.1 The answer-key hazard, checked before the result was believed — S-DS-8

**`poses/rest.wkrp` is byte-identical to `spec/examples/restposes.example.wkrp`**
(both 560 B, both `6c2c44d5…`), and S-OW-3's fix inlines that example's complete
annotated decode — *including its decoded header map* — into the package. So
since the post-fix arm, **the header clause of the envelope task has carried its
own answer key in the prompt.** That is roundGF's caught-grader problem in a new
place, and it had to be excluded before this row could be believed.

Checked, against the exact inlined package text:

| value the program printed | present in the inlined package? |
|---|---|
| `"pose_count": 2`, `"contact_count": 7`, `trials 4096` | **yes** — echoable |
| quaternion `0.707107` | **no** |
| probabilities `0.620000`, `0.380000` | **no** |
| support areas `0.250000`, `0.105000` | **no** |
| contact coordinates `-0.250000`, `0.210000` | **no** |

And the program is a real decoder, not a printer: **8 `struct.unpack` calls**, the
`WKRP` magic checked, `payload_origin` and `sections` walked.

**Verdict: the decode is genuine.** The header could have been echoed; the pose
entries could not, and they are correct. **But the task is now compromised as an
instrument** and the next round must point it at a WKRP payload that is *not* the
worked example. Filed as **S-DS-8**.

#### 2.3.2 A real defect in a fixture, found by the model and independently confirmed — S-DS-7

The program reported, among its integrity checks:

> `input_hash checks: 2` … `input_hash: FAIL: input_hash mismatch rest-poses`

`MINI-SPECS` §11 documents `input_hash` with an executable statement *and* a
worked example, and the rule is inlined in the package, so this is a claim the
model was equipped to make. **It is right.** Recomputed independently here,
straight from the documented rule, over every fixture in the repository:

| fixture | nodes with `input_hash` | verifiable | **mismatched** |
|---|---:|---:|---|
| `fixtures/crate-v1.werk` | 25 | 25 | **0** |
| `fixtures/gsplat-v1.werk` | 3 | 3 | **0** |
| **`gauntlet/roundOW/mini-v1.werk`** | 5 | 2 | **1 — `rest-poses`** |

`rest-poses` declares `input_files: ["geometry/game.glb", "physics/bounds.json"]`
and `input_params: {}`; the documented construction over its own declared
digests yields `4b91ccbb…`, and the manifest declares `60e08ed1…`. Six
construction variants were tried (both input orders × raw digest bytes / hex
text / whole file bytes, with `{}` and with empty tail) and **none** reproduces
the declared value. The sibling node `bounds` in the same fixture verifies, so
neither the rule nor this re-implementation is at fault.

**It is a defect in the mini fixture only, not in the shipped fixtures.**
`build_mini_fixture.py` re-signs, re-converges `preview_prefix_bytes` and
recomputes `spec_sha256` — and does **not** recompute `input_hash` after the
reduced build changes what the node's inputs hash to.

**Why it matters more than one wrong hex string:** `mini-v1.werk` is the fixture
every open-weights round has used. For as long as it has existed, **a reader that
implemented `input_hash` correctly was told it had found damage in an intact
package** — the precise failure S-OW-1 was raised about, in a second field. No
previous model got far enough to notice.

**This agent does not own `gauntlet/roundOW/` or `fixtures/`** (§0) and has
changed nothing there. Filed for the owner.

### 2.4 Adapted self-run arm — FAIL, one `-I` short

**Harness: `roundGF/driver_selfrun.py`, not roundDS's own `DS-2` packer.**
roundGF had already established an adapted self-run protocol for exactly this
population — the model emits **one bash script** (extract, compile, invoke,
verify) and the harness executes it, because the interesting steps of a
*building* task are `gcc` and an `argv` line, not Python. Using roundGF's
harness makes this row comparable to its local-model attempt instead of being a
third protocol nobody can line up. The only change is `--api`. **DS-2 remains in
`roundDS/driver.py`, unused**, and is recorded here so the commit history is not
mistaken for two competing protocols.

**This is not roundSR's claim and nothing here implies it.** roundSR's 2/2 was
two agentic CLIs with a shell. This model has no shell; the harness is its hands.

| | |
|---|---|
| package | 97 181 chars, 15 items, **28 833 `prompt_tokens`** |
| cold prefill | **112.2 s, 257 tok/s** |
| iterations | **4** |
| wall | **2 813.5 s**, outcome `wall-cap` |
| **grade** | **FAIL — grade B 0 / 2** |

```
GRADE A -- ECHO CHECK ONLY, NOT EVIDENCE
  once-upon-a-time  text_present=True  sha256_lf_quoted=True
  the-little-robot  text_present=True  sha256_lf_quoted=True
GRADE B -- DECIDES: the GRADER invoked the binary the run built
  (no executable left behind)
vectors reproduced: A 2/2   B 0/2  ->  FAIL
```

**Grade A is 2/2 and is worth nothing**, exactly as roundGF's grader says in
capitals: the expected text is inside the package and this arm inlines it, so
quoting it back is an echo. **Grade B decides, and there was no binary.**

**How far it got, which is further than roundGF's attempt.** roundGF's local
model "never opened the container". This one:

* extracted all **85 entries** from the package;
* found the toolchain (`Compiler found: gcc (mingw)`);
* read both test vectors out of the package and printed prompts, step counts,
  expected text and both expected `sha256_lf` values;
* stated its prediction and its source, as the protocol requires —
  *"PREDICTION: The program will output exactly the `stdout_text` from
  `testvectors/vectors.json` … because we will build and run with the exact
  commands and temperature 0.0 (greedy argmax). PREDICTION SOURCE:
  `testvectors/vectors.json`"*;
* noticed the Windows shim needs work and **patched `win.c`** (a
  `VirtualProtect` `PDWORD` cast) into a `win_patched.c`;
* and then issued
  `gcc -O3 -o run.exe tools/llama2c/run.c win_patched.c -lm`.

**It failed on the include path.** It copied `win.c` to the working root and left
`win.h` at `tools/llama2c/win.h`, with no `-I tools/llama2c`. Reproduced by hand
here:

```
win_patched.c:1:10: fatal error: win.h: No such file or directory
```

**And it could not see that message, because of its own script.** The script ran
`eval "$BUILD_CMD" > build_out.txt 2> build_err.txt` and then printed
`build_err.txt` — which is **0 bytes** on disk. So the feedback the harness
returned contained `Build failed. stderr:` followed by nothing, and the model
had no error text to work from. It spent iterations 2 and 4 on truncated replies
(S-DS-3 again) and the wall ran out.

**The honest reading: a build error one flag wide, made invisible by the model's
own output redirection, in a protocol where it cannot simply look.** That is a
different failure from roundGF's — that model never opened the file; this one
built the whole procedure correctly and lost to a missing `-I` it could not
read. Neither is a statement about the format: nothing in `spec/` or
`BUILD-AND-RUN.md` is implicated, and `BUILD-AND-RUN.md` quotes its commands
with the package-root-relative paths that would have worked.

---

## 3. Findings

**S-DS-1 — the empty cell in the coverage matrix is filled, and the thing that
was blocking its neighbour was hardware.** A frontier open-weights model,
downloaded, verified, quantised by its publisher, served by a binary we compiled,
on our own GPUs, passes the round-1 task byte-exact and decodes both custom
binary payloads. Separately: roundGF could not run the splat task on three of
five local models because *"a 65 775-token package on a 24 GB card"* would not
serve. The identical package is **54 889 tokens** here and serves with **70 GiB
spare**. **The price of a format that carries its own specification is payable,
and the invoice is denominated in VRAM** — about 200 GB if you also want a
frontier implementer. That is a better sentence for the paper than "it did not
fit". **Severity: none, it is a result.**

**S-DS-2 — a spec fix that a weak implementer ignored, a strong one reads and
uses. Both halves are now measured.** The post-fix arm's sharpest conclusion was
*"making a fact machine-readable does not make a weak implementer read it"* — the
8B took `files[0]` with `payload_file` in front of it. This round supplies the
complement, from the program rather than from the model's report:

* **S-OW-1 (`werk-sig/1`):** `build_message()` emits the six fields in order,
  LF-joined, exactly as `MINI-SPECS` §12.1 specifies. It also implemented
  **Ed25519 from scratch** — `point_decompress`, `point_add`, `point_double`,
  `point_mul`, `point_eq` — which no previous open-weights model attempted.
* **S-OW-2 (`payload_file`):** it resolved `primary.sound` through
  `payload_file` and `role`, and the WAV came out rather than the descriptor.
* **`MINI-SPECS` §12.2 (`unverified`):** its own curve arithmetic had a bug, it
  said so, and it reported **`unverified`** rather than `present-and-invalid`.
  **Zero false tampering alarms in four runs.**

The two findings together are one sentence: **a spec fix removes an excuse; the
excuse being gone only helps an implementer that was going to read it.**
**Severity: none — it closes a question the post-fix arm left half-answered.**

**S-DS-3 — at this decode speed the GENERATION cap binds, not the iteration cap,
and it penalises the behaviour the protocol wants.** Decode measured at
**26.3 tok/s short and 18.75 tok/s at ~40 000 tokens of depth**, so a full
16 384-token reply costs ~875 s and the 2 700 s wall admits about three replies.
Across the round: **14 iterations, 7 of them `finish=length`** — exactly half —
and a truncated reply has no closing fence, so it yields **no program at all**.
The round-1 run is the clean illustration: it had `exit 0` and two correct
digests at iteration 2, then spent iterations 3 and 4 producing nothing because
it was re-emitting the whole program to fix an honesty defect **it had found in
its own report** ("the report says 'We did not read the loaders/ source files'
which is false … we should be honest in report"). *Proposed fix for the next
round:* a diff-or-whole-file reply contract, or a generation cap scaled to the
measured decode rate rather than fixed at a number chosen for 24 GB models.
**Severity: medium — it is a harness property, and it costs the strongest
implementer the most, because the strongest implementer writes the most.**

**S-DS-4 — `spec_sha256`'s construction is not in the travelling set.** The model
asked for it in as many words: *"We wanted the definition of `spec_sha256` (what
exactly it hashes) … We attempted to derive it by hashing `spec/` files in
various orders; result: unverified."* This is S-OW-1's shape in a third field:
`MANIFEST.json` declares it, and the rule that constructs it lives where the
budget cannot reach. **Severity: medium.** *Proposed fix:* one executable
statement in `MINI-SPECS` §11 beside the `input_hash` one, which is the model of
how to do it.

**S-DS-5 — the harness truncated valid programs at a fence inside a string
literal, and handed the model back its own apparent SyntaxError.** roundOW's
`extract_program()` ended a fenced block at the first ```` ``` ```` anywhere.
Every task in this family asks for a `REPORT.md` quoting source, so a program
that builds markdown contains a literal triple-backtick in a string. Measured on
the stored reply: **old 18 441 chars, `SyntaxError` line 488; new 21 924 chars,
parses.** It destroyed both complete programs of the splat attempt, identically.
Fixed as **DS-3** (a closing fence must start its own line); the attempt is
recorded ungraded. **Severity: high for the instrument, zero for the format.**
This is the third consecutive round whose largest defect was in a harness rather
than in `spec/` — S-OW-5, S-GF-1, now S-DS-5 — and the pattern is worth naming:
**the gauntlet's instruments are less well tested than the thing they measure.**

**S-DS-6 — the splat grader tests a storage representation, not a value.**
`grade_gsplat.py` looks for the colour triple `39 19 6`. The run reported
`0.152941, 0.074510, 0.023529` under a column labelled `rgb_linear` — the same
numbers before the ×255 quantisation the grader itself applies when deriving
ground truth. Either reading is defensible and **this agent does not get to
pick**: the grader's verdict as run (`FAIL`) is what the tables record, and the
grader was not modified after the result was seen. **Filed for Gregor's ruling.**

**S-DS-7 — `gauntlet/roundOW/mini-v1.werk` declares a wrong `input_hash`, and
every open-weights round has used it.** Reported by the model, confirmed
independently here: `crate-v1` 25/25 verify, `gsplat-v1` 3/3 verify,
**`mini-v1` node `rest-poses` does not** — declared `60e08ed1…`, documented
construction over its own declared digests yields `4b91ccbb…`, six construction
variants tried and none reproduces it, and the sibling node `bounds` in the same
fixture verifies. `build_mini_fixture.py` recomputes `spec_sha256` and re-signs
but never recomputes `input_hash`. **Consequence: for as long as this fixture has
existed, a reader that implemented `input_hash` correctly was told an intact
package was damaged** — the exact failure mode S-OW-1 was raised about, in a
different field, and this time it was the *fixture* lying rather than the model
guessing. **Severity: high.** No previous model got far enough to notice. Filed
for the owner of `gauntlet/roundOW/` and `fixtures/`; this agent changed nothing
there.

**S-DS-8 — the envelope task now carries its own answer key.**
`poses/rest.wkrp` is **byte-identical** to `spec/examples/restposes.example.wkrp`,
and S-OW-3's fix inlines that example's complete decoded header. So the header
clause has been an echo check since the post-fix arm. It was excluded before this
row was believed — the header values are echoable, the pose-entry values
(quaternion `0.707107`, probabilities, support areas, contact coordinates) appear
nowhere in the package and are correct, and the program walks
`payload_origin`/`sections` with eight `struct.unpack` calls — so **this decode is
genuine**. But the instrument is compromised and the next round must point the
task at a WKRP payload that is not the worked example. **Severity: high for the
instrument.** It is the same class as roundGF's caught grader: *a fix that made
the spec better made the test easier, and nothing warned anyone.*

---

## 4. What this round does not establish

**n = 1 model.** One frontier open-weights family. It fills a corner of the
capability-by-provenance grid; it is not a population, and no rate should be
computed from it.

**The protocol was never reached.** Every run ended on the wall cap or on a
truncated reply. **7 of 14 iterations were `finish=length`**, so no run got near
its 8-iteration budget, and the iteration counts here are not comparable to the
24 GB rounds' (S-DS-3).

**There is no clean spec-forcing pass in this round.** The envelope decode is
genuine — proven by values that appear nowhere in the package — but the task is
compromised by **S-DS-8** and cannot be quoted as a clean result until it points
at a payload that is not the worked example. The splat verdict is a grader
`FAIL` turning on **S-DS-6**, which is unresolved and is Gregor's to rule on.

**The self-run row is not roundSR's claim.** roundSR's 2 / 2 was two agentic
CLIs with a shell. This arm's model has none; the harness is its hands, and the
row is labelled accordingly.

**Nothing here is a statement about `spec/`.** Zero new specification bugs were
found. The one real defect is in a **fixture** (S-DS-7) and three are in
**instruments** (S-DS-5, S-DS-6, S-DS-8).

---

## 5. Handover

### 5.1 The server is left RUNNING, deliberately

Gregor decides teardown. As of the end of this wave, `dsv4-server.service` is
active on **v100**, holding 181 GiB across 8 GPUs, serving
`http://<lan-ip>:8123/v1` with model id **`DeepSeek-V4-Flash-0731`** at
**1 048 576** context.

```bash
# status
ssh v100 "systemctl --user status dsv4-server --no-pager | head -5"

# stop (Gregor's call)
ssh v100 "systemctl --user stop dsv4-server"

# restart, exactly as it was brought up
ssh v100 "systemd-run --user --unit=dsv4-server --collect bash -c '
  export LD_LIBRARY_PATH=\$HOME/cuda12/targets/x86_64-linux/lib:\$LD_LIBRARY_PATH
  export CUDA_DEVICE_ORDER=PCI_BUS_ID
  <user-home>/dsv4/llamacpp-dsv4/build/bin/llama-server \
    -m <user-home>/dsv4/DeepSeek-V4-Flash-0731-MXFP4-00001-of-00002.gguf \
    --host 0.0.0.0 --port 8123 -ngl 99 -c 1048576 --parallel 1 \
    --jinja --reasoning-format none --alias DeepSeek-V4-Flash-0731 \
    > <user-home>/dsv4/server.log 2>&1'"
```

A **cold** load reads 155 GB off ext4 at ~150 MB/s, so allow ~17 minutes before
the endpoint answers; warm (page-cached) it was **54 s**. Only shard 1 is named
— llama.cpp follows `split.no`/`split.count` and opens shard 2 itself.

**Nothing else on the lab was touched.** The vLLM vision service on **<lab-gpu-host>**
port 8102 was never contacted and its two A5000s were never allocated against;
<lab-gpu-host> was surveyed read-only and rejected as a host in §1.1. Gregor's own
`~/llama.cpp` checkout on v100 is untouched — this round built in a **git
worktree** at `<user-home>/dsv4/llamacpp-dsv4`.

### 5.2 Left on disk on v100

| path | size | note |
|---|---:|---|
| `<user-home>/dsv4/DeepSeek-V4-Flash-0731-MXFP4-0000{1,2}-of-00002.gguf` | 155 GB | verified against publisher digests; **ext4, not the ntfs3 mount** (§1.5) |
| `<user-home>/dsv4/llamacpp-dsv4/` | ~2 GB | b10333 worktree + CUDA sm_70 build |
| `<user-home>/pget.sh` | 1 KB | the resumable parallel-range fetcher |
| `/media/gregor/m4tx/dsv4/` | — | **the abandoned ntfs3 attempt; the mount was returning I/O errors and this agent did not force it.** Left for Gregor to clear when the volume is healthy |

### 5.3 Open for a ruling or an owner

| id | what | who |
|---|---|---|
| **S-DS-6** | does "the colours it contains" mean WKPC's uint8 bytes or the linear floats `gsplat.layout` §5 defines? The splat verdict turns on it | **Gregor** |
| **S-DS-7** | `mini-v1.werk`'s `rest-poses` `input_hash` is wrong; `build_mini_fixture.py` never recomputes it | owner of `gauntlet/roundOW/` + `fixtures/` |
| **S-DS-8** | the envelope task needs a WKRP payload that is not the inlined worked example | owner of `gauntlet/roundOW/` |
| **S-DS-3** | reply contract or a decode-rate-scaled generation cap, for the next round | next round's harness author |
| **S-DS-4** | `spec_sha256`'s construction should travel, as an executable statement beside `input_hash`'s | owner of `spec/` |
| **Table 9** | the *in progress* row can be filled; row text and caveat in `paper/v2/NUMBERS.md` §13.1 | **paper-edit agent** |
