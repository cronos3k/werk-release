# Reproducibility environments

An exact-byte claim applies only to its recorded input and environment.
Current package snapshots do not establish an unknown historical package version.
The files under `locks/` record this host without installing or updating anything.

| Component | Recorded value | Basis |
|---|---|---|
| OS | Windows 11 Home, 10.0.26200.0, x86_64 | Current host query |
| Shell | PowerShell 7.6.5 | Current shell query |
| Git | 2.51.0.windows.1 | Current tool query |
| Rust | 1.98.0, commit 88d9e12ae178fab0fb5cc050a94da85685d449ea | Current tool query |
| Cargo | 1.98.0, commit 797e8a9bc | Current tool query |
| Rust target | x86_64-pc-windows-msvc, LLVM 22.1.8 | Current tool query |
| MSVC | 19.44.35215 for x64 | Current retained compilation output and direct rebuild. |
| MinGW | Absent | Task file and retained audit |
| Blender | 4.2.1 LTS | Retained audit |
| Blender exporter | 1.0.0 | `bl_info.version` at 6d547d0 |
| Python | 3.10.11, 3.13.7, 3.14.0; Blender 3.11.7; sharp 3.13.11 | Current interpreter probes |
| PYTHONUTF8 | Recorded in each Python snapshot | Current environment probe |

MSVC is Microsoft's C and C++ compiler. MinGW supplies GCC for Windows.
The Rust target identifies the compiler's operating system and native interface.
`PYTHONUTF8=1` makes Python use UTF-8 as its default text encoding.
The corrected graders also invoke Python with `-X utf8`.

| Builder or claim | Environment and dependencies | Exact-byte limit |
|---|---|---|
| Golden crate manual rebuild | Audit checkout 6d547d0, package CRLF spec files, script `<second-lab>/audit-scratch/scripts/item5_src.py` | Both original archives matched. Reassembly uses embedded payloads. It does not repeat asset creation. |
| Ista-varun manual rebuild | Python 3.10.11, NumPy 1.26.4, Pillow 12.3.0, stock zlib 1.2.13 | Reconstructed database row and copied evidence. Preview compression uses the explicit parameters below. |
| Crate-tex rebuild | Blender 4.2.1 LTS, exporter 1.0.0, package input asset | Payload comparisons apply. The whole archive does not match the LF checkout rebuild. |
| Splat rebuild | Package source splat, package spec, recorded CPython patch in each run configuration | Computed payloads match. Host metadata can prevent whole-archive identity. |
| Public image builder | Python 3.10.11, NumPy 1.26.4, Pillow 12.3.0 | Compression and embedded spec bytes affect the archive. |
| Enrichment pipeline | Native V-HACD 4.1 and MikkTSpace 1.0 in the retained audit | Example original. Crate textures and lantern inputs are substitutes. |
| Self-run Kimi rebuild | MSVC 19.44 substitute compiler | Vector output matches. This does not verify the requested MinGW build. |

Pillow is the Python imaging library. Its PNG compression library affects exact file bytes.
The installed Pillow wheels use zlib-ng. Python 3.10.11 also supplies stock zlib 1.2.13.
The matching Ista-varun recompression used level 6, memory level 9, and `Z_FILTERED`.
It split compressed data into 65,536-byte chunks.
These parameters were recovered by the prior audit. They are not independently documented historical builder settings.

V-HACD splits geometry into convex parts. MikkTSpace computes tangent vectors for surface shading.
The fallback tools use voxel-hacd-lite/0.1 and gram-schmidt-accumulated/0.1.
The retained native comparison reports different geometry and tangent results from these fallbacks.
Do not treat fallback output as a native reproduction.

The installed locks list every installed distribution, its exact version, dependency declarations and installation record hash.
The installation record lists each distribution's files and their recorded hashes.
The per-builder lock links each builder source and imports to these complete environment snapshots.
The Rust Cargo lock pins transitive dependencies. No package was installed to make these locks.
Blender's Python snapshot records its bundled environment. The sharp snapshot records OpenCV's existing environment.
These locks pin the current host. They do not recover missing historical dependency versions.

Every exact-byte claim in the second-lab report now names its environment or marks missing historical versions.
Claims with unknown historical versions are retained observations, rather than fully pinned repeatable builds.
Kimi's current native rerun was blocked by application control after one retry.
DeepSeek's MSVC rerun requires MSYS_NO_PATHCONV=1 to preserve compiler options in Git Bash.
