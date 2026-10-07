# Negative-control / comparative gauntlet round (roundNC) — DESIGN

**Status: DESIGN ONLY. Nothing has been executed against any agent. For Yuvraj's review.**
Date: 2026-09-30. Target: paper v2 (arXiv, 4-6 weeks). Priority #2 per Gregor.

## 0. What this round tests, in one paragraph

Every gauntlet round to date aims the agent-implementability protocol at a werk
file, and werk files always pass at the frontier tier. That leaves the metric
open to the objection: *maybe any format passes; maybe the metric has no
dynamic range and measures the agent, not the format.* This round runs the
EXACT same protocol (same task sentence, same isolation, same artifact-based
grading, same harness timing) against three ordinary interchange formats
carrying comparable content: a bare FBX, a glTF with external textures, and a
USDZ. The controls do not carry their specification inside; werk files do.
That asymmetry is not a confound. It is the measured variable, and the round
must say so in every write-up.

Pre-registration discipline: this document, the prompts, the grading criteria
and the ground-truth expectations files are all committed BEFORE any trial
runs. Following the house rule from every prior round: an agent's report is
evidence about the agent; success is decided by hashing bytes on disk.

---

## 1. Comparison fixtures

### 1.1 Content parity target

The werk baseline is `gauntlet/roundOW/mini-v1.werk` (post-fix build,
sha256 `f7bdcc85...`): one crate mesh (`geometry/game.glb`, 16 736 B), one
texture-class PNG, four WAVs, JSON sidecars, plus the travelling `spec/` tree
and loaders. The controls must carry the *payload* content class (a mesh plus
a texture, and a sound where the format allows one) without the spec tree,
because no ordinary format has one. Payload complexity is matched at the
"single textured prop" level, not at byte-count level; section 5.2 records
this as a limitation.

All control payloads come from CC0 sources already in the repo, so all three
fixtures are redistributable and can be committed:

- Mesh + texture: Poly Haven **Wooden Crate 01** (CC0), already vendored at
  `fixtures/sources/crate-cc0/` for the CC0 fixture arm.
- Sound: the deterministic synthetic WAV that `build_crate_cc0.py --variant
  full` generates (CC0 by construction), extracted once and reused verbatim.

### 1.2 The three fixtures and exactly how each is produced

One build script, `gauntlet/roundNC/build_controls.py` (to be written),
drives everything it can from Python; Blender 4.x headless (a pending install
item on this machine anyway) is the one external tool, pinned by exact version
and recorded in the pin file. Cross-machine byte-determinism is NOT required
for the controls (unlike the CC0 werk arm) because grading never rebuilds
them: ground truth is recorded once at build time and the built bytes are
committed and hash-pinned. Determinism posture per fixture is still recorded
honestly.

| fixture | produced by | payloads inside | determinism posture |
|---|---|---|---|
| `crate-nc-v1.fbx` | Blender 4.x headless: import the CC0 crate, export binary FBX with `path_mode='COPY', embed_textures=True` (one file, texture embedded as an FBX Video/Content blob). Export script committed. | mesh (FBX geometry arrays), 1 embedded PNG/JPG texture | single-build, hash-pinned; Blender version + export settings recorded |
| `crate-nc-v1.gltf` + `crate-nc-v1.bin` + `crate_diffuse.png` | Preferred: Poly Haven's own glTF-separate download, used verbatim (already redistributable, no tool in the loop). Fallback: Blender glTF-separate export of the same crate. | mesh (external .bin buffer), 1 external PNG | verbatim source bytes (or single-build); all three files hash-pinned |
| `crate-nc-v1.usdz` | Blender 4.x USD export to .usdc + texture, then packaged per the USDZ rule (uncompressed zip, 64-byte aligned) either by Blender's direct .usdz export or by pinned `usd-core` (pip) `usdzip`. The WAV is added as a `UsdMedia SpatialAudio` prim referencing `audio/impact.wav` inside the package. | mesh (usdc), 1 PNG, 1 WAV | single-build, hash-pinned; tool versions recorded |

Notes and honest caveats, decided now rather than discovered later:

- **"Bare FBX"** is read as: one single `.fbx` file, nothing beside it. Binary
  FBX has no published official specification; the agent will be working from
  prior knowledge plus the bytes. That is the realistic condition for FBX and
  it is part of what the control measures.
