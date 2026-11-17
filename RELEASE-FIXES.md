# Release fixes — branch `release-fixes` (workstream W1b)

Made 2026-11-07 on top of `main` `fa32df8`, against the findings of the
evidence matrix (`evidence/EVIDENCE.md` of the release workspace, items
N1–N11) and of the agent re-run (`evidence/gauntlet/record/RESULTS.md` §3).
One commit per finding; every commit message names its finding and says, where
spec and code disagreed, which was right and why. Nothing here was pushed.

## 1. What changed, by finding

| finding | what was wrong (measured) | fix | commits |
|---|---|---|---|
| N1 | the paper's fixtures were built from a CRLF working tree; `text=auto` left the text/binary decision for spec and loaders to git's heuristic | `spec/**`, `loaders/**` and the Blender add-on's vendored copies are `text eol=lf` explicitly; the binary examples stay binary | `8a0ed14` |
| N2 | "broken toolchain" SKIP: Git for Windows' `/mingw64/bin` precedes MSYS2's on PATH, `cc1.exe` loads the wrong DLLs (reproduced: exit 1 silent; 0 with its own bin first) | every gate runs gcc/clang/g++ with the compiler's own bin first on PATH; SKIP text states what was measured; three records and RELEASE-ASSEMBLY.md corrected | `a30b48a` |
| N3 | gsplat-v1 recorded `platform`/`runtime_version`; image fixtures' PNGs were Pillow's zlib-ng (Windows) or stock-zlib (Linux) streams; crate-tex used `zlib.compress`; the retarget fixture followed ext4 directory order and recorded last-bit libm noise | `pipeline/det_png.py` (pure-Python deterministic PNG/zlib encoder) for every builder PNG; no host strings in tool configs; sorted directory walks; retarget measurement records rounded to 12 significant digits; Gate 9 L1 no longer guesses a deflater | `3b9f034` `986fbeb` `8eacd2e` `646b4bc` |
| N4 | numpy unpinned (three numpy versions, three gsplat fixtures); `requirements-build.txt` claimed no sensitivity | `numpy==2.5.2`, `scipy==1.16.3` pinned beside `Pillow==12.3.0`, each with its measured reason | `3e54c0a` |
| N5 | `humanoid-retarget-v1` carried the absolute path of the builder's checkout | repository-relative path | `c899f27` |
| N6 | core: damaged `SIGNATURE.json` → `absent`, exit 0; `"algorithm": "x-unknown"` → `signed-and-valid` | present-but-unreadable → `present-and-invalid` (error); foreign algorithm → `unverified` (warn, ABI 3); werkc prints the fixed state word first; SPEC §6 says so | `77b91b0` `b710666` |
| N7 / N7b | loaders disagreed on structural damage (5 500 of 17 442 offsets); C accepted non-UTF-8 manifests; Rust refused on a damaged CD name and compared local-header methods; version fallback exited 0 in the loaders; Python loader tracebacked on 165 single-bit flips | one rule set for all four readers (MINI-SPECS §5.4 "Reader rules for a damaged container"); `--strict` = "an `error` entry exists" (SPEC §10.1); a malformed node dies, no traceback ever; no `nodes` array → `manifest-structurally-invalid` (SPEC §12.1 clarified) | `e82a446` `1abc465` `10aa250` |
| duplicate entry names | unspecified; py took the last record, C/Rust the first | refused whole (`bad-container`, exit 2) by core (port of werk-core `zipstore.rs` from release-cli `3e57ce0`, byte-identical), the three loaders; SPEC §1 + §10.1 table + MINI-SPECS §5.4 | `77b91b0` `e82a446` `10aa250` |
| N8 (not in the brief) | `double(long long(D))` rejected by g++ | `static_cast`s | `b49194e` |
| N11 | container gate built a different zip64-extra file on Python ≤ 3.10; CC0-image failure text blamed the fixtures | gate normalises the local headers itself (25/0 on 3.10.0 and 3.12.8); failure text lists the differing entries and the Pillow version; the store corpus path was already `WERK_LAB`-relative | `db42061` `ac69ae4` |
| W4 §3 F5 F6 F8 F9 F10 F11 F12 | see `evidence/gauntlet/record/RESULTS.md` §3 | §4 below | `4089588` `10aa250` |
| W2 damage_agree (a) | werk-core dropped a node whose `active` key was damaged (census 17 / 0 dead; loaders and libs: 18 / 1 dead) | the node stays in the census, dead, under its id (SPEC §12.1) | `35df34f` |
| W2 damage_agree (b) | `werk_read.py` kept a node alive when a file record lost `size` | the node-shape check requires path, sha256 and integer size; SPEC §12.1 lists them | `a15af66` |
| (found adding (a)/(b) to the harness) | C and Rust `--verify` reported "1 dead" without naming a node killed by a malformed record | both print one line per dead node | `7316263` |
| re-pin | — | every fixture rebuilt by its builder, Blender add-on re-vendored | `a60bfcf` `7015e23` `07a2a7e` `4ba7792` |

