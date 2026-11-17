# Release assembly — how this repository was put together

Assembled 2026-11-07 (workstream W1 of the first public release). This
repository has a fresh history; its first commits are the release. This file
records the sources, every decision, every patch resolution, the gate results
before and after, what was left out, and the questions only Gregor can answer.
Nothing here was pushed anywhere public.

## 1. Sources

| Source | Revision | Role |
|---|---|---|
| Private lineage, branch `artcraft-profiles` | `6bf77f3` (= private `master` `099167b` + any-profile core, format definitions in SPEC §3.18, deflate read, writing walkthroughs, 32-bit inflate fix) | **the base**: exported with `git archive`, then curated |
| Earlier public snapshot `cronos3k/werk`, `main` | `6d547d0` (separate history, no common ancestor) | compared file by file; brought over what the base lacked (below) |
| Same, branch `fix/replication-f1-f4` | `df3ee77` | F1/F3/F4 of the independent replication |
| Yuvraj Puyam's pull requests #4–#11, #13 | heads `a284269` (#4), `1017694` (#5), `4c57a05` (#6), `ae96361` (#7), `fe54cbf` (#8), `7463601` (#9), `37a3eab` (#10), `c5fe4f4` (#11), `890d2e3` (#13) | applied with his authorship (§3) |
| The reviews of those PRs (A: spec and paper, B: code/gates/graders, C: evidence) and the decisions list | 2026-10-19 | the fixes made in §4 |

**What the snapshot had and the base lacked.** By content: only
`fixtures/DOWNLOADS.md` and `tools/fetch_fixtures.py` (replaced by
`RELEASE-ASSETS.md` and a new `tools/fetch_fixtures.py`, §6), `LICENSE`
(MPL-2.0) and `TRADEMARK.md` (not carried: licence undecided, see
`LICENSE-PENDING.md`), and `README.werk.md` (a text-rewriting-tool copy of the
README, not carried). The CC0 public fixture arm (`fixtures/build_*_cc0.py`,
`CC0-FIXTURES.md`, `run_gate_cc0_*.py`, rulings of 2026-09-09) is already in
the base, in its re-pinned form (F-AC-5/6). The base lacked the F1/F3/F4 fixes
of `df3ee77`; they are ported (commit "fixtures: fix independent-replication
findings F1, F3, F4"). **The snapshot's committed gauntlet run records were
reworded by a text-rewriting tool; none was taken from it.** Every run record
here is the private lineage's original.

## 2. Decisions

1. **Base = `artcraft-profiles` 6bf77f3**, exported, not merged.
2. **Out of git, into hash-pinned release assets** (`RELEASE-ASSETS.md`, files
   in the upload folder beside the repository): every file over 5 MB
   (`crate-v1`, `crate-v1-damaged`, `ista-varun-v1`, `gsplat-v1`,
   `image-cc0-v1`, `image-cc0-v1-damaged`, `gauntlet/roundSR/selfrun-v1.werk`),
   the three hardcopy page scans, and the negative-control round's 147
   reproducible outputs as one deterministic tarball. 11 assets,
   151 650 698 bytes. `image-cc0-v1` (5.5 MB) is CC0 and rebuildable from the
   repository; it is an asset only because of the size rule.
3. **Internal working documents and unreleased research material were
   excluded** (session handover, agent briefs, local tool configuration, the
   internal push sweep, and research material not yet ready for release).
   `ROADMAP.md` is kept: the gate harnesses quote their gates from it.
4. **Author-lab paths in code became environment variables.** `WERK_LAB` names
   the directory holding the author's sibling projects (splat-foley, SFNovels,
   ArtCraft samples, the UE mannequin export). Unset, every author-lab clause
   reports SKIP, as it already did on any machine but the author's.
   `WERK_UE_TESTBED` names the Unreal test project; `GAUNTLET_ROOT` the
   gauntlet runners' run directory. In documents and result ledgers, local
   paths read `<repo>` (this repository) and `<lab>` (the author's machine);
   host names and addresses read `<lab-…>` / `<lan-ip>`; the user profile
   `<user-home>`. Agent run records keep their recorded workspace paths (they
   are evidence) and lose only host names and the user profile.
5. **No LICENSE file.** `LICENSE-PENDING.md` states both candidates and the
   `Cargo.toml` inconsistency. No licence header was changed.
6. **Spec text**: as the base, plus PR #11's edge-target rule with its review
   fixes, plus two schema descriptions that named a local path. All three move
   `spec_sha256`, so every fixture was rebuilt and re-pinned (§5).
7. **Provisional rulings used** (until Gregor answers): #11 accepted (an absent
   `requires` target kills the node, the file survives); PASS = the recorded
   criteria, the stricter full-task re-grade reported beside them as post-hoc;
   S-DS-6 accepted; the negative control is exploratory, not
   "pre-registered".

