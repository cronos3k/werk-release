# Report — `gsplat-v1.werk` inspection

## What I was asked to do

1. Write a program that opens `gsplat-v1.werk`, lists its contents with their meanings, and verifies integrity.
2. Extract the point positions and colours it contains, and say how many points there are.
3. Identify the tools that made the file, say what each one does, and show their source.

I worked **only** from `gsplat-v1.werk` and the files it contains. I did not search the web, read any directory outside the working directory, or run any code that came out of the package.

---

## Summary of success

| Task | Result |
|---|---|
| 1. Open, list with meanings, verify integrity | **Succeeded.** `inspect_werk.py` opens the zip, prints every entry with its node/type meaning from `MANIFEST.json`, checks all zip CRCs, checks every declared file hash, checks `spec_sha256`, and checks that `MANIFEST.json` matches the signature record. |
| 2. Extract positions and colours | **Succeeded.** 281,498 points. Positions and colours extracted from `points/plush-dc.wkpc`; the same 281,498 means and DC colours were also read from `splats/plush.wkgs` as a cross-check. |
| 3. Identify tools and show source | **Succeeded.** Three embedded tools: `splat-to-ply`, `werk-gsplat`, and `werk-pointcloud`. Their source is quoted below. |

---

## The program I wrote

`inspect_werk.py` (in the working directory) is a pure-Python 3 standard-library script that:

* opens the `.werk` as a zip file,
* reads `MANIFEST.json` and `SIGNATURE.json`,
* prints every zip entry together with the meaning derived from the manifest's `nodes[].versions[].files[]`,
* recomputes and compares SHA-256 for every declared file,
* recomputes the `spec_sha256` over the `spec/` tree exactly as `SPEC.md` §2 defines,
* compares the manifest hash with the value recorded in `SIGNATURE.json`,
* parses the binary envelopes of `points/plush-dc.wkpc` and `splats/plush.wkgs` using a small MessagePack decoder I wrote from the table in `spec/layouts/ENVELOPE.layout.txt` §4, and
* extracts positions and colours.

No code from inside the package is imported or executed.

---

## Integrity verification results

```
ZIP integrity: OK (all CRCs match)
Declared files: 75 OK, 0 bad
No floating entries besides MANIFEST.json and SIGNATURE.json
spec_sha256 declared: 331519c8d96aca0f8ea31200c68a6b28d62205f8458038a06cf2057fa5734575
spec_sha256 computed:  331519c8d96aca0f8ea31200c68a6b28d62205f8458038a06cf2057fa5734575
spec_sha256: OK
MANIFEST.json sha256:  e197af7f85988819e46bb5cee6849e7cc914f98d5dab7ac744922516d7785c7e
SIGNATURE.json manifest_sha256: e197af7f85988819e46bb5cee6849e7cc914f98d5dab7ac744922516d7785c7e
Manifest hash matches signature record: OK
```

I did **not** verify the Ed25519 cryptographic signature itself: the Python standard library does not include an Ed25519 verifier, and the package's own note says the dev key is "not a trust anchor" and "proves only that the chain verifies". The manifest hash, which the signature is over, does match.

---

## Point count and sample

**Number of points: 281,498**

The point cloud node (`points-dc`, `points/plush-dc.wkpc`) contains two fields:

* `position` — `f32`, 3 components, in metres
* `color` — `u8`, 3 components, `linear-srgb`

The first five positions (metres):

```
[0]  -0.060075  +1.625257  +0.935071
[1]  -0.035026  +1.578063  +1.032170
[2]  -0.109434  +1.615720  +1.005387
[3]  -0.025732  +1.576227  +1.033759
[4]  -0.011812  +1.612853  +0.940788
```

The first five colours (u8, linear-srgb):

```
[0]   39   19    6
[1]   60   30   29
[2]  109   71   26
[3]   65   43   46
[4]   51   18    9
```

A spot-check confirmed that all 281,498 positions in the WKPC match the `means` section of the WKGS, and the WKPC colours are the WKGS `sh-dc` band through `clamp(0.5 + C0 * sh_dc, 0, 1)` quantised to 8 bits, exactly as `spec/layouts/gsplat.layout.txt` §7 defines.

---

## Tools that made this file

The conversion chain is recorded in `recipe/recipe.json`. Three embedded `core.tool` nodes performed it:

| # | Tool node | Source inside package | Role in the chain |
|---|---|---|---|
| 1 | `tool-splat-to-ply` | `tools/splat-to-ply/splat_to_ply.py` (+ `ply.py`) | Step 1: convert the 32-byte `.splat` to an INRIA-convention PLY. |
| 2 | `tool-werk-gsplat` | `tools/werk-gsplat/p_gsplat.py` (+ `common.py`, `ply.py`) | Step 2: ingest the PLY into the WKGS Gaussian splat binary. |
| 3 | `tool-werk-pointcloud` | `tools/werk-pointcloud/p_pointcloud.py` (+ `common.py`, `ply.py`) | Step 3: degrade the WKGS to the WKPC point cloud. |

