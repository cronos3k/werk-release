# MikkTSpace, vendored

`mikktspace.c` and `mikktspace.h` are the **unmodified** reference
implementation by Morten S. Mikkelsen — the same two files glTF, Blender,
Unity and Unreal all carry.

| | |
|---|---|
| upstream | https://github.com/mmikk/MikkTSpace — `mikktspace.c`, `mikktspace.h`, branch `master` |
| retrieved | 2026-08-08 |
| version | 1.0 (stated in the header comment) |
| lines | 1 899 + 145 |
| sha256 | `de87e74107df766ce68108801262bd8d53899414236b59810509a8fc2a51e288` (`mikktspace.c`) |
| | `17fc433894f24c73753d548086cc4d8c5c0379f4a6edfb98b5da243e4f0bc3d0` (`mikktspace.h`) |
| licence | zlib-style permissive, © 2011 Morten S. Mikkelsen — full text in `LICENSE.txt`. Use for any purpose including commercial; do not misrepresent the origin; mark altered versions; keep the notice |
| modifications | **none.** Both files are byte-for-byte upstream — which is also what the licence's clause 2 asks for, and what the header's own "designed to be stand-alone files" paragraph asks for |

`werk_mikktspace.c` is werk's own code (same licence as the rest of this
repository). The reference implementation is callback-driven; that file holds
the callbacks and exposes one flat-array entry point so ctypes can call it:

    int werk_mikktspace(const float *pos, const float *nrm, const float *uv,
                        const unsigned int *idx, int ntri, float *out_tan);

`out_tan` receives four floats per **face corner** (12 per triangle): tangent
xyz plus the sign w. MikkTSpace's `fSign` is passed through unchanged, because
MikkTSpace and glTF define the same thing — `bitangent = w * cross(N, T)`.

Per corner and not per vertex on purpose: the entire reason MikkTSpace exists
is that the basis is *discontinuous* across a UV chart seam. Averaging the
corners back down inside this file would throw away the one thing it is here
for, so the caller gets the per-corner answer and decides where to split.

## Building

    python tools/build_native.py mikktspace

Produces `tools/_build/werk_mikktspace.dll` (`.so` / `.dylib` on POSIX);
git-ignored, `tools/_build/build.json` records the compiler.

Measured on this box, 2026-08-08: MSVC 19.43.34808 x64, `/O2 /MT /LD`,
**0.4 s**, 124 467 bytes.

## What the pipeline does with it

`pipeline/mikktspace.py` loads the DLL through ctypes and returns per-corner
tangents; `pipeline/p_geom.py` splits vertices where the corners disagree and
writes `meta.tangent_method: "mikktspace/1.0"`. If the DLL is missing the
producer falls back to the accumulate-then-Gram-Schmidt basis and writes
`"gram-schmidt-accumulated/0.1"` instead. The node always says which ran.