## 3. Yuvraj Puyam's commits — applied with his authorship

Each PR commit was applied with `git am -3` from his PR head (the snapshot's
blobs were fetched temporarily so the 3-way fallback had its bases, then
deleted). Author, author date and message are his. Resolutions:

| PR | Commits | Applied as | Resolution |
|---|---|---|---|
| #4 | 1 | as-is | clean |
| #7 | 6 | 4 applied | `gauntlet/RESULTS.md` (rewriting-tool leftovers) and `README.md` (JS reader line) **skipped**: they fix the snapshot's reworded copies; the base's originals have neither defect (review B §4). The other four clean. |
| #6 | 7 | all | `tests/run_gate_9.py` conflicted twice with the path neutralisation (§2.4): took the PR side, kept the neutral path. Two literal author-lab paths his commits introduced (`tests/package_rebuild.py` docstring, a `run_gate_a.py` SKIP string, which also carried the invalid `\s` escape) were neutralised inside his commit before the next ones were replayed. |
| #11 | 5 | all | `spec/SPEC.md` and the Blender copy merged 3-way without conflict; the closed code table row was added in the fix commit. Commit 4 conflicted in `werkc.rs`, `build_golden.py`, `build_image_fixture.py`, `build_retarget_fixture.py`, `pipeline/package.py`: both sides kept (the base's `loader_capabilities` import / argument and his guard). |
| #5 | 11 | all | clean |
| #8 | 9 | replayed, relocated | `gauntlet/roundNC/` → `evidence/second-lab/roundNC/`; 147 run outputs and logs kept out of git (asset); his three shared files (`RERUN-CONVENTION.md`, `rerun_support.py`, `test_rerun_support.py`) are byte-identical to #5's and were not re-added, so his last commit is empty here and says so |
| #13 | 1 | replayed, relocated | `results/second-lab/` → `evidence/second-lab/` |
| #9, #10 | 7 + 8 | **not applied** | paper changes, parked as his patch series in `paper/incoming/` for the paper edit |