The recipe explicitly says:

```json
"steps": [
  { "step_id": "splat-to-inria-ply", "tool": { "tool_node": "tool-splat-to-ply" }, ... },
  { "step_id": "ply-to-wkgs",        "tool": { "tool_node": "tool-werk-gsplat" }, ... },
  { "step_id": "wkgs-to-wkpc",       "tool": { "tool_node": "tool-werk-pointcloud" }, ... }
]
```

I did not run any of these tools; I only read them.

### Tool 1 — `splat-to-ply`

**Location:** `tools/splat-to-ply/splat_to_ply.py`  
**What it does:** Reads the web-viewer `.splat` format (32-byte records with already-activated position, linear scale, rgba u8, and u8 WXYZ quaternion) and writes the INRIA Gaussian-splatting PLY with pre-activation values: log scales, logit opacity, raw degree-0 SH coefficients, and f32 quaternions.

Key source (the docstring and the inverse transforms):

```python
"""splat_to_ply.py — turn an antimatter15 `.splat` file into an INRIA-convention
Gaussian-splatting PLY.

    offset  bytes  field                          state in the .splat
    ------  -----  -----------------------------  --------------------------
    0       12     position x,y,z   f32 LE         as-is
    12      12     scale    sx,sy,sz f32 LE        LINEAR (already exp'd)
    24      4      colour   r,g,b,a  u8            r,g,b are 0.5 + C0*f_dc,
                                                   scaled to 0..255 and
                                                   clipped; a is sigmoid
                                                   (opacity) scaled to 0..255
    28      4      rotation q        u8            (128 + 128*q), WXYZ order
"""

# colour -> the degree-0 SH coefficient.
f_dc = ((col[:, :3] / 255.0) - 0.5) / SH_C0

# alpha -> logit opacity, with the clamp this file's docstring argues for.
alpha = col[:, 3] / 255.0
clamped = int(np.count_nonzero((alpha < ALPHA_LO) | (alpha > ALPHA_HI)))
alpha = np.clip(alpha, ALPHA_LO, ALPHA_HI)
opacity = np.log(alpha / (1.0 - alpha))

# linear scale -> log scale.
log_scale = np.log(scl.astype(np.float64))

# byte quaternion -> f32, WXYZ, renormalised, canonical w >= 0 sign
q = (rot - 128.0) / 128.0
nrm = np.linalg.norm(q, axis=1)
nrm[nrm == 0] = 1.0
q = q / nrm[:, None]
q = np.where(q[:, :1] < 0, -q, q)
```

### Tool 2 — `werk-gsplat`

**Location:** `tools/werk-gsplat/p_gsplat.py`  
**What it does:** Ingests an INRIA Gaussian-splatting PLY into the six declared streams of `spec/layouts/gsplat.layout.txt`: applies `exp` to log scales, applies the logistic function to logit opacity, reorders/sign-canonicalises quaternions, transposes SH coefficients from channel-major to coefficient-major, and writes the WKGS envelope.

Key source (from the module docstring and `ingest`):

```python
"""p_gsplat.py — core.geom.gsplat, the WKGS binary: ingest a 3D-Gaussian-
Splatting PLY into werk's six declared streams.

WHAT IT DOES, IN ONE PARAGRAPH. It reads the INRIA field convention
(`x y z`, the always-zero `nx ny nz`, `f_dc_*`, `f_rest_*`, `opacity`,
`scale_*`, `rot_*`), applies `exp` to the log scales, `sigmoid` to the logit
opacity, reorders and sign-canonicalises the quaternions, TRANSPOSES the
spherical-harmonic coefficients from the source's channel-major layout to
werk's coefficient-major one, and writes six sections whose offsets and sizes
are declared in the header. It does not resample, decimate, sort, recentre or
rescale.
"""

blob = build_wkgs(means, scales, rot, opac, sh, extra)
```

`build_wkgs` builds the six sections (`means`, `scales`, `rotations`, `opacities`, `sh-dc`, `sh-rest`) and passes them to `write_envelope` from `common.py`.

### Tool 3 — `werk-pointcloud`

**Location:** `tools/werk-pointcloud/p_pointcloud.py`  
**What it does:** Produces the WKPC point cloud from the WKGS splat using the normative degradation path: positions are the splat means exactly; colours are the DC band through `clamp(0.5 + C0 * sh_dc, 0, 1)` quantised to 8 bits.

Key source (`from_gsplat`):

