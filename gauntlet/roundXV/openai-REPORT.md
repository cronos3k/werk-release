# REPORT ? crate-v1.werk

## Outcome

**Succeeded: yes.** `inspect_werk.py` opened the container, listed all 174 archive entries and all 36 graph nodes with their manifest-supplied meanings, verified the graph/reachability rules and every current-package hash declaration I found, verified the signature chain, and extracted the declared primary mesh plus the declared primary sound's `best` WAV.

The completed verification was:

- 174/174 archive CRC-32 checks passed. The archive library also checked the stored entries while reading them.
- 172/172 `nodes[].versions[].files[].sha256` declarations passed, and 172/172 declared sizes passed.
- 25/25 `input_hash` derivation hashes passed, using ordered raw input digests followed by canonical JSON for `input_params`.
- 1/1 global `spec_sha256` aggregate passed.
- 1/1 separate `license.sha256` declaration passed.
- 1/1 payload-level provenance `consumed[].sha256` declaration passed.
- 2/2 signature manifest SHA-256 anchors and 1/1 `prev_entry_sha256` chain declaration passed.
- 1/1 Ed25519 signature passed after the verifier passed the in-package RFC test vector.
- In total, 203 current-package SHA-256 declarations were accounted for: 199 in `MANIFEST.json`, 3 in `SIGNATURE.json`, and 1 in `provenance/provenance.json`. Hash-looking values inside schemas and `spec/examples/MANIFEST.example.json` describe schemas or a different illustrative package, so they are not declarations about this container.
- The signature state is the specification's exact state token `signed-and-valid`. This establishes byte integrity and possession of the bundled private-key counterpart at signing time; it does not establish a trusted author identity because the package says this is a public DEV key with no external root of trust.

The detailed node graph and file meanings are in `CONTENTS.md`; every individual check and computed value is in `verification.json`.

## Extracted files

| Output | Selected from | Why selected | Bytes | Declared SHA-256 | Computed SHA-256 |
|---|---|---|---:|---|---|
| `primary_mesh.glb` | `geometry/game.glb` in node `geom-game` | `primary.mesh` names the node; its active version has exactly one GLB | 16,736 | `eee8b3cbc87703fc945555efec8fdcb0fb133f6c94cf75c8643b57189c4ef2ce` | `eee8b3cbc87703fc945555efec8fdcb0fb133f6c94cf75c8643b57189c4ef2ce` |
| `primary_sound.wav` | `audio/sfx/crate-impact-hard-surface.wav` in node `audio-crate-impact-hard-surface` | `primary.sound` names the node; this WAV is explicitly `role: "best"` | 17,644 | `1e634f03aebdb0ee82a4c24a0174d381a0552e6dfb03e996b34de8905359aa5e` | `1e634f03aebdb0ee82a4c24a0174d381a0552e6dfb03e996b34de8905359aa5e` |

The computed digests above were taken over the exact byte strings written to disk. The output operation wrote those same byte strings without transformation.

## Bundled reader programs

I did **not** open any bundled reader as source, run it, import it, compile it, or port it. In particular, I did not inspect `loaders/werk_read.py`, `loaders/werk_read.rs`, or `loaders/werk_read.c`. Their bytes were read only as opaque payload during the all-entry CRC/SHA-256 pass, which was necessary to verify every declared file hash. The final reader was independently written from `MANIFEST.json` and the normative material under `spec/`.

I deliberately made this choice after `spec/SPEC.md` explained the loader model. The Python source would have been permissible to read, but doing so was unnecessary and would have weakened the result of the isolation experiment. No program extracted from the container was executed.

## Files read for meaning, in chronological order

The exploratory/semantic reading order was:

1. `MANIFEST.json` ? read first directly from the first stored local record. It identified the profile, container form, conventions, 36 nodes, primary node IDs, all declared file paths/sizes/hashes, and the internal documentation paths.
2. `README.txt` ? confirmed the intended starting point.
3. `spec/README.md` ? first read succeeded but console display failed at a Unicode arrow; it was immediately reread with UTF-8 output. This was the file that most directly **unblocked the task**, because it prescribed the authoritative reading order and mapped each question to a file.
4. `spec/SPEC.md` ? opened first for headings, then reread selectively for sections 1, 2, 5?7, and 10: container, manifest, aggregate hash, degradation, signatures, loader safety, and reader checklist.
5. `spec/MINI-SPECS.md` ? opened first for headings, then reread selectively for JSON canonicalization, ZIP, SHA-256/input hashing, and Ed25519.
6. `spec/schemas/manifest.schema.json` ? checked which hash-bearing fields the manifest can declare.
7. `spec/schemas/signature.schema.json` ? confirmed signature-chain hash meanings, especially that a previous-link digest hashes the UTF-8 hex signature string.
8. `SIGNATURE.json` ? read the actual chain, key, anchor, timestamp, and signature.
9. `provenance/provenance.json` ? opened after an in-package JSON audit found its one additional current-package hash declaration.

`MANIFEST.json`, `spec/SPEC.md`, and `spec/MINI-SPECS.md` were reread several times while narrowing specific rules. I also scanned JSON members inside the package to distinguish actual current-package hashes from schema definitions and example-package hashes. No loader source was decoded or displayed.

## Complete byte-read order during final verification

The final program read every archive entry once in physical/central-directory order below. This is the authoritative complete order for the integrity pass; entries not named in the semantic list above were treated as opaque bytes unless needed for a declared derived hash. `MANIFEST.json` and `SIGNATURE.json` were subsequently parsed from the already-read bytes, and the two extracted payload byte strings were written from that same in-memory pass.