## 2. Spec diff, in one screen

`git diff fa32df8 -- spec`: 7 files, MINI-SPECS.md, SPEC.md, WRITING-3D-ENTITY.md,
WRITING-IMAGE.md, extensions/x.cub.v1.md, extensions/x.cub.v1.baked.layout.txt,
schemas/core.audio.effect.schema.json. No behaviour of a conformant package
changed; every addition states a rule a reader already had to choose:

* **SPEC §1** one name, one entry (duplicate → `bad-container`); §10.1 code table row says so.
* **SPEC §6** absent = not in the container; unreadable → present-and-invalid; foreign algorithm → `unverified` (the fourth word describes the reader); a reader without Ed25519 still checks object + `manifest_sha256`.
* **SPEC §10.1** a version fallback is not a clean load: the passed-over file's error entry makes the status 1 (bootstrap loaders: under `--strict`); `--strict` = "an `error` entry exists", no warning promoted.
* **SPEC §12.1** the container-scoped structural trigger is the graph (`nodes` missing / not an array, manifest not an object); a node whose own structure is unusable — including a `files[]` entry without path, sha256 or integer size — dies under its id, the rest loads (law 3).
* **MINI-SPECS §5.2/§5.4** bit 11: MUST for non-ASCII names, MAY be clear for ASCII (the zip-library route is conformant), readers never reject a clear bit 11; no duplicate names; entry order SHOULD; unmatched `entry_order` elements are skipped; six reader rules for a damaged container (EOCD with exact comment length; walk `total records`, not the byte size; lossy name decoding; bit 3 refuses, bit 0 per entry; duplicates refuse; the central directory is the authority, the local header contributes only its signature and lengths).
* **SPEC §2.1** `payload_file`: the field is PROPOSED, the resolution order is NORMATIVE; set-type nodes (`core.spec`, `core.loader`) are not "ambiguous" and a verifier does not report it.
* **SPEC §3.9 + schema** `clap_score` and `prompt_used` nullable (null = not measured / not from a prompt; writing 0 is a fabricated measurement); the WAV is the payload, the JSON the descriptor.
* **SPEC §2 `total_size_bytes`** is not the `.werk` file size.
* **MINI-SPECS §1** the actual list of big-endian places; **§12.2** three package states, four words.
* **WRITING-3D-ENTITY / WRITING-IMAGE §7** nine checkable acceptance rules (and which of them the bundled loader and the core check) instead of "run the bundled loader"; the "6 nodes" census depends on the donor's loader nodes (8 from a donor with all three); §6 bit 11 as above.
* **x.cub.v1** WKX0..9 serve a profile's own `core.*` binaries and `x.*` alike (SPEC §3.1 rule 4); the layout file's path is `spec/extensions/…`.