The replays (#8, #13) wrote each of his commits' files at the new paths and
committed them with his author name, e-mail, date and message, plus one line
naming the relocation.

## 4. Fixes made after his commits (separate commits, by the assembler)

* **#6** (review B problems 1–4): Gate 12's payload clause renamed "rebuild
  reproduces the payload entries", whole-file identity its own clause; Gate 9
  L1 detects which deflater reproduces the pin (Pillow's own stream, else a
  stock-zlib re-deflate); L3 failures name the differing entries; Gate A's
  MSVC helper creates its folder (Gates 9 and 12 no longer crash on a fresh
  tree).
* **#11** (review A changes 1–5): writers refuse an edge of either kind to an
  absent node (`refuse_dangling_edges`, Python and Rust, `Package::add_node`,
  `edge_targets.py` exit 1 for any); the self-run builder, the hardcopy builder
  and the Blender exporter are guarded (the gsplat builders already were,
  through `pipeline/package.py`); a skipped node that dies is reported both
  ways by werk-core too; the closed code table gains `requires-missing-node`;
  clause 6b expects Rust `--strict` exit 1 (ruling 9); ruling R1 gains a note
  that its value is the fingerprint of its date. **Not done:** the Unreal C++
  exporter is not guarded (cannot be compiled here).
* **#5** (review B a–f, finding 4): text columns tolerated in point tables (the
  cross-vendor openai run's 281 498 rows); grader/harness JSON excluded from
  evidence; cp1252-safe re-run output; `grade_selfrun --scratch`; the full-task
  verdict labelled post-hoc in the grader, its JSON (`verdict_kind`) and
  `RERUN-CONVENTION.md`, which also states the `python -I -X utf8` change.
  Correction for the record (review B finding 1): the PR text and the issue
  addendum say none of the five committed gsplat runs wrote the point set; the
  openai cross-vendor run did write all 281 498 points.
* **#8 / #13**: marked exploratory (`evidence/second-lab/EXPLORATORY.md`, with
  the path mapping and the review's reading notes). Their files are otherwise
  as he committed them.
* **`df3ee77`**: its message claims an F2 fix that the commit does not contain;
  the port's message says so. PR #4 is the F2 fix.

## 5. Fixture re-pin (base procedure F-AC-6)

After every spec and loader change, `run_gate_reference.py` failed ("fixtures
carry THIS spec and THESE loaders": 64 embedded files differ). Every fixture
was rebuilt by its own builder from this tree and `fixtures/record_fixtures.py`
re-recorded the pins. `spec_sha256` `225072870294…` → `c46c3435eaf3…`
(`crate-synthetic`, the directory fixture's subset: `049a13d6…` → `ddba2d95…`).
The four author-lab builders used the author's inputs on the assembling host.
The frozen gauntlet fixtures (`roundOW/mini-v1.werk`, `roundSR/selfrun-v1.werk`)
were not rebuilt.

| fixture | before: bytes, sha256 | after: bytes, sha256 | in git |
|---|---|---|---|
| `fixtures/crate-v1.werk` | 13931978, `885a29038364849ee82cc65a7876299ac91bc666cfd4637d476079c88965972d` | 13936014, `fc8fe4f8a8e80843437785356b34c86420a481fde5ae12eb6a1ed1be1f306ed0` | no (asset) |
| `fixtures/crate-v1-damaged.werk` | 13933130, `3771330048d3a1255e72079520397e3c16e698517ad369fc0b62aa7de702c73c` | 13937166, `059324b60c975fc24ba3e55ab7e506cc6ba7d3fedacaeafe40b3bc30657eff53` | no (asset) |
| `fixtures/crate-tex-v1.werk` | 1143485, `c7958c9f3d48d3807ac7c37859f92f5fabe9ef2a29244cbb034e2213ab3fe573` | 1146946, `27e6574476d4186abebd38ecabca6f42356fae6ef619a35362be1cb8285c3b86` | yes |
| `fixtures/ista-varun-v1.werk` | 10473910, `b666e4a191212e87dcec99d681e45438678629f2c4e209ee302dc6d7929c9b4a` | 10477946, `11cb754fc0f040304b5f5b9d61d9a0ae807196feefae3770f16c3bfde4655c36` | no (asset) |
| `fixtures/humanoid-retarget-v1.werk` | 1760876, `935300098594efe1c8e24a286e6fded21239a87f279ba0beb912f252fb2cd7cb` | 1764924, `1f9a45e515e0c2ef6ef06a69a76a6324e9f3337cde11b621b84a80f4efbc728d` | yes |
| `fixtures/gsplat-v1.werk` | 30485454, `8ae411d1feb2dbefd439347dd7539ff439865916b1bdb6a37967e0f217433ebd` | 30489490, `36482595d13ecf5bc748f75b09bb78b8c3c2936ae6695e19f48a99b2acee7f2b` | no (asset) |
| `tests/fixtures/crate.werk` | 849012, `8894abc7741acd8cfb5209ff1524aef4d1ac22ccbe59d39228b9fbbde3c47e7e` | 853051, `5e27e17c7fc3b721fb8ebf210123e07da8a085893c75b04008afc2ff47ff5354` | yes |
| `fixtures/crate-cc0-lean-v1.werk` | 1478048, `d0f93d2fd6a011f9405dc7d55ee8cc2de751a46701a44316e5c1a500e2decd9b` | 1481529, `299ded3d7d9f9935b4aa1611a57ce1ebe062746f03a2eccc9fc947b9620f60cc` | yes |
| `fixtures/crate-cc0-lean-v1-damaged.werk` | 1479251, `8edd9e20fcf63d8ed762b401db63cb08f94bac2bbd076d809a70f5667a853acb` | 1482732, `51752bd1b2160ea2d71e50306204850f72e6831e104be46befc0697d3913c51c` | yes |
| `fixtures/crate-cc0-full-v1.werk` | 1531623, `57a89de514eca180bfd6709475efefd4727ba1e9a48a211e73b18a3153c4a8f3` | 1535104, `4b62cd9ab61cda099762f5b7fa6bb7b828c018e8abbb41f6e4be028e03281e31` | yes |
| `fixtures/crate-cc0-full-v1-damaged.werk` | 1532826, `72802ac7731c978659fd3a26e1c23193861542e4ea25df775160798ca7e1d643` | 1536307, `3ae6b6356472d92187da3e04a41bacf945baae716642e804bb1b6b2f4af07d63` | yes |
| `fixtures/image-cc0-v1.werk` | 5532277, `0ae9db458cafdb48af9b6152ecb8e997790ac267d0baa28d5e156af74df923cb` | 5535758, `582489761b29f2a2f02a2539b9d642684cb94fe1e6fb89eeb9b173fb5de27358` | no (asset) |
| `fixtures/image-cc0-v1-damaged.werk` | 5533326, `36e44d5778b64afdd2ce8537bcea9acb5c883b380ba5cc1fd846deaab7f28d2d` | 5536807, `d841db4d83f66ac292a0da641ca27883178a5db6ed56762de35af608c8cb0fac` | no (asset) |
| `fixtures/gsplat-cc0-v1.werk` | 1746891, `b4402e10f36653e6732d05396380fe57bc4d936d8ab8d7cae27b005acc72eda6` | 1750927, `43f9bea9a027c911e9e437d1f48c8f99d23e474d87ba1640d8855ea590947046` | yes |
| `fixtures/gsplat-cc0-v1-damaged.werk` | 1747941, `0a41f0129a373c8a2792ec5d9206fc36ff952e045f4321d34f6f6d820d234f6a` | 1751977, `44d5334d2ed5323fe66c1b92040d8dde96aa3f70f04a6136b4f900538d257832` | yes |
| `fixtures/crate-cc0-lean-v1-deflated.werk` | 595340, `a1abfa5aa7dea08d6cea8c7034fc5f4358167bc10c7206c08f3b202aae572066` | 596366, `185d5e693e4f17a93beecaa559f1d20e75e3a37bd5c2ebe65151a61722b937cb` | yes |

## 6. Getting the files that are not in git

`RELEASE-ASSETS.md` lists every asset with its size and sha256 and the URL
placeholder `{RELEASE_BASE_URL}`. `python tools/fetch_fixtures.py --base-url
<URL>` (or `--from-dir <mirror>`) fetches into place and refuses any hash
mismatch; `--check` only verifies. `python tools/release_assets.py` regenerates
the list (`--copy-to DIR` fills an upload folder; `--check` compares).

## 7. Gates, before and after

Table 11 of the paper, same rows, same format. Measured on the assembling host
(Windows 10, RTX 4090, Python 3.12.8 (numpy 2.5.2, Pillow 12.3.0), rustc 1.94.0, MSVC 2022, MSYS2 gcc
15.2.0, Blender 4.2.1). "Before" is the base `6bf77f3` exported unchanged into
a scratch tree; "after" is this repository at the release commit. Both with
`WERK_LAB` pointing at the author's tree (so the author-lab clauses run as
they did in the base's own measurement). `git status` was clean after every
gate in both trees: no gate mutated a tracked or untracked file.

| Gate (harness) | Before: base `6bf77f3` | After: release `main` | After: fresh clone, `WERK_LAB` unset, assets fetched |
|---|---|---|---|
| Reference core, three faces (`tests/run_gate.py`) | 11 PASS, 0 FAIL, 1 SKIP | 11 PASS, 0 FAIL, 1 SKIP | 11 PASS, 0 FAIL, 1 SKIP |
| Golden fixture (`tests/run_gate_a.py`) | 10 PASS, 0 FAIL, 0 SKIP | 14 PASS, 0 FAIL, 0 SKIP | 14 PASS, 0 FAIL, 0 SKIP |
| Enrichment pipeline (`tests/run_gate_3b.py`) | 19 PASS, 0 FAIL, 0 SKIP | 19 PASS, 0 FAIL, 0 SKIP | 0 PASS, 4 FAIL, 0 SKIP (exit 1) |
| Retarget, three foreign rigs (`tests/run_gate_6.py`) | 34 PASS, 0 FAIL, 0 SKIP | 34 PASS, 0 FAIL, 0 SKIP | 23 PASS, 0 FAIL, 1 SKIP (exit 1) |
| Image profile fixture (`tests/run_gate_9.py`) | 15 PASS, 0 FAIL, 0 SKIP | 17 PASS, 0 FAIL, 0 SKIP | 16 PASS, 0 FAIL, 1 SKIP (exit 1) |
| Splat, tools, self-regeneration (`tests/run_gate_12.py`) | 18 PASS, 0 FAIL, 0 SKIP | 19 PASS, 0 FAIL, 0 SKIP | 18 PASS, 0 FAIL, 1 SKIP (exit 1) |
| Blender adapter (`adapters/blender/test_gate.py`, Blender 4.2.1) | 20 PASS, 0 FAIL, 0 SKIP | 20 PASS, 0 FAIL, 0 SKIP | 20 PASS, 0 FAIL, 0 SKIP |
| Store, whole-blob and chunked (`store/`, pytest) | 59 tests, 0 failed, 0 skipped | 59 tests, 0 failed, 0 skipped | 58 tests, 0 failed, 1 skipped |
| CC0 public crate (`tests/run_gate_cc0_public.py`) | 18 PASS, 0 FAIL, 0 SKIP | 20 PASS, 0 FAIL, 0 SKIP | 20 PASS, 0 FAIL, 0 SKIP |
| CC0 image (`tests/run_gate_cc0_image.py`) | 11 PASS, 0 FAIL, 0 SKIP | 11 PASS, 0 FAIL, 0 SKIP | 11 PASS, 0 FAIL, 0 SKIP |
| CC0 splat (`tests/run_gate_cc0_gsplat.py`) | 10 PASS, 0 FAIL, 0 SKIP | 11 PASS, 0 FAIL, 0 SKIP | 11 PASS, 0 FAIL, 0 SKIP |
| Fixture pins (`tests/fixture_pin.py`) | 16 of 16 match | 16 of 16 match | 16 of 16 match |
| ArtCraft corpus (`tests/run_gate_artcraft.py`) | 90 PASS, 0 FAIL, 0 SKIP | 90 PASS, 0 FAIL, 0 SKIP | 0 PASS, 0 FAIL, 1 SKIP (exit 1) |
| Container (`tests/run_gate_container.py`) | 25 PASS, 0 FAIL, 0 SKIP | 25 PASS, 0 FAIL, 0 SKIP | 25 PASS, 0 FAIL, 0 SKIP |
| Envelope magic (`tests/run_gate_magic.py`) | 22 PASS, 0 FAIL, 0 SKIP | 22 PASS, 0 FAIL, 0 SKIP | 22 PASS, 0 FAIL, 0 SKIP |
| Reference consistency (`tests/run_gate_reference.py`) | 19 PASS, 0 FAIL, 0 SKIP | 19 PASS, 0 FAIL, 0 SKIP | 19 PASS, 0 FAIL, 0 SKIP |
| Writing walkthroughs (`tests/run_gate_writing.py`) | 26 PASS, 0 FAIL, 0 SKIP | 26 PASS, 0 FAIL, 0 SKIP | 26 PASS, 0 FAIL, 0 SKIP |
| Golden fixture with `--rebuild` (L1/L2/L3, PR #6) | not run (the base's `--rebuild` writes into `fixtures/`, review B) | 19 PASS, 0 FAIL, 0 SKIP | not run |
| Reference core, `cargo test --release` | 82 tests, 0 failed (28 unit, 25 conformance, 29 profiles) | 84 tests, 0 failed (28 unit, 27 conformance, 29 profiles) | built, not re-tested |
| Unreal engine-free core (`adapters/unreal/tests/build_gate.bat`, MSVC) | 10 PASS, 0 FAIL | 10 PASS, 0 FAIL | not run |
| Unreal round trip (UE 5.7) | not run | not run | not run |
| Unreal live editor control | not run | not run | not run |
| Game engine consumer (CUB) | not run | not run | not run |
| Single-file loaders standalone (`python -I`, bare `rustc -O`, MSYS2 `gcc -std=c99 -O2 -Wall -Wextra`), `--verify --strict` over the 16 pinned fixtures | not run | 48 of 48 exits as expected (0 for the 11 clean, 1 for the 5 damaged, in all three) | not run |

Notes on the table.

* The SKIP in the first row is the one the paper describes: this host's MinGW
  `gcc` exits 1 with no diagnostics when the gate calls it; the same C source
  compiles under MSVC in the next clause, and compiles cleanly (one
  `-Wformat-truncation` warning) with MSYS2's `bin` first on `PATH` (last row).
  That is the whole cause (release finding N2): Git for Windows' `/mingw64/bin`
  precedes MSYS2's on PATH and `cc1.exe` loads the wrong DLLs; the toolchain is
  not broken. Branch `release-fixes` runs every compiler with its own `bin`
  first, and the SKIP is gone (`RELEASE-FIXES.md`).
* The count increases are the clauses PR #6 added (Gate A 10 → 14 includes PR
  #11's clause 6b with its four rows; Gate 9: L1/L2/L3; Gate 12: the separate
  whole-file clause; CC0 crate and splat: builder determinism).
* Fresh clone: `git clone` of `main`, `tools/fetch_fixtures.py --from-dir`
  the asset folder, `cargo build --release`, `WERK_LAB` unset. The exits of 1
  are SKIPs and FAILs of author-lab inputs only: Gate 3b has no input of its
  own and reports its three absent GLBs as FAIL (as the base does); Gate 6
  skips the Unreal mannequin rig (Epic content, never redistributed) and so
  measures two rigs, 23 clauses; Gates 9 and 12 skip L3 and the large PLY
  ingest; the ArtCraft corpus is not in this repository; the store suite skips
  its real-corpus test.
* `git status --porcelain --untracked-files=all` was empty after every gate
  in all three columns.

## 8. Not run, not done

* Unreal round trip and live editor gates: this host has UE 5.8 only; the
  adapter targets 5.7. The engine-free C++ core gate ran (table).
* The CUB consumer gate (author-lab only, ruling R2).
* The Unreal C++ exporter has no dangling-edge guard (PR #11 change 2): not
  compiled here.
* The gauntlet rounds were not re-run (W4), and no Linux or second-OS run was
  made here (W3).
* The negative-control tarball was built and its sha256 listed; it was not
  extracted and re-graded here.
* Gate 3b on a machine without the author's GLBs FAILs instead of SKIPping
  (unchanged from the base). A CC0 input for it is a follow-up.
* The PR #13 ledger's `repo:` pointers name the PR layout, not
  `evidence/second-lab/` (EXPLORATORY.md maps them); `ledger/check.py` was not
  run against this tree.

## 9. Open questions for Gregor

1. **Licence** (LICENSE-PENDING.md): PolyForm-NC, MPL-2.0 or other; and the
   `license = "MIT"` in `core/Cargo.toml`.
2. **Yuvraj's rulings** — the provisional answers used here: #11 accepted;
   PASS = recorded criteria, the full-task re-grade beside it as post-hoc;
   S-DS-6 accepted; the negative control is exploratory, not
   "pre-registered". Confirm or reverse; a reversal of #11 needs another
   fixture re-pin.
3. **The CUB extension in the spec tree** (`spec/extensions/x.cub.v1.*`,
   SPEC §8, SPEC-3D-ENTITY, MANIFESTO, WHITEPAPER): kept as in the base and the
   earlier public snapshot. Curtain-down asks for the paper's wording only;
   trimming it is a spec change and a re-pin.
4. **Ken Gamble** on the manifesto and README author line (unchanged here).
5. **Release asset host**: `{RELEASE_BASE_URL}` is a placeholder; the earlier
   snapshot used a personal web host. Where do the 11 assets go?
6. **Gauntlet run records keep the agents' recorded workspace paths** (drive
   letter and folder names, no host or user). Keep as evidence, or redact
   mechanically before the public flip?
7. **`image-cc0-v1` (5.5 MB)** is out of git only by the 5 MB rule; it is
   CC0 and rebuildable. Keep it an asset, or allow it in git?
8. **Private inputs** of the author-lab clauses (DECISIONS question 6): share
   them with the second lab, or keep the clauses author-lab?
