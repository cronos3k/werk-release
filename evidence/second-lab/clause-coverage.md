# Clause coverage

Each row identifies one observed gate clause. A PASS applies only to the named inputs.

The table reuses retained measurements. This audit did not rerun these gates.
The baseline gate records use review checkout `c5fe4f4`; the later audit uses `6d547d0`.
A substitute PASS does not establish the original-input claim.
The observed column preserves the original gate result, even when a separate audit adds coverage.

| Gate | Clause | Coverage class | Observed | Reason or input limit | Evidence |
|---|---|---|---|---|---|
| run_gate.py | fixture pinned: crate-synthetic | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/stage2.txt |
| run_gate.py | cargo test | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/stage2.txt |
| run_gate.py | round-trip byte identity | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/stage2.txt |
| run_gate.py | round-trip from directory form | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/stage2.txt |
| run_gate.py | damage gauntlet | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/stage2.txt |
| run_gate.py | face: Rust (werkc) | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/stage2.txt |
| run_gate.py | face: Python (ctypes) | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/stage2.txt |
| run_gate.py | face: C++ (MSVC) | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/stage2.txt |
| run_gate.py | bootstrap: werk_read.py | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/stage2.txt |
| run_gate.py | bootstrap: werk_read.rs | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/stage2.txt |
| run_gate.py | bootstrap: werk_read.c | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/stage2.txt |
| run_gate_a.py | fixture pinned: crate-v1 | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate-a.txt |
| run_gate_a.py | fixture pinned: crate-v1-damaged | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate-a.txt |
| run_gate_a.py | werk-core loads the clean fixture | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate-a.txt |
| run_gate_a.py | round-trip byte identity | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate-a.txt |
| run_gate_a.py | damaged: exact skip report | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate-a.txt |
| run_gate_a.py | bootstrap: werk_read.py | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate-a.txt |
| run_gate_a.py | bootstrap: werk_read.rs | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate-a.txt |
| run_gate_a.py | bootstrap: werk_read.c | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate-a.txt |
| run_gate_a.py | extract mesh + one sound | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate-a.txt |
| run_gate_a.py | primary.* resolves to a payload file (S-OW-2) 2 primary key(s) resolved: mesh -> geometry/game.glb, sound -> audio/sfx/crate-impact-hard-surface.wav; every payload_file names a file in its own version | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate-a.txt |
| run_gate_6.py | canonical skeleton recomposes | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate6.txt |
| run_gate_6.py | source hash: cesium | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate6.txt |
| run_gate_6.py | source present: ue | SKIP with reason | SKIP | F:/Stage6UE/export/ue-mannequin.json is absent. It is not redistributable (Epic engine content; NOT redistributed, in the fixture or in this repository), so it is regenerated, not cloned. To produce it: copy "C:/Program Files/Epic Games/UE_5.7/Templates/TemplateResources/High/Mannequin/Content" to F:/Stage6UE/S6/Content/Mannequin, write a minimal S6.uproject enabling PythonScriptPlugin, then: UnrealEditor-Cmd.exe F:/Stage6UE/S6/S6.uproject -run=pythonscript -script="<repo>/retarget/tools/ue_export_skeleton.py" -unattended -nosplash -nullrhi | <second-lab>/codex-review/scratch/gate6.txt |
| run_gate_6.py | source hash: cmu | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate6.txt |
| run_gate_6.py | cesium: scan finds a distinguished pose | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate6.txt |
| run_gate_6.py | cesium: a wrong calibration pose breaks it binding on the worst candidate moves the pose by 0.8878 rad (50.9 deg) at r-toe, threshold >= 0.30 | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate6.txt |
| run_gate_6.py | cesium: per-bone error is frame-invariant | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate6.txt |
| run_gate_6.py | cesium: round trip through core.anim.clip | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate6.txt |
| run_gate_6.py | cesium: retarget moves rotations only | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate6.txt |
| run_gate_6.py | cesium: retargeted figure is plausible | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate6.txt |
| run_gate_6.py | cmu: scan finds a distinguished pose | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate6.txt |
| run_gate_6.py | cmu: a wrong calibration pose breaks it | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate6.txt |
| run_gate_6.py | cmu: per-bone error is frame-invariant | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate6.txt |
| run_gate_6.py | cmu: round trip through core.anim.clip | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate6.txt |
| run_gate_6.py | cmu: retarget moves rotations only | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate6.txt |
| run_gate_6.py | cmu: retargeted figure is plausible | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate6.txt |
| run_gate_6.py | transit cesium -> cmu -> canonical | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate6.txt |
| run_gate_6.py | transit cmu -> cesium -> canonical | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate6.txt |
| run_gate_6.py | fixture pinned | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate6.txt |
| run_gate_6.py | fixture present | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate6.txt |
| run_gate_6.py | fixture: werk-core verify | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate6.txt |
| run_gate_6.py | fixture: werk_read.py standalone | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate6.txt |
| run_gate_6.py | fixture: WKAC binary and JSON agree | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate6.txt |
| run_gate_6.py | fixture: clip rotations are unit quaternions worst /q/-1 = 4.16e-08 over 22 x 344 stored rotations | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate6.txt |
| run_gate_9.py | fixture pinned: ista-varun-v1 | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate9.txt |
| run_gate_9.py | werk-core loads fixture #2 | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate9.txt |
| run_gate_9.py | round-trip byte identity | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate9.txt |
| run_gate_9.py | builder is deterministic (author-lab) | PASS with substitute inputs | SKIP | Separate manual rebuild: reconstructed database row, copied evidence, stock-zlib PNG recompression. Audit item 2. | <second-lab>/codex-review/scratch/gate9.txt |
| run_gate_9.py | bootstrap: werk_read.py | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate9.txt |
| run_gate_9.py | bootstrap: werk_read.rs | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate9.txt |
| run_gate_9.py | bootstrap: werk_read.c | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate9.txt |
| run_gate_9.py | WKEM envelope: every §7 assertion | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate9.txt |
| run_gate_9.py | descriptor recomputes (epistemic: measured) worst component drift 1.381e-08 (vector) / 1.108e-08 (palette), declared tolerance 1e-06 | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate9.txt |
| run_gate_9.py | preview_prefix_bytes recomputes (S-15) | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate9.txt |
| run_gate_9.py | entry_order two-pass matching (S-14) | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate9.txt |
| run_gate_9.py | S-18: one node, two versions, shared file 2 file(s) listed by both versions with identical hash and size: recipe/inputs/imperial-painterly.png, recipe/prompt-recorded.txt | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate9.txt |
| run_gate_9.py | recipe hermeticity (law 1, D-REC-1) | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate9.txt |
| run_gate_9.py | palette: JSON and WKEM agree (law 9) | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate9.txt |
| run_gate_9.py | disclosure agrees with the recipe | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate9.txt |
| run_gate_12.py | fixture pinned | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate12.txt |
| run_gate_12.py | fixture present | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate12.txt |
| run_gate_12.py | cargo build --release | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate12.txt |
| run_gate_12.py | werk-core verify | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate12.txt |
| run_gate_12.py | bootstrap: werk_read.py | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate12.txt |
| run_gate_12.py | bootstrap: werk_read.rs | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate12.txt |
| run_gate_12.py | bootstrap: werk_read.c | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate12.txt |
| run_gate_12.py | gsplat reparses from declared offsets | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate12.txt |
| run_gate_12.py | gsplat payload values (all 281498) | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate12.txt |
| run_gate_12.py | DC-band degradation is exact | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate12.txt |
| run_gate_12.py | package regenerates itself from its own tools intermediate PLY MATCHES (15764528 B, recipe declared 6ffaf5691f34); WKGS byte-identical in 0.4 s, nothing from this repo on the path | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate12.txt |
| run_gate_12.py | embedded tools resolve inside the file | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate12.txt |
| run_gate_12.py | round trip: rebuild is byte-identical | unavailable | FAIL | Archive identity not established. Separate computed-payload matches do not satisfy this clause. Audit item 12e. | <second-lab>/codex-review/scratch/gate12.txt |
| run_gate_12.py | damaged variant: one node dies, the rest load werk-core exit 1, 1 hash-mismatch on splats/plush.wkgs, 1 dead node; both readers agree; 2 enhances edges degraded and reported; werk_read.py still verifies 80/80 files over 16 of 17 nodes | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate12.txt |
| run_gate_12.py | INRIA PLY ingest, real trainer output | SKIP with reason | SKIP | F:\splat-foley\data\generated\marble-cellar.ply is not on this machine | <second-lab>/codex-review/scratch/gate12.txt |
| run_gate_12.py | ascii PLY, sh_degree 3, xyzw reorder | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate12.txt |
| run_gate_12.py | fixtures.json record | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate12.txt |
| run_gate_12.py | Blender vendored spec is current | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/gate12.txt |
| run_gate_cc0_public.py | lean clean: binding load | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-public.txt |
| run_gate_cc0_public.py | lean clean: round-trip byte identity | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-public.txt |
| run_gate_cc0_public.py | lean clean: werk_read.py --verify --strict | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-public.txt |
| run_gate_cc0_public.py | lean clean: extract mesh blob (glTF magic) | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-public.txt |
| run_gate_cc0_public.py | lean clean: primary.mesh resolves to game.glb | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-public.txt |
| run_gate_cc0_public.py | lean damaged: exact dead/skip report | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-public.txt |
| run_gate_cc0_public.py | lean damaged: werk_read.py reports the corruption exit 1, names disclosure/disclosure.json | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-public.txt |
| run_gate_cc0_public.py | full clean: binding load | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-public.txt |
| run_gate_cc0_public.py | full clean: round-trip byte identity | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-public.txt |
| run_gate_cc0_public.py | full clean: werk_read.py --verify --strict | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-public.txt |
| run_gate_cc0_public.py | full clean: extract mesh blob (glTF magic) | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-public.txt |
| run_gate_cc0_public.py | full clean: primary.mesh resolves to game.glb | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-public.txt |
| run_gate_cc0_public.py | full damaged: exact dead/skip report | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-public.txt |
| run_gate_cc0_public.py | full damaged: werk_read.py reports the corruption exit 1, names audio/sfx/crate-cc0-click.wav | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-public.txt |
| run_gate_cc0_image.py | image clean: binding load | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-image.txt |
| run_gate_cc0_image.py | image clean: round-trip byte identity | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-image.txt |
| run_gate_cc0_image.py | image clean: werk_read.py --verify --strict | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-image.txt |
| run_gate_cc0_image.py | image clean: extract source blob (JPEG magic) | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-image.txt |
| run_gate_cc0_image.py | image clean: extract descriptor blob (WKEM magic) style-embedding.wkem 1136 bytes, magic b'WKEM' | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-image.txt |
| run_gate_cc0_image.py | image clean: primary.image / thumbnail resolve primary.image -> image/source.jpg, primary.thumbnail -> image/thumb-256.png | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-image.txt |
| run_gate_cc0_image.py | image damaged: exact dead/skip report | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-image.txt |
| run_gate_cc0_image.py | image damaged: werk_read.py reports the corruption exit 1, names disclosure/disclosure.json | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-image.txt |
| run_gate_cc0_image.py | image: builder is deterministic (rebuild identical) two builds, byte-identical | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-image.txt |
| run_gate_cc0_gsplat.py | gsplat clean: binding load | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-gsplat.txt |
| run_gate_cc0_gsplat.py | gsplat clean: round-trip byte identity | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-gsplat.txt |
| run_gate_cc0_gsplat.py | gsplat clean: werk_read.py --verify --strict | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-gsplat.txt |
| run_gate_cc0_gsplat.py | gsplat clean: extract splat blob (WKGS magic) | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-gsplat.txt |
| run_gate_cc0_gsplat.py | gsplat clean: extract point-cloud blob (WKPC magic) points/cc0-sphere.wkpc 90960 bytes, magic b'WKPC' | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-gsplat.txt |
| run_gate_cc0_gsplat.py | gsplat clean: primary.geometry resolves to WKGS primary.geometry -> splats/cc0-sphere.wkgs | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-gsplat.txt |
| run_gate_cc0_gsplat.py | gsplat damaged: exact dead/skip report | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-gsplat.txt |
| run_gate_cc0_gsplat.py | gsplat damaged: werk_read.py reports the corruption exit 1, names points/cc0-sphere.wkpc | public PASS on original inputs | PASS | Retained public gate run. | <second-lab>/codex-review/scratch/cc0-gsplat.txt |
| Blender adapter | add-on selftest (no Blender) | public PASS on original inputs | PASS | Original adapter gate inputs. | <second-lab>/audit-scratch/item12/blender-gate.out.txt |
| Blender adapter | vendored copies byte-identical | public PASS on original inputs | PASS | Original adapter gate inputs. | <second-lab>/audit-scratch/item12/blender-gate.out.txt |
| Blender adapter | fixture pinned: crate-v1 | public PASS on original inputs | PASS | Original adapter gate inputs. | <second-lab>/audit-scratch/item12/blender-gate.out.txt |
| Blender adapter | fixture pinned: crate-v1-damaged | public PASS on original inputs | PASS | Original adapter gate inputs. | <second-lab>/audit-scratch/item12/blender-gate.out.txt |
| Blender adapter | fixture pinned: gsplat-v1 | public PASS on original inputs | PASS | Original adapter gate inputs. | <second-lab>/audit-scratch/item12/blender-gate.out.txt |
| Blender adapter | fixtures present | public PASS on original inputs | PASS | Original adapter gate inputs. | <second-lab>/audit-scratch/item12/blender-gate.out.txt |
| Blender adapter | Blender located | public PASS on original inputs | PASS | Original adapter gate inputs. | <second-lab>/audit-scratch/item12/blender-gate.out.txt |
| Blender adapter | add-on zip builds | public PASS on original inputs | PASS | Original adapter gate inputs. | <second-lab>/audit-scratch/item12/blender-gate.out.txt |
| Blender adapter | Blender run | public PASS on original inputs | PASS | Original adapter gate inputs. | <second-lab>/audit-scratch/item12/blender-gate.out.txt |
| Blender adapter | registration | public PASS on original inputs | PASS | Original adapter gate inputs. | <second-lab>/audit-scratch/item12/blender-gate.out.txt |
| Blender adapter | install from zip | public PASS on original inputs | PASS | Original adapter gate inputs. | <second-lab>/audit-scratch/item12/blender-gate.out.txt |
| Blender adapter | import: clean fixture | public PASS on original inputs | PASS | Original adapter gate inputs. | <second-lab>/audit-scratch/item12/blender-gate.out.txt |
| Blender adapter | import: damaged fixture | public PASS on original inputs | PASS | Original adapter gate inputs. | <second-lab>/audit-scratch/item12/blender-gate.out.txt |
| Blender adapter | round trip: werk -> Blender -> werk | public PASS on original inputs | PASS | Original adapter gate inputs. | <second-lab>/audit-scratch/item12/blender-gate.out.txt |
| Blender adapter | exported .werk: werk-core verify | public PASS on original inputs | PASS | Original adapter gate inputs. | <second-lab>/audit-scratch/item12/blender-gate.out.txt |
| Blender adapter | exported .werk: werk_read.py standalone 63/63 files verified over 8 resolved node(s) (exit 0) | public PASS on original inputs | PASS | Original adapter gate inputs. | <second-lab>/audit-scratch/item12/blender-gate.out.txt |
| Blender adapter | writer determinism | public PASS on original inputs | PASS | Original adapter gate inputs. | <second-lab>/audit-scratch/item12/blender-gate.out.txt |
| Blender adapter | rig round trip (skeleton + clip) | public PASS on original inputs | PASS | Original adapter gate inputs. | <second-lab>/audit-scratch/item12/blender-gate.out.txt |
| Blender adapter | point cloud + gsplat import | public PASS on original inputs | PASS | Original adapter gate inputs. | <second-lab>/audit-scratch/item12/blender-gate.out.txt |
| Blender adapter | textured round trip (core.tex + slots) 2 core.tex node(s) declared {"tex-basecolor": "srgb", "tex-roughmap": "linear"}; 2 image(s) back as {"tex-basecolor": "sRGB", "tex-roughmap": "Non-Color"}; slots ['base_color', 'metallic_roughness']; metallic 0.25 -> 0.25; 855693 B | public PASS on original inputs | PASS | Original adapter gate inputs. | <second-lab>/audit-scratch/item12/blender-gate.out.txt |
| Gate 3B | wooden-crate-01-noimg: pipeline runs unattended 119.6 s, exit 0, no prompts | PASS with substitute inputs | PASS | Example original. Crate geometry original, textures replaced. Lantern replaced by CesiumMan. | <second-lab>/audit-scratch/item4/gate3b-py314.out.txt |
| Gate 3B | wooden-crate-01-noimg: werk-core loads | PASS with substitute inputs | PASS | Example original. Crate geometry original, textures replaced. Lantern replaced by CesiumMan. | <second-lab>/audit-scratch/item4/gate3b-py314.out.txt |
| Gate 3B | wooden-crate-01-noimg: werk_read.py standalone 89/89 files verified over 34 resolved node(s) | PASS with substitute inputs | PASS | Example original. Crate geometry original, textures replaced. Lantern replaced by CesiumMan. | <second-lab>/audit-scratch/item4/gate3b-py314.out.txt |
| Gate 3B | wooden-crate-01-noimg: JSON Schema validation manifest + 8 payload documents against the package's own spec/, 0 problem(s) | PASS with substitute inputs | PASS | Example original. Crate geometry original, textures replaced. Lantern replaced by CesiumMan. | <second-lab>/audit-scratch/item4/gate3b-py314.out.txt |
| Gate 3B | wooden-crate-01-noimg: every node stamped, every derived hash recomputes 34 versions stamped, 24 derived, 24 input_hash recomputed and matched, 0 problem(s) | PASS with substitute inputs | PASS | Example original. Crate geometry original, textures replaced. Lantern replaced by CesiumMan. | <second-lab>/audit-scratch/item4/gate3b-py314.out.txt |
| Gate 3B | wooden-crate-01-noimg: binary envelopes parse 6 envelope file(s) | PASS with substitute inputs | PASS | Example original. Crate geometry original, textures replaced. Lantern replaced by CesiumMan. | <second-lab>/audit-scratch/item4/gate3b-py314.out.txt |
| Gate 3B | cesiumman-subst: pipeline runs unattended | PASS with substitute inputs | PASS | Example original. Crate geometry original, textures replaced. Lantern replaced by CesiumMan. | <second-lab>/audit-scratch/item4/gate3b-py314.out.txt |
| Gate 3B | cesiumman-subst: werk-core loads | PASS with substitute inputs | PASS | Example original. Crate geometry original, textures replaced. Lantern replaced by CesiumMan. | <second-lab>/audit-scratch/item4/gate3b-py314.out.txt |
| Gate 3B | cesiumman-subst: werk_read.py standalone | PASS with substitute inputs | PASS | Example original. Crate geometry original, textures replaced. Lantern replaced by CesiumMan. | <second-lab>/audit-scratch/item4/gate3b-py314.out.txt |
| Gate 3B | cesiumman-subst: JSON Schema validation | PASS with substitute inputs | PASS | Example original. Crate geometry original, textures replaced. Lantern replaced by CesiumMan. | <second-lab>/audit-scratch/item4/gate3b-py314.out.txt |
| Gate 3B | cesiumman-subst: every node stamped, every derived hash recomputes 35 versions stamped, 25 derived, 25 input_hash recomputed and matched, 0 problem(s) | PASS with substitute inputs | PASS | Example original. Crate geometry original, textures replaced. Lantern replaced by CesiumMan. | <second-lab>/audit-scratch/item4/gate3b-py314.out.txt |
| Gate 3B | cesiumman-subst: binary envelopes parse | PASS with substitute inputs | PASS | Example original. Crate geometry original, textures replaced. Lantern replaced by CesiumMan. | <second-lab>/audit-scratch/item4/gate3b-py314.out.txt |
| Gate 3B | example: pipeline runs unattended | public PASS on original inputs | PASS | Original embedded example inputs. Native tools, Python 3.14.0. | <second-lab>/audit-scratch/item4/gate3b-py314.out.txt |
| Gate 3B | example: werk-core loads | public PASS on original inputs | PASS | Original embedded example inputs. Native tools, Python 3.14.0. | <second-lab>/audit-scratch/item4/gate3b-py314.out.txt |
| Gate 3B | example: werk_read.py standalone | public PASS on original inputs | PASS | Original embedded example inputs. Native tools, Python 3.14.0. | <second-lab>/audit-scratch/item4/gate3b-py314.out.txt |
| Gate 3B | example: JSON Schema validation | public PASS on original inputs | PASS | Original embedded example inputs. Native tools, Python 3.14.0. | <second-lab>/audit-scratch/item4/gate3b-py314.out.txt |
| Gate 3B | example: every node stamped, every derived hash recomputes 33 versions stamped, 23 derived, 23 input_hash recomputed and matched, 0 problem(s) | public PASS on original inputs | PASS | Original embedded example inputs. Native tools, Python 3.14.0. | <second-lab>/audit-scratch/item4/gate3b-py314.out.txt |
| Gate 3B | example: binary envelopes parse | public PASS on original inputs | PASS | Original embedded example inputs. Native tools, Python 3.14.0. | <second-lab>/audit-scratch/item4/gate3b-py314.out.txt |
| Gate 3B | determinism: two --reproducible runs agree | public PASS on original inputs | PASS | Original embedded example inputs. Native tools, Python 3.14.0. | <second-lab>/audit-scratch/item4/gate3b-py314.out.txt |
| Store | test_gear_table_spot_values | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_chunking.py |
| Store | test_chunking_matches_the_published_vector | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_chunking.py |
| Store | test_reassembly_identity_and_size_bounds | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_chunking.py |
| Store | test_boundaries_do_not_depend_on_read_size | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_chunking.py |
| Store | test_small_edit_disturbs_few_chunks | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_chunking.py |
| Store | test_recipe_round_trips_and_checks | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_chunking.py |
| Store | test_ingest_chunks_large_payloads_and_materializes_byte_exact | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_chunking.py |
| Store | test_small_payloads_stay_whole | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_chunking.py |
| Store | test_edit_costs_chunks_not_the_file | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_chunking.py |
| Store | test_put_stream_chunked_refuses_mismatch_and_adds_nothing | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_chunking.py |
| Store | test_gc_keeps_shared_chunks_and_sweeps_orphans | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_chunking.py |
| Store | test_scrub_catches_a_corrupt_chunk_and_materialization_fails_loudly | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_chunking.py |
| Store | test_scrub_quarantines_a_lying_recipe | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_chunking.py |
| Store | test_sync_transfers_only_the_changed_chunks | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_chunking.py |
| Store | test_chunking_can_be_disabled | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_chunking.py |
| Store | test_pre_cdc_store_layout_keeps_working | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_chunking.py |
| Store | test_shared_blobs_are_stored_once | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_dedup.py |
| Store | test_both_versions_still_materialize_after_dedup | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_dedup.py |
| Store | test_dedup_on_the_real_corpus | SKIP with reason | SKIP | Private corpus absent. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_dedup.py |
| Store | test_diff_reports_versions_files_and_the_changelog | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_diff.py |
| Store | test_diff_json_and_text_agree | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_diff.py |
| Store | test_diff_of_a_package_with_itself_is_empty | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_diff.py |
| Store | test_reverse_diff_reports_removal | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_diff.py |
| Store | test_blob_accounting_predicts_what_a_sync_would_move | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_diff.py |
| Store | test_garbage_goes_and_referenced_survives | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_gc.py |
| Store | test_inactive_versions_are_roots_too | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_gc.py |
| Store | test_a_pin_keeps_an_otherwise_unreachable_object | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_gc.py |
| Store | test_gc_refuses_when_a_root_cannot_be_read | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_gc.py |
| Store | test_scrub_finds_a_deliberately_corrupted_object | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_gc.py |
| Store | test_scrub_can_report_without_quarantining | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_gc.py |
| Store | test_key_is_the_manifest_hash_with_no_translation | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_objects.py |
| Store | test_dedup_writes_nothing_the_second_time | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_objects.py |
| Store | test_mismatch_refuses_and_stores_nothing | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_objects.py |
| Store | test_streaming_never_holds_the_payload_whole | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_objects.py |
| Store | test_copy_to_verifies_on_the_way_out | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_objects.py |
| Store | test_missing_object_is_named | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_objects.py |
| Store | test_remove_prunes_empty_fanout_dirs_but_not_the_root | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_objects.py |
| Store | test_is_hash_rejects_uppercase_and_short | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_objects.py |
| Store | test_directory_roundtrip_is_byte_identical | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_roundtrip.py |
| Store | test_zip_roundtrip_is_byte_identical_and_preview_first | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_roundtrip.py |
| Store | test_materialization_fails_loudly_when_the_store_rotted | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_roundtrip.py |
| Store | test_ingest_refuses_a_tampered_package | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_roundtrip.py |
| Store | test_ingest_refuses_a_floating_file | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_roundtrip.py |
| Store | test_unsigned_package_round_trips_and_says_so | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_roundtrip.py |
| Store | test_stripping_the_signature_after_ingest_is_caught | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_roundtrip.py |
| Store | test_two_ingests_of_the_same_package_are_one_ref | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_roundtrip.py |
| Store | test_rfc8032_vectors parameter 1 | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_signature.py |
| Store | test_rfc8032_vectors parameter 2 | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_signature.py |
| Store | test_rfc8032_vectors parameter 3 | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_signature.py |
| Store | test_verify_rejects_flipped_bit | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_signature.py |
| Store | test_three_states_are_distinct | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_signature.py |
| Store | test_broken_link_is_detected | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_signature.py |
| Store | test_pretty_printing_does_not_break_the_chain | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_signature.py |
| Store | test_first_push_moves_everything_then_nothing | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_sync.py |
| Store | test_second_package_moves_only_the_new_node_versions | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_sync.py |
| Store | test_the_far_side_can_materialize_byte_exact | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_sync.py |
| Store | test_sync_is_resumable_by_construction | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_sync.py |
| Store | test_receiver_verifies_rather_than_trusting_the_sender | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_sync.py |
| Store | test_pull_is_push_with_the_ends_swapped | public PASS on original inputs | PASS | Published test inputs. Retained 58 PASS, 1 SKIP. | <second-lab>/codex-review/scratch/store-tests.txt; repo:store/tests/test_sync.py |
| Unreal engine-free core | basis change | public PASS on original inputs | PASS | Retained audit item 12b: 10 PASS with MSVC 19.44. | <second-lab>/unavailable-audit/AUDIT.md |
| Unreal engine-free core | sha-256 | public PASS on original inputs | PASS | Retained audit item 12b: 10 PASS with MSVC 19.44. | <second-lab>/unavailable-audit/AUDIT.md |
| Unreal engine-free core | store-mode zip + crc32 | public PASS on original inputs | PASS | Retained audit item 12b: 10 PASS with MSVC 19.44. | <second-lab>/unavailable-audit/AUDIT.md |
| Unreal engine-free core | json (MINI-SPECS 3 subset) | public PASS on original inputs | PASS | Retained audit item 12b: 10 PASS with MSVC 19.44. | <second-lab>/unavailable-audit/AUDIT.md |
| Unreal engine-free core | glb read/write | public PASS on original inputs | PASS | Retained audit item 12b: 10 PASS with MSVC 19.44. | <second-lab>/unavailable-audit/AUDIT.md |
| Unreal engine-free core | manifest parse (golden fixture) | public PASS on original inputs | PASS | Retained audit item 12b: 10 PASS with MSVC 19.44. | <second-lab>/unavailable-audit/AUDIT.md |
| Unreal engine-free core | package open + verify all hashes | public PASS on original inputs | PASS | Retained audit item 12b: 10 PASS with MSVC 19.44. | <second-lab>/unavailable-audit/AUDIT.md |
| Unreal engine-free core | primary mesh -> UE space | public PASS on original inputs | PASS | Retained audit item 12b: 10 PASS with MSVC 19.44. | <second-lab>/unavailable-audit/AUDIT.md |
| Unreal engine-free core | audio payloads are readable WAV | public PASS on original inputs | PASS | Retained audit item 12b: 10 PASS with MSVC 19.44. | <second-lab>/unavailable-audit/AUDIT.md |
| Unreal engine-free core | damage gauntlet | public PASS on original inputs | PASS | Retained audit item 12b: 10 PASS with MSVC 19.44. | <second-lab>/unavailable-audit/AUDIT.md |
| Unreal round trip | texture import: colour spaces | unavailable | NOT RUN | UE 5.7 absent. | repo:adapters/unreal/tests/roundtrip_gate.py |
| Unreal round trip | mesh import: UVs survived the build | unavailable | NOT RUN | UE 5.7 absent. | repo:adapters/unreal/tests/roundtrip_gate.py |
| Unreal round trip | material import: slots bound | unavailable | NOT RUN | UE 5.7 absent. | repo:adapters/unreal/tests/roundtrip_gate.py |
| Unreal round trip | export: textured entity | unavailable | NOT RUN | UE 5.7 absent. | repo:adapters/unreal/tests/roundtrip_gate.py |
| Unreal round trip | texture export: three real PNGs | unavailable | NOT RUN | UE 5.7 absent. | repo:adapters/unreal/tests/roundtrip_gate.py |
| Unreal round trip | texture round trip: pixels | unavailable | NOT RUN | UE 5.7 absent. | repo:adapters/unreal/tests/roundtrip_gate.py |
| Unreal round trip | material round trip: slots | unavailable | NOT RUN | UE 5.7 absent. | repo:adapters/unreal/tests/roundtrip_gate.py |
| Unreal round trip | export: no phantom master material | unavailable | NOT RUN | UE 5.7 absent. | repo:adapters/unreal/tests/roundtrip_gate.py |
| Unreal round trip | re-import: the exported package | unavailable | NOT RUN | UE 5.7 absent. | repo:adapters/unreal/tests/roundtrip_gate.py |
| Unreal round trip | reader: loaders/werk_read.py | unavailable | NOT RUN | UE 5.7 absent. | repo:adapters/unreal/tests/roundtrip_gate.py |
| Unreal round trip | import: crate-v1 | unavailable | NOT RUN | UE 5.7 absent. | repo:adapters/unreal/tests/roundtrip_gate.py |
| Unreal round trip | import: crate-tex-v1 | unavailable | NOT RUN | UE 5.7 absent. | repo:adapters/unreal/tests/roundtrip_gate.py |
| Unreal round trip | import: ista-varun-v1 | unavailable | NOT RUN | UE 5.7 absent. | repo:adapters/unreal/tests/roundtrip_gate.py |
| Unreal round trip | import: crate-v1-damaged | unavailable | NOT RUN | UE 5.7 absent. | repo:adapters/unreal/tests/roundtrip_gate.py |
| Unreal round trip | reader: jsonschema (manifest + material) | unavailable | NOT RUN | UE 5.7 absent. | repo:adapters/unreal/tests/roundtrip_gate.py |
| Unreal round trip | reader: werk_gate.exe (this adapter's core) | unavailable | NOT RUN | UE 5.7 absent. | repo:adapters/unreal/tests/roundtrip_gate.py |
| Unreal live editor | MCP: list /Game/Werk assets | unavailable | NOT RUN | UE 5.7 absent. | repo:tools/ue_mcp/proof_session.py |
| Unreal live editor | level: sun, sky and floor | unavailable | NOT RUN | UE 5.7 absent. | repo:tools/ue_mcp/proof_session.py |
| Unreal live editor | in-editor: the mesh IS shaded by the imported textures | unavailable | NOT RUN | UE 5.7 absent. | repo:tools/ue_mcp/proof_session.py |
| Unreal live editor | MCP: spawn the imported meshes | unavailable | NOT RUN | UE 5.7 absent. | repo:tools/ue_mcp/proof_session.py |
| Unreal live editor | MCP: viewport screenshots on disk | unavailable | NOT RUN | UE 5.7 absent. | repo:tools/ue_mcp/proof_session.py |
| Unreal live editor | screenshots: the two framings really differ | unavailable | NOT RUN | UE 5.7 absent. | repo:tools/ue_mcp/proof_session.py |

Additional scope limits:

| Gate or measurement | Coverage class | Reason or evidence |
|---|---|---|
| Gate 9 fresh-agent clause | PASS with substitute inputs | Retained round-2 readers rerun on the current image fixture. Historical image builds are absent. |
| Gate 12 fresh-agent clause | public PASS on original inputs | Existing full-task splat report, dated 2026-10-12. This is the source date. |
| Unreal engine-free core, 10 clauses | public PASS on original inputs | Audit item 12b, MSVC 19.44. Individual clause output still needs locating. |
| Unreal round trip, 16 clauses | unavailable | UE 5.7 absent. No installation permitted. |
| Unreal live editor, 6 clauses | unavailable | UE 5.7 absent. |
| CUB gate | author-lab only | Gate source and original inputs unavailable. Audit item 12f. |
| Store, private corpus clause | SKIP with reason | Private production corpus unavailable. |
| Store, substitute corpus measurements | PASS with substitute inputs | Crate-v1 corpus. These measurements do not reproduce the published private-corpus numbers. |
| MinGW self-run rebuild | unavailable | MinGW is absent on this host. The MSVC rebuild is a substitute compiler check. |

The 16 Unreal round-trip checks and six live-editor checks have individual rows above.
Two mutually exclusive jsonschema branches represent one check. The CUB source is unavailable.
Its individual clauses cannot be reconstructed from an aggregate author report.