- **glTF** is deliberately the *friendliest* control: JSON manifest-like
  structure, external payloads sitting in plain sight, `json` in the Python
  stdlib. If any control passes cleanly, it will be this one; that is useful
  signal, not a flaw.
- **USDZ**: the container is zip (stdlib `zipfile` opens it) but the payload
  is binary usdc ("Crate" format), which has no spec inside the file. Audio is
  supported, so USDZ gets the WAV. If the Blender/usd-core route stalls, the
  fallback is an Apple sample USDZ, but those are NOT redistributable, so the
  fallback is: ship without USDZ rather than ship a non-CC0 file. The round is
  still publishable with two controls; three is the target.
- **Sound coverage is uneven by nature**: FBX embedding of audio is
  nonstandard, glTF has no audio at all, USDZ supports it. Section 2 resolves
  what the prompt says about this.

### 1.3 Declared expectations (the ground-truth replacement for MANIFEST)

werk grading walks `MANIFEST.json` inside the fixture. The controls declare
nothing, so grading uses a ground-truth file **built at fixture-creation time
by the build script, from the source assets, and kept OUTSIDE the agent's
workspace at all times**: `gauntlet/roundNC/expectations.json` (committed to
the repo; the agent's temp dir receives the fixture file(s) and the prompt,
nothing else).

Per fixture it records two tiers:

- **Tier 1 — byte-exact payloads.** sha256 of every payload the format stores
  verbatim: the glTF's `.bin` and `.png` (trivially the sidecar files' own
  bytes), the USDZ's zip entries (usdc, png, wav), and the FBX's embedded
  texture blob (FBX stores embedded media content bytes verbatim inside the
  Video node; the build script records the sha256 of the source image bytes it
  embedded).
- **Tier 2 — canonical mesh dump.** Because "extract the primary mesh" has no
  single byte-exact answer for FBX (geometry lives in arrays, not in an
  extractable sub-file), the build script also records: vertex count, triangle
  count, axis-aligned bbox (6 floats), and the sha256 of a canonical vertex
  dump defined as: positions only, float32 little-endian, in the file's own
  storage order, no dedup, no reindex. Tolerance for bbox/positions when an
  agent emits text rather than binary: values matching to 1e-5 after parse.
  This mirrors the splat round's `281 498` + first-point check.