**spec_sha256** `c46c3435eaf3dcb9003e6b3671470b5ab126e07ff1a6d0f06b050975d3dbe633` →
`12b0e574e00e6d5fc78625ee750ae8517058ace68481cdfd3e26917b4d3e600a` (first re-pin) →
**`55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3`** (after the W2 follow-up).
Directory fixture's subset (`crate-synthetic`): `ddba2d95643428fef156279cee081d6f0fb2c235334435d8a460db3f41d43803` →
`ab73f862e7fb3fc2eef6c2d4fa8fe82e62f20c87477763fdffc0f712c1c8628c` → `58324e2d409f05e4c7d0b5980c93db19dcc400211bb8d0e13df25560e1a3445d`.

## 3. Fixtures, old and new

Every fixture rebuilt by its own builder (author-lab builders from the W3
input set, which reproduced the shipped `fa32df8` fixtures on this machine);
assets copied to `stage\assets-fixes\` of the release workspace, in the
`stage\assets\` layout by `tools/release_assets.py --copy-to`
(`RELEASE-ASSETS.md` regenerated, `--check` matches 11 files).

| fixture | before (`fa32df8`): bytes, sha256 | after (`release-fixes`): bytes, sha256 | in git |
|---|---|---|---|
| `fixtures/crate-v1.werk` | 13936014, `fc8fe4f8a8e80843437785356b34c86420a481fde5ae12eb6a1ed1be1f306ed0` | 13965429, `e13b8ba90f08eca8ed6d0a57f21f38c41d78229f10e335746e5b86f39b4fa6d2` | no (asset) |
| `fixtures/crate-v1-damaged.werk` | 13937166, `059324b60c975fc24ba3e55ab7e506cc6ba7d3fedacaeafe40b3bc30657eff53` | 13966581, `f3c82ba8802fc1160ccae25465522696af32c4c91133b917b8f36df3acca2edc` | no (asset) |
| `fixtures/crate-tex-v1.werk` | 1146946, `27e6574476d4186abebd38ecabca6f42356fae6ef619a35362be1cb8285c3b86` | 1164737, `2aa64f9d1f23f3cf4b350548e3638d5462fd24cc121da0cdefc4cc411badbb77` | yes |
| `fixtures/ista-varun-v1.werk` | 10477946, `11cb754fc0f040304b5f5b9d61d9a0ae807196feefae3770f16c3bfde4655c36` | 10881124, `9bacd8022198041730a35d93fd66098ce685c54681f07bf2df88e4851e825aa1` | no (asset) |
| `fixtures/humanoid-retarget-v1.werk` | 1764924, `1f9a45e515e0c2ef6ef06a69a76a6324e9f3337cde11b621b84a80f4efbc728d` | 1794117, `b0dda1993f3ca5ddfa1bdfe50f02d1f2ef98f69b76d8f3531f5c04b3c0910239` | yes |
| `fixtures/gsplat-v1.werk` | 30489490, `36482595d13ecf5bc748f75b09bb78b8c3c2936ae6695e19f48a99b2acee7f2b` | 30519513, `fbe7b32c3f2f9b1c311d718a5ed1d66b962331f26b4be689e2e4665454e3a86f` | no (asset) |
| `tests/fixtures/crate.werk` | 853051, `5e27e17c7fc3b721fb8ebf210123e07da8a085893c75b04008afc2ff47ff5354` | 877496, `3646ca4290baf8a2b000961d1ca6b5d8ee867cb414a8711edbf46ec05b647c23` | yes |
| `fixtures/crate-cc0-lean-v1.werk` | 1481529, `299ded3d7d9f9935b4aa1611a57ce1ebe062746f03a2eccc9fc947b9620f60cc` | 1543293, `0e3149db90b086fa964caa362c44bde57a970c891b9ebb9dff36437c0220fc50` | yes |
| `fixtures/crate-cc0-lean-v1-damaged.werk` | 1482732, `51752bd1b2160ea2d71e50306204850f72e6831e104be46befc0697d3913c51c` | 1544496, `83ccaa77aa063406501cccdd795306ec0551959733f90c538407fd919d17b8db` | yes |
| `fixtures/crate-cc0-full-v1.werk` | 1535104, `4b62cd9ab61cda099762f5b7fa6bb7b828c018e8abbb41f6e4be028e03281e31` | 1604099, `a596a302470c1741e91e8dc0053a61af600bcbb4461b48ea8903eaf41b933a4d` | yes |
| `fixtures/crate-cc0-full-v1-damaged.werk` | 1536307, `3ae6b6356472d92187da3e04a41bacf945baae716642e804bb1b6b2f4af07d63` | 1605302, `2c02340abf1773ed7b29f5e80d373ce0b14ff1b8e4b46b813e397eb5e6091428` | yes |
| `fixtures/image-cc0-v1.werk` | 5535758, `582489761b29f2a2f02a2539b9d642684cb94fe1e6fb89eeb9b173fb5de27358` | 5803605, `a45c875ef2620ae4b2f26900869538fa952f57719d8847fbab7e40fda48f2353` | no (asset) |
| `fixtures/image-cc0-v1-damaged.werk` | 5536807, `d841db4d83f66ac292a0da641ca27883178a5db6ed56762de35af608c8cb0fac` | 5804654, `027339f56d3e08fcdba13907ff79c9603010755458fc995ec1a5c73cf3945eb2` | no (asset) |
| `fixtures/gsplat-cc0-v1.werk` | 1750927, `43f9bea9a027c911e9e437d1f48c8f99d23e474d87ba1640d8855ea590947046` | 1780342, `9f576abe10a8ad3e0fbfe3243570e0493444ec8a6d3a3c765eefc08b3f4e8c1a` | yes |
| `fixtures/gsplat-cc0-v1-damaged.werk` | 1751977, `44d5334d2ed5323fe66c1b92040d8dde96aa3f70f04a6136b4f900538d257832` | 1781392, `8b90cb36b5730777458aacb6ae792856529ddd9294efee94912d71a04d7a3087` | yes |
| `fixtures/crate-cc0-lean-v1-deflated.werk` | 596366, `185d5e693e4f17a93beecaa559f1d20e75e3a37bd5c2ebe65151a61722b937cb` | 647860, `74318b4e5837d350ccdadfcc2ca4e326cdf755635087ee900fad8c5883dd6b22` | yes |


## 4. W4 §3 findings: what was fixed here and what is W6's

Fixed in the release spec (commit `4089588`, bit 11 in `10aa250`): **F5**
(x.cub layout path), **F6** (WKX0..9 wording in the x.cub texts), **F8** (bit
11 vs "use your zip library"), **F9** (checkable writing rules), **F10**
(`payload_file` status, set-type nodes), **F11** (`core.audio.effect` can say
"not measured"), **F12** (six-vs-eight census, `total_size_bytes`, byte-order
overview, three vs four words, entry order SHOULD / unmatched `entry_order`
elements). The release spec's own 12.2 recovery table and ENVELOPE §2 already
gave WKX0..9 to profile `core.*` binaries.

**Not fixed — ArtCraft capsules only, for W6:** F1 (simple.werk preview does
not depict the document), F2 (composite size vs PROFILE-RASTER-LAYERS §3.12),
F3 (sales.werk content), F4 (the 3D-entity SPEC.md shipped in raster and sheet
capsules), F6 in CRAFT-BASE (core cell bands assigned WKX0/WKX1 — consistent
with the release rule, but the capsules' older SPEC §12.2 contradicts it), F7
(ENVELOPE §3 `input_hash` vs computed bands), F12 parts in PROFILE-RASTER (no
compressed pixels vs zlib tiles; ENVELOPE "no compression" vs zlib-wrapped
tiles; §7.3/§7.5 copy-list wording), PROFILE-SPREADSHEET (preview vs minimal
recipe; undefined 5×7 font; computed.layout §4; "six counts"; schema
descriptions; value kinds), the craft profiles' `loaderMeta` capability lists
(missing `summarize-points`/`summarize-gsplat`), and the crate LICENSE
"FULL LICENCE TEXT" wording of the craft samples.

## 5. Gates, three machines

Harness `evidence/harness/run_all.py` (W3), runs at `4ba7792`:
<lab-win> `20261107T190558Z-4ba7792-w1b-final2` (Windows 10, Python 3.12.8, Blender 4.2.1, MSVC + MSYS2 gcc 15.2),
<lab-linux-1> `20261107T190559Z-4ba7792-w1b-final2` (Ubuntu 24.04.3, Python 3.12.3, gcc 13.3, clang 18.1, Blender 5.0.1),
<lab-linux-2> `20261107T190601Z-4ba7792-w1b-final2` (Ubuntu 24.04.5, Python 3.12.3, gcc 13.3, clang 18.1, no Blender),
all with the author-lab inputs (`WERK_LAB`, `--inputs`). Raw output: `evidence/runs/<machine>/<run id>/` of the release workspace
(machine names there are the hosts' own).

| gate | <lab-win> (Windows) | <lab-linux-1> | <lab-linux-2> |
|---|---|---|---|
| Fixture pins (tests/fixture_pin.py) | PASS 16/0 | PASS 16/0 | PASS 16/0 |
| Reference core, three faces (tests/run_gate.py) | PASS 11/0 | PASS 11/0 | PASS 11/0 |
| Golden fixture (tests/run_gate_a.py) | PASS 14/0 | PASS 14/0 | PASS 14/0 |
| Enrichment pipeline (tests/run_gate_3b.py) | PASS 19/0 | PASS 19/0 | PASS 19/0 |
| Retarget, three foreign rigs (tests/run_gate_6.py) | PASS 34/0 | PASS 34/0 | PASS 34/0 |
| Image profile fixture (tests/run_gate_9.py) | PASS 17/0 | PASS 17/0 | PASS 17/0 |
| Splat, tools, self-regeneration (tests/run_gate_12.py) | PASS 19/0 | PASS 19/0 | PASS 19/0 |
| Blender adapter (adapters/blender/test_gate.py) | PASS 20/0 | FAIL 19/1 | NOT RUN |
| Unreal round trip, UE 5.7 (adapters/unreal/tests/roundtrip_gate.py) | NOT RUN | NOT RUN | NOT RUN |
| Unreal engine-free core (werk_gate, built here) | PASS 10/0 | PASS 10/0 | PASS 10/0 |
| Unreal live editor control (proof_session.py) | NOT RUN | NOT RUN | NOT RUN |
| Game engine consumer (cargo test -p cub-werk) | NOT RUN | NOT RUN | NOT RUN |
| Store, whole-blob and chunked (pytest store/tests) | PASS 59/0 | PASS 59/0 | PASS 59/0 |
| Store CDC measurement (store/tests/measure_gate_cdc.py) | PASS 1/0 | PASS 1/0 | PASS 1/0 |
| Store whole-blob corpus measurement (store/tests/measure_gate.py) | PASS 1/0 | PASS 1/0 | PASS 1/0 |
| Reference core, cargo test --release (core/) | PASS 88/0 | PASS 88/0 | PASS 88/0 |
| CC0 public crate (tests/run_gate_cc0_public.py) | PASS 20/0 | PASS 20/0 | PASS 20/0 |
| CC0 image (tests/run_gate_cc0_image.py) | PASS 11/0 | PASS 11/0 | PASS 11/0 |
| CC0 splat (tests/run_gate_cc0_gsplat.py) | PASS 11/0 | PASS 11/0 | PASS 11/0 |
| Container (deflate, zip64) (tests/run_gate_container.py) | PASS 25/0 | PASS 25/0 | PASS 25/0 |
| Envelope magic (tests/run_gate_magic.py) | PASS 22/0 | PASS 22/0 | PASS 22/0 |
| Reference consistency (tests/run_gate_reference.py) | PASS 19/0 | PASS 19/0 | PASS 19/0 |
| Writing walkthroughs (tests/run_gate_writing.py) | PASS 26/0 | PASS 26/0 | PASS 26/0 |
| ArtCraft corpus (tests/run_gate_artcraft.py) | PASS 90/0 | PASS 90/0 | PASS 90/0 |

Against `fa32df8` (W3): the reference core has **0 SKIP** everywhere (N2); Gate 9
17/0 and the CC0 image gate 11/0 and Gate 12 19/0 on **both Linux machines**
(were 15/2, 10/1, 18/1: N3); the Unreal engine-free core compiles and passes
on Linux (N8). The one red cell is Blender **5.0.1** on <lab-linux-1> (the add-on
targets 4.2 LTS; its rig clause raises inside Blender 5 — W3 measured the
same on `fa32df8`; adapter work, not touched here).

Same runs, named structural-damage cases (`evidence/harness/wh_cases.py`, new:
`active` / `size` / `sha256` / `versions` key renamed, `nodes` renamed,
duplicate README.txt, SIGNATURE.json not JSON, unknown algorithm, invalid UTF-8
key; every fixture that admits the case): **142 of 142 agree** on outcome class
and dead set across core, py, rs, gcc, clang on each of the three machines.

Same runs: signature tamper matrix 120 rows (15 signed fixtures × 8
variants) on each machine, **0 not as expected** — `alg-unknown` is now
`unverified` on 15/15, damaged/removed variants as specified; zip vs directory
form 16 fixtures, every reader equivalent; every loader extracts every node of
16 fixtures identically; release-libs cross-matrix (`stage/libs/tests/cross_matrix.py`
pointed at the new fixtures by the harness; libs not edited) **0 failures** on
all three (<lab-linux-1> without the JS readers: no Node.js there). NB the
cross-matrix's `ref-*` readers are the loaders bundled in `stage/libs`
(release `fa32df8`), not this branch's.

## 6. Cross-OS rebuild

Every builder run by the harness's determinism step on each machine, compared
with the pin:

| builder output | <lab-win> (Windows) | <lab-linux-1> | <lab-linux-2> | all equal |
|---|---|---|---|---|
| crate.werk | 3646ca4290ba (=pin) | 3646ca4290ba (=pin) | 3646ca4290ba (=pin) | yes |
| crate-cc0-lean-v1-damaged.werk | 83ccaa77aa06 (=pin) | 83ccaa77aa06 (=pin) | 83ccaa77aa06 (=pin) | yes |
| crate-cc0-lean-v1.werk | 0e3149db90b0 (=pin) | 0e3149db90b0 (=pin) | 0e3149db90b0 (=pin) | yes |
| crate-cc0-full-v1-damaged.werk | 2c02340abf17 (=pin) | 2c02340abf17 (=pin) | 2c02340abf17 (=pin) | yes |
| crate-cc0-full-v1.werk | a596a302470c (=pin) | a596a302470c (=pin) | a596a302470c (=pin) | yes |
| crate-cc0-lean-v1-deflated.werk | 74318b4e5837 (=pin) | 74318b4e5837 (=pin) | 74318b4e5837 (=pin) | yes |
| image-cc0-v1-damaged.werk | 027339f56d3e (=pin) | 027339f56d3e (=pin) | 027339f56d3e (=pin) | yes |
| image-cc0-v1.werk | a45c875ef262 (=pin) | a45c875ef262 (=pin) | a45c875ef262 (=pin) | yes |
| gsplat-cc0-v1-damaged.werk | 8b90cb36b573 (=pin) | 8b90cb36b573 (=pin) | 8b90cb36b573 (=pin) | yes |
| gsplat-cc0-v1.werk | 9f576abe10a8 (=pin) | 9f576abe10a8 (=pin) | 9f576abe10a8 (=pin) | yes |
| humanoid-retarget-v1.werk | b0dda1993f3c (=pin) | b0dda1993f3c (=pin) | b0dda1993f3c (=pin) | yes |
| crate-v1-damaged.werk | f3c82ba8802f (=pin) | f3c82ba8802f (=pin) | f3c82ba8802f (=pin) | yes |
| crate-v1.werk | e13b8ba90f08 (=pin) | e13b8ba90f08 (=pin) | e13b8ba90f08 (=pin) | yes |
| gsplat-v1.werk | fbe7b32c3f2f (=pin) | fbe7b32c3f2f (=pin) | fbe7b32c3f2f (=pin) | yes |
| ista-varun-v1.werk | 9bacd8022198 (=pin) | 9bacd8022198 (=pin) | 9bacd8022198 (=pin) | yes |
| crate-tex-v1.werk | 2aa64f9d1f23 (=pin) | - | - | yes |

`crate-tex` needs Blender 4.2 (only <lab-win> has it): rebuilt and pinned there
only; not cross-checked. `build_deflated_fixture.py` deflates with the
interpreter's zlib by design (the fixture's point is streams from an encoder
unrelated to the four inflaters); stock zlib 1.3.1 (Windows CPython 3.12) and
1.3 (Ubuntu) give the same bytes, a zlib-ng-linked Python (Windows CPython
3.14) would not.

## 7. Damage campaigns

Readers in every campaign: werk-core (`werkc verify`), `werk_read.py` (CPython 3.12),
`werk_read.rs` (bare rustc), `werk_read.c` with gcc 13.3 and with clang 18.1 —
the loaders with `--verify --strict`. Agreement = all readers give the same exit
class (ok / node / container; a traceback, panic, other exit or timeout is "crash").
All at `4ba7792`.

| campaign | machine, run | offsets | all agree | disagree | crash | spec-prediction violations |
|---|---|---:|---:|---:|---:|---:|
| exhaustive XOR 0xFF, `tests/fixtures/crate.werk` (877 496 B) | `<lab-linux-2>` `20261107T190812Z-4ba7792-w1b-damage-exhaustive2` | 877 496 | 877 496 | 0 | 0 | 0 |
| exhaustive XOR 0xFF, `crate-cc0-lean-v1-deflated.werk` (647 860 B) | same run | 647 860 | 647 860 | 0 | 0 | 15 (below) |
| stratified XOR 0xFF, all 16 fixtures (every zip-structure, manifest and signature byte + sampled payload) | `<lab-linux-1>` `20261107T190810Z-4ba7792-w1b-damage-stratified2` | 301 911 | 301 911 | 0 | 0 | 0 |
| named structural cases (`wh_cases.py`, 142 per machine) | the three gate runs of §5 | 3 × 142 | 3 × 142 (class **and** dead set) | 0 | 0 | — |
| stratified XOR **0x01**, `crate-cc0-full-v1.werk` (core, py, rs, gcc) | `<lab-win>`, harness `wh_damage` via a local driver | 17 441 | 16 924 | 517 (below) | 0 | 0 |

`fa32df8` for comparison (W3): 5 500 of 17 442 disagreeing on
`crate-cc0-full-v1.werk` (XOR 0xFF); 165 Python tracebacks under XOR 0x01; 24
version-fallback offsets with differing exit status. The two exhaustive files
are covered in all 41 regions each (EOCD, every central-directory and
local-header field, names, manifest, signature, payload), every region 100 %.

The **15 "violations"** are payload flips after which every reader says ok:
each damaged raw-deflate stream inflates to the identical bytes (stdlib zlib:
15 of 15), so the CRC-32 and sha256 over the uncompressed bytes are unchanged —
correct behaviour; "every payload flip kills its node" is false for
compressed entries.

The **517 XOR 0x01 disagreements** are all inside `SIGNATURE.json` and all of
one shape: werk-core exit 1, the bootstrap loaders exit 0. 469 are flips of a
signed field or a hex digit — the core's Ed25519 check fails
(present-and-invalid), the loaders carry no Ed25519 and say `unverified`, as
SPEC §10 step 4 [B] specifies; 48 leave the chain valid and break the
signature schema on an unsigned field (e.g. `werk_signature` → `verk_signature`:
`schema-invalid`, signature still signed-and-valid) — a JSON Schema finding the
bootstrap loaders do not look for. Neither is a reader fault; they are the
designed difference between a full reader and a bootstrap loader. XOR 0xFF
never produces them (it always breaks UTF-8, which every reader refuses alike).

## 7a. The release libraries on the N6 cases (checked, not edited)

On `crate-cc0-full-v1.werk` with `SIGNATURE.json` replaced by non-JSON, by
invalid UTF-8, with `"algorithm": "x-unknown"`, and removed:
`stage/libs` Python (`werk_single.py verify`), JS (`werk.js`) and ES3
(`werk-es3.js`) readers report present-and-invalid/exit 1,
present-and-invalid/exit 1, unverified/exit 0, absent/exit 0 — the same as
the fixed core. Duplicate entry names: refused (exit 2) since `3e57ce0`.

## 8. What remains

* **Blender 5.0.1** rig clause (<lab-linux-1>): adapter work for Blender ≥ 4.4's
  action API; the add-on is gated on 4.2.1 (<lab-win> 20/0).
* **Not run**: Unreal round trip and live-editor gates (no UE 5.7), the CUB
  consumer gate (private repo), crate-tex rebuild on Linux (no Blender 4.2),
  the harness's Python-version matrix (`pymatrix`) — with numpy pinned to
  2.5.2 and Pillow to 12.3.0, interpreters that cannot install those pins
  rebuild different fixtures by construction; the rebuild clauses then fail
  and say why.
* **The libs bundle** (`stage/libs/bundle`, spec `c46c3435…`) and every
  plugin's vendored copy predate this branch: re-bundle (W2) and re-vendor
  (W5) once this branch is merged; the cross-matrix's bootstrap readers are
  the old loaders until then.
* **`tests/fixtures/crate.werk`** carries a 22-file spec subset whose texts
  reference 31 files it does not carry (by the builder's design); not changed.
* **paper/v2/PAPER.md** lines 1319–1324 still call gcc broken (W7's).
* Bootstrap loaders without Ed25519 cannot see a signature flipped inside a
  hex string (they say `unverified`, the core `present-and-invalid`): a
  designed difference, invisible to XOR 0xFF damage (always invalid UTF-8)
  and to every campaign above, which agree on exit class.
* `package_rebuild.py` keeps its now-unused `--restock` code path.
* N9, N10 (graders, non-re-measurable numbers) were not in this brief.

## 9. History scan (whole branch: every commit message and every blob)

Pattern: absolute paths on drive F (backslash, slash or JSON-escaped), the
C-drive user-profile directory, the lab's host names, private IPv4 ranges. After rewriting this branch's messages
(`git filter-branch --msg-filter` over `fa32df8..release-fixes` only: the local
path quoted in the N5 commit and the host names in later messages replaced by
`<lab>` / `<lab-win>` / `<lab-linux-1|2>`; the first RELEASE-FIXES.md commit
dropped and this file re-added at the head; `main` untouched at `fa32df8`; the
pre-rewrite head is kept as the local branch `backup/release-fixes-pre-rewrite`):

* **Commit messages and blobs introduced by `release-fixes`: 0 hits**
  (25 commits, 100 new blobs).
* **Inherited from `main` (`fa32df8`), not rewritten here:** 3 commit messages
  with a drive-F path (`82cf22c`, `61fdf3e`, `817fd76`, all Yuvraj Puyam's PR commits);
  in the tree, 133 files with 699 hits: gauntlet run records and prompts under
  `gauntlet/roundDS|GF|HC|OW|SR|XV/` (the agents' recorded workspace paths, kept
  as evidence by W1's decision 4 / open question 6), `evidence/second-lab/…`
  (PR #8/#13 records, including 2 user-profile paths in `roundNC/RESULTS-NC.md`), and
  `paper/NUMBERS.md`, `paper/v2/NUMBERS.md`, `paper/STAGE8-RESULTS.md` (1
  user-profile path). No host name and no private IP anywhere in `main`. The one
  inherited hit inside a fixture (`humanoid-retarget-v1.werk`, N5) is gone.
