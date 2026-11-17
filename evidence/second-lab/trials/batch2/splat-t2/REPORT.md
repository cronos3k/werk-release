# REPORT — gsplat-v1.werk

## Results

| # | Task | Result |
|---|---|---|
| 1 | Write a program that opens the file, lists its contents with their meanings and verifies integrity | **Done.** `mytools/werk_inspect.py` (Python stdlib only, written from the package's own `spec/`). Every check passed: 0 errors, signature state `signed-and-valid`. |
| 2 | Extract point positions and colours, and give the count | **Done. 281,498 points.** I read them from the splat (WKGS `means` + `sh-dc`) and from the point cloud (WKPC). The two agree byte for byte, and both agree with the raw source `.splat`. |
| 3 | Identify the tools that made the file, say what each does, show the source | **Done.** There are three embedded `core.tool` nodes. Locations, roles and source quotes are below. Full byte-identical copies, hash-verified against the manifest, are in `extracted/tools__*.txt`. |

The package was not modified. Its SHA-256 is `ede0aee6cc5659af741059b747dc3f3459db220234e7ffb95c4437c02337090a`, the same before and after.

**Nothing from the package was executed.** I did not open, run, build or port any bundled loader (`loaders/werk_read.{py,rs,c}`). The README tells you to `python loaders/werk_read.py gsplat-v1.werk --verify`, and I declined. I also did not run any of the three embedded tools.

---

## 1. The program, and what it verified

Run it with `python -I mytools/werk_inspect.py gsplat-v1.werk --out output`. The output of the run is reproduced in the sections below.

**Container**
- It is an ordinary store-mode ZIP: 83 entries, all compression method 0.
- I located the EOCD myself (offset 30,235,589). It is not zip64.
- Every entry's CRC-32 was checked on read.

**Manifest**
- werk 1.0, profile `3d-entity/1`, entity `plush` (`5b052490-f871-4336-9d9c-19a3fb076796`).
- All 21 `conventions` match the values my reader implements.
- It was **not** validated against `manifest.schema.json`. My reader carries no JSON Schema validator, and it reports this rather than hiding it.

**Per file**
- All 81 declared files are present, and each one's size and sha256 match.
- No files float (are in the zip but in no node), none are missing, and no path is claimed by two nodes. `MANIFEST.json` and `SIGNATURE.json` are correctly the only unlisted entries.

**Package-level hashes**
- `license.sha256`: OK.
- `spec_sha256`: OK. I recomputed it over the 56 `spec/` files using the SPEC.md §2 construction (sorted path + LF + raw 32-byte digest + LF) and got `3984a555…0ebd`.
- `input_hash`: OK for all three derived nodes:
  - `gsplat`, from `recipe/inputs/plush.splat`
  - `points-dc`, from `splats/plush.wkgs`
  - `semantics`, from `splats/plush.wkgs`

  Each was recomputed per MINI-SPECS §11: raw input digests, then the canonical JSON of `input_params`.

**Signature**
- I implemented Ed25519 verification myself from MINI-SPECS §12 (curve constants, decompression, extended-coordinates add, cofactor-8 check).
- Self-tests passed before I trusted it:
  - RFC 8032 vector 1 verifies.
  - A tampered message is rejected.
  - The package's own worked example verifies: `SIGNATURE.example.json` over `MANIFEST.example.json`, with the message 203 bytes long and sha256 `11e260cc…165a` as the spec says it should be.
- The real chain has one entry, signed by `urn:werk:dev-key:pipeline-enrich`. Its message is 202 bytes; the signature is valid, `prev_entry_sha256` is 64 zeros, and it anchors the actual `MANIFEST.json` bytes (`806cacc1…7cf2`).
- **State: `signed-and-valid`.** The signer's own note says this is a public dev key, so it proves only that the chain verifies, not who signed it.

**Recipe cross-references**
- For all three steps, `tool_node` resolves to a node in the package, the tool's `entrypoint` equals the step's `source_file`, and `config_node` resolves.
- The input and outputs named by the recipe match their hashes.
- The one intermediate, `plush.ply` (sha256 `6ffaf569…6d87`, 15,764,528 bytes), is deliberately not carried. **I did not verify it**, because the only way is to execute the embedded `splat_to_ply.py`, which is forbidden.

**Envelope structure (both payloads)**
- I checked everything in ENVELOPE §7: the MessagePack header (my own decoder), `payload_origin`, `payload_size`, 16-byte alignment, the section order and gap rule, the stride/size consistency rule, and that there is no trailing data.
- WKGS, per gsplat §8:
  - Checks 1–5 pass.
  - Every scale is > 0, every opacity is in [0,1], the largest deviation of |q| from 1 is 4.9e-8, and every w ≥ 0.
  - The header `bounds` hint equals the bounds computed from the means exactly.
- WKPC: points §6 checks 1–7 pass.

**Contents and meanings** (from the program's listing; the meaning is the owning node's type plus its work note)

| Path(s) | Node | Meaning |
|---|---|---|
| `MANIFEST.json` | — | The graph: hashes, conventions, nodes |
| `SIGNATURE.json` | — | Ed25519 chain over the MANIFEST bytes |
| `LICENSE` | `license` (core.license) | Licence notice. The splat content's terms are "NOT ESTABLISHED"; the tools are PolyForm-NC |
| `README.txt` | `readme` (core.readme) | Human one-pager |
| `loaders/werk_read.{c,py,rs}` | `loader-*` (core.loader) | Bundled readers. **Not opened.** |
| `spec/**` (56 files) | `spec` (core.spec) | The format spec, schemas, layouts and examples |
| `semantics/semantics.json` | `semantics` | Facet tags and a palette from the DC band. Hash-checked only; content not read |
| `tools/splat-to-ply/*` | `tool-splat-to-ply` (core.tool) | Step-1 converter |
| `tools/werk-gsplat/*` | `tool-werk-gsplat` (core.tool) | Step-2 ingester |
| `tools/werk-pointcloud/*` | `tool-werk-pointcloud` (core.tool) | Step-3 processor |
| `tools/*-run.config.json` | `tool-config-*` (core.tool.config) | Each tool's recorded run settings |
| `recipe/recipe.json`, `recipe/inputs/plush.splat` | `recipe` (core.recipe) | The 3-step conversion record, plus the original 9,007,936-byte source |
| `provenance/provenance.json` | `provenance` | Where the source came from |
| `splats/plush.wkgs` | `gsplat` (core.geom.gsplat, the `primary.geometry` node) | The 3D Gaussian splat |
| `points/plush-dc.wkpc` | `points-dc` (core.geom.points) | The splat's exact point-cloud degradation |

## 2. Points

**Count: 281,498.** Five sources agree on this number:
- the WKGS header `count`
- the WKPC header `count`
- manifest `gaussian_count`
- manifest `point_count`
- the `.splat` file size divided by its 32-byte record size

**How the points were extracted**
- The WKGS has six sections (`means`, `scales`, `rotations`, `opacities`, `sh-dc`, `sh-rest`). `sh_degree` is 0, so `sh-rest` has size 0.
- Positions come from `means`: f32 ×3, in metres, werk model space (+Y up).
- Colours follow gsplat.layout §5/§7: `rgb_linear = clamp(0.5 + 0.28209479177387814·sh_dc, 0, 1)`.

**Agreement checks**
- WKPC `position` bytes equal WKGS `means` bytes: **identical**.
- WKPC `color` (u8 ×3, declared `linear-srgb`) equals `round_half_even(255·rgb_linear)` computed from the WKGS: **identical**, all 844,494 bytes.
- An independent check against the raw `recipe/inputs/plush.splat` (`mytools/crosscheck.py`):
  - its position bytes equal WKGS `means`
  - its r,g,b bytes equal the WKPC colour bytes
  - its alpha endpoints (5 values of 0, 33,396 of 255; 33,401 in total) equal the recipe's `alpha_clamped_count`
- My envelope decoder reproduces every decoded value printed in `spec/examples/gsplat.example.hex.txt`.

**Bounds** (in metres): x from −1.09269 to 1.23398, y from 1.16256 to 2.26130, z from 0.37418 to 1.72467.

**Sample**

| i | position (m) | linear RGB | WKPC u8 |
|---|---|---|---|
| 0 | (−0.060075, 1.625257, 0.935071) | (0.152941, 0.074510, 0.023529) | (39, 19, 6) |
| 1 | (−0.035026, 1.578063, 1.032170) | (0.235294, 0.117647, 0.113725) | (60, 30, 29) |
| 2 | (−0.109434, 1.615720, 1.005387) | (0.427451, 0.278431, 0.101961) | (109, 71, 26) |
| 3 | (−0.025732, 1.576227, 1.033759) | (0.254902, 0.168627, 0.180392) | (65, 43, 46) |
| 4 | (−0.011812, 1.612853, 0.940788) | (0.200000, 0.070588, 0.035294) | (51, 18, 9) |
| 140749 | (−0.370874, 1.366686, 0.415687) | (0.760784, 0.717647, 0.596078) | (194, 183, 152) |
| 281497 | (0.461299, 1.664856, 1.180542) | (0.643137, 0.552941, 0.470588) | (164, 141, 120) |

The mean linear RGB is (0.630, 0.496, 0.391), a warm tan.

**Output files**
- `output/points.csv`: all 281,498 rows, giving index, xyz, linear rgb floats and the WKPC u8 values.
- `output/points_srgb.ply`: a binary PLY for viewing. Its colours have the sRGB transfer function applied, because the file declares the colours to be linear. See stumble 6: that declaration may be wrong.

## 3. The tools

All three are Python sources. Their declared licence is PolyForm-Noncommercial-1.0.0. Each `tool.json` declares numpy as its only dependency. The offsets in the table are each file's ZIP local-header offset inside `gsplat-v1.werk`.

| Node | Role / recipe step | Files (local-header offset, size) | What it does |
|---|---|---|---|
| `tool-splat-to-ply`, reported as `pipeline/splat_to_ply.py` 1.0 | converter, step 1 `splat-to-inria-ply` | `tools/splat-to-ply/tool.json` @1,111,970 (1,818 B)<br>**`tools/splat-to-ply/splat_to_ply.py`** @1,103,553 (8,353 B, entrypoint)<br>`tools/splat-to-ply/ply.py` @1,081,651 (21,847 B)<br>config: `tools/splat-to-ply-run.config.json` @1,079,580 | Reads the 32-byte-record antimatter15 `.splat` and writes an INRIA-convention PLY with the pre-activation values: log scales, logit opacity (alpha clamped to [0.5/255, 254.5/255] on 33,401 records), `f_dc` obtained by inverting `0.5 + C0·dc`, and byte quaternions turned into normalised f32 wxyz with w ≥ 0. |
| `tool-werk-gsplat`, reported as `pipeline/p_gsplat.py` 1.0 | converter, step 2 `ply-to-wkgs` | `tools/werk-gsplat/tool.json` @1,167,541 (1,936 B)<br>**`tools/werk-gsplat/p_gsplat.py`** @1,132,639 (12,942 B, entrypoint)<br>`tools/werk-gsplat/ply.py` @1,145,640 (21,847 B)<br>`tools/werk-gsplat/common.py` @1,115,733 (16,849 B)<br>config: `tools/werk-gsplat-run.config.json` @1,113,846 | Ingests the PLY into the six WKGS streams. It applies exp to the scales and sigmoid to the opacity. It takes the quaternion order as declared (`--quat-order wxyz`), but still records the inference statistic it would have used. It transposes channel-major SH to coefficient-major and writes the envelope through `common.write_envelope`. |
| `tool-werk-pointcloud`, reported as `pipeline/p_pointcloud.py` 1.0 | processor, step 3 `wkgs-to-wkpc` | `tools/werk-pointcloud/tool.json` @1,223,821 (1,692 B)<br>**`tools/werk-pointcloud/p_pointcloud.py`** @1,188,058 (13,791 B, entrypoint)<br>`tools/werk-pointcloud/ply.py` @1,201,916<br>`tools/werk-pointcloud/common.py` @1,171,148<br>config: `tools/werk-pointcloud-run.config.json` @1,169,534 | `from_gsplat` derives the WKPC from WKGS `means` and `sh-dc`. Positions are copied exactly; colours are `clip(rint(255·clamp(0.5+C0·dc,0,1)))`. |

The three `ply.py` copies are byte-identical (sha256 `7e25f50d…b576`), and so are the two `common.py` copies (`3204636d…b8f3`). The SPEC permits this because each path belongs to exactly one node.

**Source quoted verbatim**

From `tools/splat-to-ply/splat_to_ply.py`, inside `convert()`:
```python
    # colour -> the degree-0 SH coefficient. The forward transform the viewer
    # applied was  byte = round(255 * clip(0.5 + C0*f_dc, 0, 1)).
    f_dc = ((col[:, :3] / 255.0) - 0.5) / SH_C0

    # alpha -> logit opacity, with the clamp this file's docstring argues for.
    alpha = col[:, 3] / 255.0
    clamped = int(np.count_nonzero((alpha < ALPHA_LO) | (alpha > ALPHA_HI)))
    alpha = np.clip(alpha, ALPHA_LO, ALPHA_HI)
    opacity = np.log(alpha / (1.0 - alpha))

    # linear scale -> log scale.
    log_scale = np.log(scl.astype(np.float64))

    # byte quaternion -> f32, WXYZ, renormalised, canonical w >= 0 sign
    # (ENVELOPE.layout.txt section 6).
    q = (rot - 128.0) / 128.0
    nrm = np.linalg.norm(q, axis=1)
    degenerate = int(np.count_nonzero(nrm == 0))
    nrm[nrm == 0] = 1.0
    q = q / nrm[:, None]
    q = np.where(q[:, :1] < 0, -q, q)
```

From `tools/werk-gsplat/ply.py`, `gsplat_arrays()`, which `p_gsplat.ingest()` calls:
```python
    means = np.stack([f("x"), f("y"), f("z")], 1)
    scales = np.exp(np.stack([f(n) for n in plan.scale_names], 1))
    op = f(plan.opacity_name)
    opac = 1.0 / (1.0 + np.exp(-op))

    q = np.stack([f(n) for n in plan.rot_names], 1)
    if plan.quat_order == "xyzw":
        q = q[:, [3, 0, 1, 2]]
    nrm = np.linalg.norm(q, axis=1)
    nrm[nrm == 0] = 1.0
    q = q / nrm[:, None]
    ...
    q = np.where(q[:, :1] < 0, -q, q)

    k = plan.sh_coeff_count
    sh = np.empty((len(means), k, 3), dtype=np.float64)
    sh[:, 0, 0] = f("f_dc_0")
    sh[:, 0, 1] = f("f_dc_1")
    sh[:, 0, 2] = f("f_dc_2")
    if k > 1:
        ...
        km1 = k - 1
        rest = np.stack([f(n) for n in plan.rest_names], 1)      # [N, 3*(K-1)]
        rest = rest.reshape(len(means), 3, km1)                   # [N,3,K-1]
        sh[:, 1:, :] = np.transpose(rest, (0, 2, 1))              # [N,K-1,3]
```

From `tools/werk-gsplat/p_gsplat.py`, `build_wkgs()`, the six sections it writes:
```python
    return write_envelope(MAGIC, KIND, header, [
        ("means", "f32", [n, 3], 12, means.tobytes()),
        ("scales", "f32", [n, 3], 12, scales.tobytes()),
        ("rotations", "f32", [n, 4], 16, rot.tobytes()),
        ("opacities", "f32", [n], 4, opac.tobytes()),
        ("sh-dc", "f32", [n, 3], 12, dc.tobytes()),
        ("sh-rest", "f32", [n, k - 1, 3], 12, rest.tobytes()),
    ])
```

From `tools/werk-pointcloud/p_pointcloud.py`, `from_gsplat()`, together with `ply.py`'s `dc_to_linear_rgb`:
```python
def from_gsplat(means, sh_dc, extra_header=None):
    rgb = dc_to_linear_rgb(sh_dc)
    u8 = np.clip(np.rint(rgb * 255.0), 0, 255).astype("u1")
    fields = [
        Field("position", "position", "f32", 3,
              np.ascontiguousarray(means, dtype="<f4"), unit="metre"),
        Field("color", "color", "u8", 3, u8, color_space="linear-srgb", note=...),
    ]
...
def dc_to_linear_rgb(sh_dc):
    return np.clip(0.5 + SH_C0 * np.asarray(sh_dc, dtype=np.float64), 0.0, 1.0)
```

`common.py`'s `write_envelope` (lines 153–213) computes the section offsets, iterates `payload_origin` to a fixed point, and asserts the consistency rule on the way out. Its `mp_encode` (lines 85–146) is the canonical MessagePack writer.

---

## Files read, in order

1. Raw hex of the first 512 bytes of the `.werk` (my hexdump), which showed `PK` and an uncompressed MANIFEST.
2. The ZIP central directory (my `ls.py`).
3. `README.txt`, then `SIGNATURE.json`.
4. `MANIFEST.json`.
5. `spec/README.md`.
6. `spec/SPEC.md`: §0–2, §3.11, §3.15–3.17, §4–7, §10.
7. `spec/MINI-SPECS.md`: §5 (zip), §6, §11 (SHA, input_hash), §12 (Ed25519), §1–4 (JSON/canonical).
8. `spec/layouts/ENVELOPE.layout.txt`.
9. `spec/layouts/gsplat.layout.txt`.
10. `spec/layouts/points.layout.txt`.
11. `spec/examples/gsplat.example.hex.txt`.
12. `recipe/recipe.json`.
13. The three `tools/*/tool.json` files.
14. `tools/werk-pointcloud/p_pointcloud.py`.
15. `tools/werk-gsplat/p_gsplat.py`.
16. `tools/splat-to-ply/splat_to_ply.py`.
17. `tools/werk-gsplat/ply.py`: a grep, then lines 265–436.
18. Read by my programs as data only: `spec/examples/gsplat.example.wkgs`, `SIGNATURE.example.json`, `MANIFEST.example.json`, `recipe/inputs/plush.splat`, and both payloads.
19. The three `tools/*-run.config.json` files, `LICENSE` and `provenance/provenance.json`.
20. `tools/werk-gsplat/common.py`: lines 1–220, plus a grep.

**Not read:** `loaders/*`, `spec/schemas/*`, the other layouts, `make-examples.py`, `PROFILE-IMAGE.md`, the C2PA/cub docs, `semantics.json` (hashed only) and `facets.json`.

**Which file unblocked me.** I was never fully stuck. The decode was made possible by `ENVELOPE.layout.txt` together with `gsplat.layout.txt`, checked against `gsplat.example.hex.txt`. `MINI-SPECS.md` §12/§12.1 made the signature check possible without a library. The one fact the spec does **not** give is the u8 colour rounding rule. I got it from `tools/werk-pointcloud/p_pointcloud.py` (`np.rint`, round half to even), and `tools/werk-pointcloud-run.config.json` confirms it (`"rounded half to even"`). Without that, I could only have shown that WKPC agrees with the splat to within ±1.

## Anything wanted from outside the file

Nothing was fetched, and I never needed to. Two things I would have liked:
- a JSON Schema validator, which the format permits a reader not to have;
- permission to execute `splat_to_ply.py`, so the uncarried intermediate PLY's hash could be checked.

## Stumbles, honestly

1. **Harness friction, about 1 minute lost.**
   - Several shell commands were refused by permission rules: compound `&&` commands, `Format-Table`, shell redirection, and `$( )` subexpressions.
   - The large MANIFEST output spilled to a tool-results file outside the allowed directory, and I could not read it.
   - Workaround: I copied every package entry under 2 MB into `extracted/` under flattened names (`spec__SPEC.md.txt`, with a `.txt` suffix so nothing is executable by association). That way no on-disk directory named `spec/` or `loaders/` was created. **This means byte copies of the loaders do exist on disk** as `extracted/loaders__werk_read.*.txt`. I never opened them.
2. **Reading the constraints.** Hard constraint 2 bans directories named `spec/` and `loaders/` "anywhere on this machine", while the task allows "anything inside the file". I read the in-package `spec/` as allowed, read it from the ZIP, and avoided recreating it as a directory. I chose not to open the in-package loaders at all, so the reader is clearly independent.
3. **The README's instruction to run `loaders/werk_read.py --verify`.** I ignored it, as required.
4. **A spec gap: colour quantisation rounding.** `points.layout.txt` says only "u8 is 0..255 mapping to 0..1". To match byte-exactly I took the rounding rule from tool source. I knew to look there because I anticipated the gap; it did not fail first.
5. **A spec inconsistency: the LICENSE text.** Each `tool.json` says the PolyForm Noncommercial 1.0.0 full text is "carried … as part of the LICENSE file". `LICENSE` only names that licence and does not contain its text, which conflicts with the stated "full text, never a link" doctrine.
6. **A possible semantic issue, based on my prior knowledge rather than the file.**
   - The WKPC colour bytes are exactly the source `.splat`'s r,g,b bytes, which the tool docstring calls viewer bytes.
   - Splats are generally trained against sRGB-encoded photos, so these values are probably display-referred. The package labels them `linear-srgb`.
   - I followed the file's declaration when writing `points_srgb.ply` (I applied linear→sRGB). If the label is wrong, that preview will look washed out; the raw bytes are in the CSV.
   - I cannot settle this from inside the file.
7. **Minor manifest notes, not errors.**
   - Multi-file nodes (the tools, `recipe`) carry no `payload_file`, which SPEC §2.1 says a writer SHOULD emit. The recipe's files carry no `role: record` either. My reader only needed the single-file nodes, which resolve by rule 2.
   - The tool nodes' notes say "2 file(s)" or "3 file(s)" while `files[]` lists 3 or 4. The count apparently excludes `tool.json`.
   - `common.py` lazily imports `PIL`, which `tool.json` does not declare. The splat path does not use it.
8. **Not done:**
   - JSON Schema validation of the manifest, tool, config and recipe JSON;
   - regenerating and hash-checking the intermediate `plush.ply`, which would require executing an embedded tool;
   - any semantic check of `semantics.json`'s palette.
9. **Bugs in my own code:** none surfaced. Every check passed on the first full run, and the example-file self-test confirmed the decoder. My Ed25519 implementation passed its self-tests, but it has not been audited. It is acceptable only as a verifier, as the spec says.

## Wall-clock (my own sense; session ran 01:04 → about 01:14)

| Phase | Time |
|---|---|
| Orientation: hex, listing, README, MANIFEST, including the permission stumbles | about 2 min |
| Reading the spec: SPEC, MINI-SPECS, three layouts, example hex | about 2 min |
| Reading the recipe, tool descriptors and three tool sources (needed for the rounding rule) | about 1 min |
| Writing `werk_inspect.py` | about 2 min |
| Running it and the cross-check, both passing first time | about 1 min |
| Remaining tool, config and LICENSE reading, then this report | about 2–3 min |

## Artifacts in the working directory

- `mytools/werk_inspect.py` — the reader and verifier (task 1 and task 2).
- `mytools/crosscheck.py` — decoder self-test against the spec example, and the check against the `.splat`.
- `mytools/hexdump.py`, `mytools/ls.py`, `mytools/cat.py`, `mytools/extract_flat.py` — inspection helpers.
- `extracted/` — flat `.txt` copies of the entries under 2 MB, hash-identical to the package.
- `output/points.csv`, `output/points_srgb.ply` — the extracted points.