```python
"""p_pointcloud.py — core.geom.points, the WKPC binary: a point cloud with
DECLARED fields.

  * `from_gsplat` — the normative degradation of a Gaussian splat into its
    point cloud (gsplat.layout.txt section 7, SPEC.md section 3.16, law 9):
    positions are the means EXACTLY, colours are the DC band through
    `clamp(0.5 + C0*sh_dc, 0, 1)`. No resampling, no decimation, no
    approximation — which is what makes the resulting node `epistemic:
    "measured"` over a derivation a consumer can recompute and check.
"""

def from_gsplat(means, sh_dc, extra_header=None):
    rgb = dc_to_linear_rgb(sh_dc)
    u8 = np.clip(np.rint(rgb * 255.0), 0, 255).astype("u1")
    fields = [
        Field("position", "position", "f32", 3,
              np.ascontiguousarray(means, dtype="<f4"), unit="metre"),
        Field("color", "color", "u8", 3, u8, color_space="linear-srgb",
              note="the Gaussian splat's degree-0 SH band through "
                   "clamp(0.5 + 0.28209479177387814*dc, 0, 1), quantised to 8 "
                   "bits per channel. LINEAR, not sRGB-encoded: apply the "
                   "transfer function before display."),
    ]
```

---

## Bundled readers

`loaders/werk_read.py`, `loaders/werk_read.rs`, and `loaders/werk_read.c` are present as `core.loader` nodes. I **did not open, run, or port any of them**. I wrote my own reader from the spec files in order to satisfy the constraint that nothing from inside the package is executed. (I did extract the zip contents into `extracted/` for reading, but I did not execute any extracted file.)

---

## Files inside the package I read, in order

1. `gsplat-v1.werk` itself — opened as a zip to list entries.
2. `spec/README.md` — gave the reading order and the map of node types to schema/layout files. **This unblocked the whole investigation.**
3. `spec/SPEC.md` — container rules, manifest semantics, node families, `spec_sha256` construction.
4. `spec/layouts/gsplat.layout.txt` — WKGS payload structure and the splat→point-cloud degradation formula.
5. `spec/layouts/points.layout.txt` — WKPC field-declaration layout.
6. `spec/layouts/ENVELOPE.layout.txt` — binary envelope framing and the complete MessagePack subset. **This unblocked parsing the binary payloads.**
7. `MANIFEST.json` — node graph, file hashes, conventions, and tool nodes.
8. `README.txt` — confirmed the two ways to get positions and colours (WKPC or WKGS means+DC).
9. `recipe/recipe.json` — the exact conversion chain and tool node references.
10. `provenance/provenance.json` — source of the input `.splat`.
11. `tools/splat-to-ply/tool.json`, `tools/werk-gsplat/tool.json`, `tools/werk-pointcloud/tool.json` — tool metadata and entrypoints.
12. `tools/splat-to-ply/splat_to_ply.py`, `tools/werk-gsplat/p_gsplat.py`, `tools/werk-pointcloud/p_pointcloud.py` — the tool source quoted above.
13. `tools/werk-gsplat/common.py` — only to confirm the envelope writer used by the other tools.
14. `SIGNATURE.json` — to read the manifest hash and signature record.

---

## What I wanted from outside the file

Nothing. Every rule needed to parse, verify, and understand the package is inside it. I used only the Python 3 standard library (zipfile, hashlib, struct, json, math) and the MessagePack grammar given in `spec/layouts/ENVELOPE.layout.txt` §4.

---

## Stumbles (honest)

1. **MessagePack decoder bug.** My first implementation of the header decoder did not advance past the type byte before reading the payload for integers, floats, strings, binaries, arrays and maps. That made every multi-byte value overlap with the next byte, which the decoder eventually interpreted as a map, producing a `RecursionError`. I fixed it by consuming the type byte first in every non-literal branch.

2. **Variable-name collision.** In the extraction loop I unpacked the z-coordinate into a variable named `z`, which shadowed the `zipfile.ZipFile` object also named `z`. The next attempt to read the WKGS blob failed with `AttributeError: 'float' object has no attribute 'read'`. I renamed the coordinate to `pz`.

3. **Initial uncertainty about which payload to treat as "the points".** The file is a Gaussian-splat package; the positions and colours live both in `splats/plush.wkgs` (as means and DC SH coefficients) and, pre-computed, in `points/plush-dc.wkpc`. `README.txt` and `spec/layouts/gsplat.layout.txt` §7 make clear that the WKPC is the normative point-cloud view, so I extracted from there and cross-checked against the WKGS.

---

## Wall-clock sense of time spent

* Initial zip inspection and listing: ~2 min
* Reading specs (`README.md`, `SPEC.md`, layouts, `ENVELOPE.layout.txt`): ~10 min
* Writing the integrity/extraction program: ~15 min
* Debugging the MessagePack decoder and variable-name collision: ~10 min
* Running verification and extracting samples: ~5 min
* Reading tool source and writing this report: ~10 min

**Total: roughly 50–55 minutes.**