1. `MANIFEST.json`
2. `SIGNATURE.json`
3. `LICENSE`
4. `README.txt`
5. `loaders/werk_read.c`
6. `loaders/werk_read.py`
7. `loaders/werk_read.rs`
8. `spec/MINI-SPECS.md`
9. `spec/PROFILE-IMAGE.md`
10. `spec/README.md`
11. `spec/SPEC.md`
12. `spec/X-C2PA-EXPORT.md`
13. `spec/conventions-map.image.json`
14. `spec/conventions-map.json`
15. `spec/examples/MANIFEST.example.json`
16. `spec/examples/make-examples.py`
17. `spec/examples/restposes.example.hex.txt`
18. `spec/examples/restposes.example.wkrp`
19. `spec/extensions/x.cub.v1.baked.layout.txt`
20. `spec/extensions/x.cub.v1.md`
21. `spec/facets.json`
22. `spec/layouts/ENVELOPE.layout.txt`
23. `spec/layouts/animclip.layout.txt`
24. `spec/layouts/embedding.layout.txt`
25. `spec/layouts/flowfield.layout.txt`
26. `spec/layouts/gsplat.layout.txt`
27. `spec/layouts/imposter.layout.txt`
28. `spec/layouts/points.layout.txt`
29. `spec/layouts/restposes.layout.txt`
30. `spec/layouts/skeleton.layout.txt`
31. `spec/schemas/conventions-map.schema.json`
32. `spec/schemas/core.anim.clip.schema.json`
33. `spec/schemas/core.audio.effect.schema.json`
34. `spec/schemas/core.audio.package.schema.json`
35. `spec/schemas/core.destruct.schema.json`
36. `spec/schemas/core.disclosure.schema.json`
37. `spec/schemas/core.imposter.schema.json`
38. `spec/schemas/core.material.schema.json`
39. `spec/schemas/core.phys.body.schema.json`
40. `spec/schemas/core.phys.bounds.schema.json`
41. `spec/schemas/core.phys.colliders.schema.json`
42. `spec/schemas/core.props.schema.json`
43. `spec/schemas/core.provenance.schema.json`
44. `spec/schemas/core.recipe.schema.json`
45. `spec/schemas/core.retarget.bind.schema.json`
46. `spec/schemas/core.semantics.schema.json`
47. `spec/schemas/core.skeleton.schema.json`
48. `spec/schemas/core.tool.config.schema.json`
49. `spec/schemas/core.tool.schema.json`
50. `spec/schemas/facets.schema.json`
51. `spec/schemas/manifest.image.schema.json`
52. `spec/schemas/manifest.schema.json`
53. `spec/schemas/signature.schema.json`
54. `spec/schemas/x.c2pa.export.schema.json`
55. `spec/skeleton/canonical-humanoid-v1.json`
56. `spec/skeleton/core.hands.v1.json`
57. `spec/skeleton/derive-canonical-humanoid.py`
58. `semantics/semantics.json`
59. `audio/sfx/crate-impact-hard-surface.wav`
60. `materials/wood.json`
61. `physics/bounds.json`
62. `properties/properties.json`
63. `provenance/provenance.json`
64. `geometry/game.glb`
65. `geometry/source.glb`
66. `audio/package.json`
67. `audio/sfx/beam-impact-hard-surface.json`
68. `audio/sfx/beam-impact-hard-surface.raw.wav`
69. `audio/sfx/beam-impact-hard-surface.var2.wav`
70. `audio/sfx/beam-impact-hard-surface.var3.wav`
71. `audio/sfx/beam-impact-hard-surface.wav`
72. `audio/sfx/beam-kicked-hard.json`
73. `audio/sfx/beam-kicked-hard.raw.wav`
74. `audio/sfx/beam-kicked-hard.var2.wav`
75. `audio/sfx/beam-kicked-hard.var3.wav`
76. `audio/sfx/beam-kicked-hard.wav`
77. `audio/sfx/corner-joined-beams.json`
78. `audio/sfx/corner-joined-beams.raw.wav`
79. `audio/sfx/corner-joined-beams.var2.wav`
80. `audio/sfx/corner-joined-beams.var3.wav`
81. `audio/sfx/corner-joined-beams.wav`
82. `audio/sfx/crate-dragged-rough-concrete.json`
83. `audio/sfx/crate-dragged-rough-concrete.var2.wav`
84. `audio/sfx/crate-dragged-rough-concrete.var3.wav`
85. `audio/sfx/crate-dragged-rough-concrete.wav`
86. `audio/sfx/crate-impact-hard-surface.json`
87. `audio/sfx/crate-impact-hard-surface.raw.wav`
88. `audio/sfx/crate-impact-hard-surface.var2.wav`
89. `audio/sfx/crate-impact-hard-surface.var3.wav`
90. `audio/sfx/crate-kicked-hard.json`
91. `audio/sfx/crate-kicked-hard.var2.wav`
92. `audio/sfx/crate-kicked-hard.var3.wav`
93. `audio/sfx/crate-kicked-hard.wav`
94. `audio/sfx/crate-scraped-edge.json`
95. `audio/sfx/crate-scraped-edge.var2.wav`
96. `audio/sfx/crate-scraped-edge.var3.wav`
97. `audio/sfx/crate-scraped-edge.wav`
98. `audio/sfx/crate-set-down-hard.json`
99. `audio/sfx/crate-set-down-hard.raw.wav`
100. `audio/sfx/crate-set-down-hard.var2.wav`
101. `audio/sfx/crate-set-down-hard.var3.wav`
102. `audio/sfx/crate-set-down-hard.wav`
103. `audio/sfx/crate-tipped-over.json`
104. `audio/sfx/crate-tipped-over.raw.wav`
105. `audio/sfx/crate-tipped-over.var2.wav`
106. `audio/sfx/crate-tipped-over.var3.wav`
107. `audio/sfx/crate-tipped-over.wav`
108. `audio/sfx/crate-wind-desert.json`
109. `audio/sfx/crate-wind-desert.raw.wav`
110. `audio/sfx/crate-wind-desert.var2.wav`
111. `audio/sfx/crate-wind-desert.var3.wav`
112. `audio/sfx/crate-wind-desert.wav`
113. `audio/sfx/crate-wind-forest-dense.json`
114. `audio/sfx/crate-wind-forest-dense.var2.wav`
115. `audio/sfx/crate-wind-forest-dense.var3.wav`
116. `audio/sfx/crate-wind-forest-dense.wav`
117. `audio/sfx/crate-wind-forest.json`
118. `audio/sfx/crate-wind-forest.raw.wav`
119. `audio/sfx/crate-wind-forest.var2.wav`
120. `audio/sfx/crate-wind-forest.var3.wav`
121. `audio/sfx/crate-wind-forest.wav`
122. `audio/sfx/dowel-impact-hard-surface.json`
123. `audio/sfx/dowel-impact-hard-surface.raw.wav`
124. `audio/sfx/dowel-impact-hard-surface.var2.wav`
125. `audio/sfx/dowel-impact-hard-surface.var3.wav`
126. `audio/sfx/dowel-impact-hard-surface.wav`
127. `audio/sfx/dowel-kicked-hard.json`
128. `audio/sfx/dowel-kicked-hard.raw.wav`
129. `audio/sfx/dowel-kicked-hard.var2.wav`
130. `audio/sfx/dowel-kicked-hard.var3.wav`
131. `audio/sfx/dowel-kicked-hard.wav`
132. `audio/sfx/front-face-impact-hard-surface.json`
133. `audio/sfx/front-face-impact-hard-surface.raw.wav`
134. `audio/sfx/front-face-impact-hard-surface.var2.wav`
135. `audio/sfx/front-face-impact-hard-surface.var3.wav`
136. `audio/sfx/front-face-impact-hard-surface.wav`
137. `audio/sfx/front-face-kicked-hard.json`
138. `audio/sfx/front-face-kicked-hard.var2.wav`
139. `audio/sfx/front-face-kicked-hard.var3.wav`
140. `audio/sfx/front-face-kicked-hard.wav`
141. `audio/sfx/plank-dragged-wood-floor.json`
142. `audio/sfx/plank-dragged-wood-floor.var2.wav`
143. `audio/sfx/plank-dragged-wood-floor.var3.wav`
144. `audio/sfx/plank-dragged-wood-floor.wav`
145. `audio/sfx/plank-impact-hard-surface.json`
146. `audio/sfx/plank-impact-hard-surface.raw.wav`
147. `audio/sfx/plank-impact-hard-surface.var2.wav`
148. `audio/sfx/plank-impact-hard-surface.var3.wav`
149. `audio/sfx/plank-impact-hard-surface.wav`
150. `audio/sfx/plank-kicked-hard.json`
151. `audio/sfx/plank-kicked-hard.var2.wav`
152. `audio/sfx/plank-kicked-hard.var3.wav`
153. `audio/sfx/plank-kicked-hard.wav`
154. `audio/sfx/plank-scraped-edge.json`
155. `audio/sfx/plank-scraped-edge.raw.wav`
156. `audio/sfx/plank-scraped-edge.var2.wav`
157. `audio/sfx/plank-scraped-edge.var3.wav`
158. `audio/sfx/plank-scraped-edge.wav`
159. `x/splat-foley/segments/seg_00.png`
160. `x/splat-foley/segments/seg_01.png`
161. `x/splat-foley/segments/seg_02.png`
162. `x/splat-foley/segments/seg_03.png`
163. `x/splat-foley/segments/seg_04.png`
164. `x/splat-foley/segments/seg_05.png`
165. `x/splat-foley/segments/seg_06.png`
166. `x/splat-foley/segments/seg_07.png`
167. `x/splat-foley/segments/seg_08.png`
168. `x/splat-foley/segments/seg_09.png`
169. `x/splat-foley/views/view_00.png`
170. `x/splat-foley/views/view_01.png`
171. `x/splat-foley/views/view_02.png`
172. `x/splat-foley/views/view_03.png`
173. `x/splat-foley/views/view_04.png`
174. `x/splat-foley/views/view_05.png`