The same two tiers are recorded for `mini-v1.werk` (Tier 1 is just the
manifest's declared hashes; Tier 2 computed from `game.glb`), so the baseline
and controls are graded by one grader with one code path.

`expectations.json` also records, per format, **what integrity data the file
itself declares**, fixed now so the "verifies integrity" clause is gradeable:

| format | integrity data the file itself carries |
|---|---|
| werk | per-file sha256 for every declared file, zip CRC-32s, `spec_sha256`, `input_hash`, Ed25519 chain |
| FBX (binary) | none (no checksums of any kind) |
| glTF | none (byteLength/count consistency checks only, not cryptographic) |
| USDZ | zip CRC-32 per entry (a real, checkable declaration, and the only one) |

This gradient is itself a result the paper can print.

---

## 2. Task prompt adaptation

### 2.1 The prompt, verbatim with the filename swapped

The control prompt is `gauntlet/roundOW/PROMPT-round1task-mini.txt` reproduced
byte-for-byte with exactly TWO string substitutions:

1. `mini-v1.werk` → the control filename (`crate-nc-v1.fbx`,
   `crate-nc-v1.gltf`, `crate-nc-v1.usdz`), in both places it appears (the
   TASK line and hard constraint 1/5).
2. In the TASK sentence only: `and one sound` → `and one texture`.

Substitution 2 needs a ruling and here is the case for it, stated before any
run: glTF cannot reference audio at all and FBX audio embedding is
nonstandard, so a verbatim "one sound" clause would make two of three
controls fail on a *content* technicality rather than on implementability,
which would tilt the comparison **toward** werk. Substituting "texture", a
strictly easier and universally present payload class, tilts the only
direction a critic cannot complain about: in the controls' favor. The werk
baseline trials (section 4) keep "one sound" verbatim. If Yuvraj prefers
absolute verbatimness, the alternative is: keep "one sound" and score the
sound clause N/A for FBX/glTF; the plan recommends the substitution because
N/A clauses complicate the headline table. **Decision needed at review.**

For the glTF fixture only, constraint 1 becomes "is crate-nc-v1.gltf and the
two files it references (crate-nc-v1.bin, crate_diffuse.png)", because
external references are that format's containment model; refusing the agent
its own format's sidecar files would be sabotage, not isolation. This is the
third and final permitted edit, and it exists because "the file" is a
different noun for a multi-file format.

### 2.2 What may NOT be changed (the anti-tilt statement, published with the round)

- The task verb list: opens, lists contents with their meanings, verifies
  integrity, extracts to disk. No verb weakened, dropped, or added.
- All six HARD CONSTRAINTS: same isolation, same no-web rule, same
  "recognising the format from prior knowledge does NOT license using it...
  derive every rule from the file itself" clause, same "REPORT rather than
  fetch" escape hatch, same no-modify and no-execute rules. Note what the
  recognition clause does here: for werk it is nearly vacuous (nothing to
  recognise); for FBX/glTF/USDZ it demands the agent ground its prior
  knowledge in the actual bytes. It stays verbatim precisely because it is
  the clause a critic would accuse us of relaxing for werk or tightening for
  the controls. Same words, both arms.
- The entire REPORTING block, including the stumble-honesty instruction (so
  stumble counts remain comparable within this round, and remain
  instruction-inflated relative to silent runs, as RESULTS.md already
  documents).
- The harness: same wrapper script, same timeout, same fresh-directory
  discipline, same model, same day where feasible.
- Grading: same grader, same artifact-not-report rule, same PASS/PARTIAL/FAIL
  definitions (section 3), fixed before trial one.

The three permitted edits (filename, sound→texture, the glTF multi-file
clause) are the COMPLETE list. Anything else found to differ between the
werk and control prompts after the fact invalidates the trial.

### 2.3 The asymmetry, stated in the round's own words

The werk file contains ~35 000 tokens of self-description; the FBX contains
zero. The controls therefore test the agent's prior knowledge of a format,
while the werk arm tests the file's ability to teach a format. Those are
different experiments sharing one protocol, and that difference is the point:
the paper's claim is not "agents can read werk" but "werk is implementable
from the artifact alone, and ordinary formats are implementable only to the
extent the implementer already knows them and the file lets them verify
anything at all." The round exists to measure where those two curves sit, not
to manufacture a werk win.

---

## 3. Grading (pre-registered, written before any trial)

Grader: `gauntlet/roundNC/grade_nc.py`, a variant of `roundOW/grade.py` that
reads `expectations.json` instead of walking a MANIFEST, keeps the same
walk-the-rundir / hash-the-bytes / rerun-in-clean-dir behavior, and adds the
Tier 2 mesh-dump check. It is run by the orchestrator (Yuvraj), never by the
agent, and expectations.json never enters the agent's workspace.

Per-clause scoring, graded from artifacts and transcript:

| clause | graded how |
|---|---|
| C1 open | program exits 0 and enumerates the container/file structure |
| C2 list with meanings | listing names the payloads and states what they are (mesh, texture, sound, scene description); graded lenient/strict noted per trial |
| C3 verify integrity | agent verifies everything the file itself declares (per the section 1.3 table) AND correctly reports what could not be verified. For FBX/glTF the fully honest answer is "this file declares no integrity data; only structural consistency was checkable", and that answer scores C3 = PASS-honest. Inventing a verification (e.g. claiming hashes checked when none exist) scores C3 = FAIL regardless of other output. |
| C4 extract | the named payloads exist on disk in the run dir |
| C5 hash match | Tier 1: extracted texture/sound/buffer bytes sha256-match expectations. Tier 2: mesh dump matches (or vertex count + bbox within tolerance if the agent chose a text dump). |

Overall verdict, identical in shape to the werk rounds:

- **PASS** = C1..C5 all pass (with C3 = PASS-honest allowed; that IS the pass
  condition for a format that declares nothing).
- **PARTIAL** = at least one Tier 1 or Tier 2 artifact byte/value-exact, but
  not all clauses (the llama-8B "mesh right, sound wrong" shape).
- **FAIL** = program does not run clean, or no graded artifact matches.

Two headline numbers per format, decided now: (a) PASS rate, and (b) the
**verifiable-integrity fraction**: of the payload bytes extracted, what
fraction could be checked against anything the file declares (werk: 100%;
USDZ: CRC-32 only; FBX/glTF: 0%). Number (b) is the dynamic range the binary
PASS/FAIL may lack at frontier tier, and it is committed as a primary
endpoint NOW so it cannot be accused of being a post-hoc rescue (see 5.3).

Secondary recorded measures, same as every round: harness wall clock, stumble
count, files-read-in-order, "wanted from outside the file" list, whether the
agent grounded its prior knowledge or coded from memory (the §7 recognition
hazard, self-reported per the REPORT.md format).

---

## 4. Trial matrix

| arm | fixture | agent | n | prompt |
|---|---|---|---|---|
| baseline | `mini-v1.werk` (post-fix, `f7bdcc85...`) | claude CLI | 3 | mini prompt verbatim |
| control | `crate-nc-v1.fbx` | claude CLI | 3 | adapted (§2.1) |
| control | glTF triple | claude CLI | 3 | adapted |
| control | `crate-nc-v1.usdz` | claude CLI | 3 | adapted |
| optional | all four | codex CLI, kimi CLI | 1 each | same |

The fresh werk baseline (rather than citing round-1's 2026-08 numbers) is
mandatory: model versions drift, and the comparison must be same-model,
same-day, same-harness. 12 required runs; +8 if both optional CLIs run.

**Isolation on Windows.** One fresh directory per trial under
`%TEMP%\gauntlet-nc-<date>\<format>-t<N>\`, outside all werk repositories,
containing only the fixture file(s) and `PROMPT.txt`. The prompt's off-limits
list already names `spec/`, `werk/`, `loaders/` directories machine-wide; the
D:\werk paths are added to the constraint text the same way F:\werk was in
round 1 (this edit is part of the isolation boilerplate, not the task
sentence, matching round 1's documented deviation 1).

**Execution is Yuvraj's, by hand.** Spawning autonomous agents from a Claude
session is blocked by the permission system (correctly), so the round ships a
runner script Yuvraj executes in his own terminal. Shape (final script to be
generated with the fixtures, one command per trial, harness-timed):

```bash
# run_nc_trials.sh -- run from Git Bash; one block per trial
ROOT="$TEMP/gauntlet-nc-$(date +%Y%m%d)"
run_trial () {  # $1=arm name  $2..=fixture file(s)
  d="$ROOT/$1"; mkdir -p "$d"
  shift; for f in "$@"; do cp "$f" "$d/"; done
  cp "D:/werk/werk/gauntlet/roundNC/PROMPT-$1.txt" "$d/PROMPT.txt"
  t0=$(date +%s)
  ( cd "$d" && claude -p "$(cat PROMPT.txt)" \
      --dangerously-skip-permissions \
      > _agent-stdout.txt 2> _agent-stderr.txt )
  echo "$1 wall_s=$(( $(date +%s) - t0 ))" | tee -a "$ROOT/timings.txt"
}
run_trial fbx-t1  "D:/werk/werk/gauntlet/roundNC/crate-nc-v1.fbx"
# ... one line per trial; werk baseline uses mini-v1.werk + the verbatim prompt
```

Grading afterward, per trial:

```bash
python D:/werk/werk/gauntlet/roundNC/grade_nc.py --rundir "$ROOT/fbx-t1" --format fbx
```

plus the `--rerun` clean-directory re-execution for every run whose verdict
will be printed, exactly as `grade.py` does today. Wall clock is measured by
the wrapper (self-reported times are recorded but never used; the
cross-vendor round measured 2.2x-11x self-report inflation).

---

## 5. Threats to validity of the control itself

**5.1 Prior knowledge cuts against werk, and that must be said out loud.**
FBX, glTF and USDZ are massively represented in every model's training data;
werk is essentially absent from it. The controls therefore start with an
advantage the werk arm never had. Consequence, stated in advance: a control
PASS is partly a memory result; a werk PASS cannot be. If werk matches or
beats the controls on any measure despite this handicap, that result is
STRONGER than a symmetric comparison would be. If the controls beat werk on
speed, that is expected and reportable without embarrassment: reading 35k
tokens of spec costs time that remembering a format does not. The paper
should print both sentences.

**5.2 Fixture complexity is matched by class, not by bytes.** A one-prop
fixture cannot be byte-identical across four containers. Mitigation: same
source mesh, same texture, same (where possible) sound, payload counts within
a factor of ~2, and the complexity table printed beside the results. Residual
risk accepted and disclosed.

**5.3 If the controls PASS (likely at frontier tier), the honest framings,
chosen NOW.** Primary: the binary PASS/FAIL was never the paper's only axis,
and the pre-registered verifiable-integrity fraction (0% / CRC-only / 100%)
plus C3-honesty is where the formats separate even when extraction succeeds.
Secondary: dynamic range lives at the open-weights tier; a follow-up arm can
rerun the controls under `driver.py`'s no-tools protocol, where the werk
package's inline spec is the only documentation any model gets, and the
controls get nothing to inline but a hex dump and a listing. What is NOT
permitted: quietly demoting the round, redefining PASS after the fact, or
reporting only the werk-favorable measures. If all three controls fully PASS
all five clauses including honest C3, the paper reports that the
implementability bar alone does not separate formats at frontier tier and
that werk's differentiator is the verifiability column, which is what law 10
actually claims (integrity is *tested*, not merely parsed).

**5.4 The recognition clause behaves differently per arm.** "Derive every
rule from the file itself" is checkable for werk (the spec is in the file)
and only self-reportable for FBX (there is nothing in the file to derive
binary-FBX rules from except the bytes). The controls' compliance with
constraint 4 is therefore weaker evidence, transcript-audited but not
structurally enforceable. Recorded, not fixable.

**5.5 Stdlib asymmetry.** Python ships `zipfile` (USDZ container) and `json`
(glTF) but no FBX parser, so the three controls are not equally hard
independent of documentation. That ordering (glTF easiest, USDZ middle, FBX
hardest) is a prediction this design registers now; if the results land in
that order, the metric is showing dynamic range *within* the controls, which
is itself evidence the instrument works.

**5.6 One model family for the required arm.** claude CLI only, n=3, same
weekday. The optional codex/kimi arm exists to blunt this; if it does not
run, the round inherits the same "one family" caveat round 1 carried, and
says so.

**5.7 Instrument risk.** Three consecutive rounds (S-OW-5, S-GF-1, S-DS-5)
found their worst defect in the harness, not the spec. Mitigations baked in:
grade_nc.py is dry-run against the ground truth BEFORE any trial (build the
fixtures, extract the payloads with reference tools, grade that directory; it
must come out PASS), and an echo-check is inherited from roundGF (nothing in
the agent's workspace may contain the expected hashes, which is why
expectations.json lives only in the repo).

---

## 6. Cost, runtime, execution order

Estimates: frontier round-1-class trials historically run 2-14 min wall each.
12 required runs ≈ 1.5-3 h of wall clock, plus grading. API cost at claude
CLI rates, order of $1-4 per trial → roughly **$15-50 for the required arm**;
optional cross-vendor arm adds ~$10-30 (codex/kimi subscriptions/keys
permitting). Fixture building is an evening: Blender install (already a
pending item), export scripts, expectations builder, grader, dry-run.

Proposed order (each step gated on the previous, nothing skipped):

1. **Build fixtures** (`build_controls.py` + Blender), record every hash,
   commit fixtures + `expectations.json` + pin file to `gauntlet/roundNC/`.
2. **Write the four prompt files** by scripted substitution from
   `PROMPT-round1task-mini.txt` (the script IS the proof only three edits
   exist), commit.
3. **Write and dry-run `grade_nc.py`** against reference extractions of each
   fixture; must grade PASS on ground truth and FAIL on a deliberately
   corrupted copy.
4. **Freeze**: commit this plan + criteria as the pre-registration; after
   this commit, criteria edits require a documented amendment.
5. **Yuvraj runs the werk baseline** (3 trials) via `run_nc_trials.sh`.
6. **Yuvraj runs the 9 control trials.**
7. **Grade everything**, including clean-dir re-runs; write
   `gauntlet/roundNC/RESULTS-NC.md` in the house style (headline table,
   per-agent detail, deviations recorded not hidden, "what this does and does
   not establish").
8. Optional cross-vendor arm, then the paper §7 text.

Steps 1-4 can be done by Claude in-session (file writing and local tool runs
only, no agent spawning). Steps 5-6 are Yuvraj's terminal. Nothing goes to
Gregor or GitHub until Yuvraj approves the results write-up.

## Open decisions for Yuvraj's review

1. The `sound` → `texture` substitution (§2.1) vs. keeping "one sound" with
   N/A scoring for FBX/glTF. Plan recommends the substitution.
2. USDZ build route: Blender direct .usdz export vs. usd-core `usdzip`
   (plan: try Blender first, since it is being installed anyway).
3. Whether the optional codex/kimi arm is in scope for v2's timeline.
4. Whether `roundNC/` fixtures + this plan should go on the existing
   `fix/cc0-replication-findings` branch or a new one (no PR either way
   until approved).
