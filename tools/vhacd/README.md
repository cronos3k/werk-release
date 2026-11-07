# V-HACD, vendored

`VHACD.h` is the **unmodified** upstream single-header release of V-HACD v4.1.

| | |
|---|---|
| upstream | https://github.com/kmammou/v-hacd — `include/VHACD.h`, branch `master` |
| retrieved | 2026-08-08 |
| version | `VHACD_VERSION_MAJOR 4`, `VHACD_VERSION_MINOR 1` |
| lines | 8 364 |
| sha256 | `c2b750a41bc6044457c79dc51d196b7bbe5e24bfaec72d409a065434d9651ff2` |
| licence | BSD-3-Clause, © 2011 Khaled Mamou — full text in `LICENSE.txt`, and also at the top of the header itself |
| modifications | **none.** The file is byte-for-byte upstream; verify with the sha256 above |

`werk_vhacd_cli.cpp` is werk's own code (same licence as the rest of this
repository). It is the only translation unit that defines
`ENABLE_VHACD_IMPLEMENTATION`, so the algorithm is compiled exactly once, and
it exposes V-HACD as a binary-in / binary-out CLI. The wire format is
documented in the comment at the top of that file.

## Building

    python tools/build_native.py vhacd

Produces `tools/_build/werk_vhacd.exe` (`werk_vhacd` on POSIX). The build
directory is git-ignored: the binary is *output*, the header is the dependency.
`tools/_build/build.json` records which compiler produced it.

Measured on this box, 2026-08-08: MSVC 19.43.34808 x64, `/O2 /EHsc /std:c++17
/MT`, **2.4 s**, 570 296 bytes. mingw-w64 g++ 15.2.0 also builds it clean
(6.3 s) and the script falls back to it when no Visual Studio is installed.

## Why a separate process rather than a DLL

V-HACD allocates through the C++ runtime and (upstream default) runs a thread
pool. A process boundary means a decomposition that asserts, hangs or blows the
stack on a hostile mesh takes the child down and the pipeline sees an exit
code, rather than taking the pipeline down with it. `m_asyncACD` is forced
**off** in the CLI so a run is single-threaded and deterministic.

## What the pipeline does with it

`pipeline/vhacd.py` finds the binary, feeds it the welded mesh and parses the
hulls back. If the binary is absent or the run fails, `pipeline/p_collider.py`
falls back to `voxel-hacd-lite/0.1` and the `core.phys.colliders` node's
`fit.engine` records **which one actually ran**. Neither engine is ever
assumed; the node states it.