## Outside information wanted but unavailable

No outside file, directory, URL, package, web result, or repository data was requested or used. I did not list or access any path outside the working directory, and inside the working directory I used only the named container as task input.

The only fact that would require an outside source is whether the signing key belongs to a trusted real-world identity. The in-package specification explicitly says there is no external root of trust, and this fixture labels the signer as a publicly derived DEV key. Therefore I can report a valid cryptographic chain but cannot?and do not?claim trusted authorship. Nothing external was needed for the requested parsing, meanings, hashes, signature math, or extraction.

Python itself and its standard library were the requested execution toolchain, not a source of format knowledge. Format-specific rules came from the container.

## Stumbles, ambiguities, missing material, and time costs

1. My first broad manifest walk emitted far too much detail and the console capture truncated it. No bytes or conclusions were lost, but it cost a pass; I replaced it with targeted summaries.
2. `spec/README.md` contains a Unicode arrow. The file read succeeded, but the Windows console initially encoded output as CP-1252 and raised `UnicodeEncodeError`. I reread it with UTF-8 output. This was a console/tooling problem, not corrupt package text.
3. The task phrase ?every declared hash? is broader than the manifest checklist. The central ?What gets hashed? discussion covers manifest file hashes, manifest anchors, and derivation hashes, but `core.provenance` may itself declare consumed-file hashes. I had to audit the in-package JSON schemas/values to discover that this fixture has one such claim. I verified it too. This was the main documentation-scope ambiguity that cost reasoning time.
4. `spec/examples/MANIFEST.example.json` contains many valid-looking hashes for an explicitly abridged example package. They must not be tested against the current archive. Distinguishing specification/example literals from current-package declarations was necessary; `spec/README.md` does say the example is abridged, which resolved the issue.
5. The global `spec_sha256` construction says to append each file?s ?own sha256.? I used the digest recomputed from the actual bytes, after separately comparing it to the declared file digest. On this valid package those are identical. In a damaged package, computing the aggregate from actual bytes gives the more diagnostic result, but the wording could make an implementer briefly wonder whether to concatenate declared or recomputed digests.
6. Earlier signature-chain entries can name historical manifest bytes that are no longer present, so those anchor values cannot all be recomputed in a multi-entry chain. The specification explicitly resolves this and requires only the final anchor to match current bytes. This fixture has one entry, so every manifest anchor here was directly checkable.
7. The first attempt to create `inspect_werk.py` through the provided patch mechanism failed. A two-byte test patch failed identically, proving it was not source size. I used one direct, workspace-only file write as a fallback. This did not touch the container.
8. I initially considered using the bundled Python loader, then chose not to open it after the internal spec supplied all rules. No time was spent executing or porting it.
9. I did not implement full JSON Schema validation. The task asks for opening, graph meanings, integrity, and extraction; the internal reader checklist distinguishes full schema validation from a bootstrap reader?s structural checks. The program performs the structural checks it relies on and does not claim schema validation.
10. I used Python?s standard-library ZIP implementation in the final program after the manifest declared `form: "zip"`/`zip_compression: "store"` and the internal mini-spec supplied the record rules. The initial manifest itself was reached by reading the visibly stored first local record, so ZIP recognition was not used as an unstated format rule.

I found no documentation that was factually wrong for this fixture. The largest avoidable cost was that payload-level hash claims are not included in one central exhaustive ?all current-package hash declarations? list.

## Damaged or corrupted data

I found no damage: every archive CRC, declared size, content hash, derived hash, aggregate hash, chain hash, and signature check passed. I did not mutate the original, inject damage, make a damaged copy, or attempt repair. The program records mismatches, enforces package-path/reachability/ownership/edge/active-version checks, and writes each selected extraction only after that selected payload?s SHA-256 matches, but I did not run a separate damage gauntlet because it was not necessary to answer the task and would have added generated test input beyond the supplied file.

## Wall-clock sense

These are human estimates, not instrument-grade timings:

- Initial byte/bootstrap inspection and manifest targeting: about 1?2 minutes.
- Reading and narrowing the in-package documentation: about 5 minutes.
- Auditing the exact hash scope, signatures, and primary-file selection: about 3?4 minutes.
- Implementing the independent reader, including the failed patch-tool attempt and fallback: about 8?10 minutes.
- Final verification/extraction itself: under one second of program runtime (about 0.4 seconds including process launch in this environment).
- Report assembly and read-order audit: about 4 minutes.

Overall wall-clock sense: roughly 20?25 minutes.
