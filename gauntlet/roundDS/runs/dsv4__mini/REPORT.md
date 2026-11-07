# REPORT

## Success

Opened container: yes
Listed node graph with meanings: yes
Verified every declared hash: no
Extracted primary mesh: yes
Extracted one sound: yes
Extracted bytes hash to declared values: yes

## Extracted files

- mesh: game.glb (from geometry/game.glb)
  - declared sha256: eee8b3cbc87703fc945555efec8fdcb0fb133f6c94cf75c8643b57189c4ef2ce
  - computed sha256: eee8b3cbc87703fc945555efec8fdcb0fb133f6c94cf75c8643b57189c4ef2ce
  - match: True
- sound: crate-impact.wav (from audio/sfx/crate-impact-hard-surface.wav)
  - declared sha256: 1e634f03aebdb0ee82a4c24a0174d381a0552e6dfb03e996b34de8905359aa5e
  - computed sha256: 1e634f03aebdb0ee82a4c24a0174d381a0552e6dfb03e996b34de8905359aa5e
  - match: True

## Reader programs bundled inside

Did we open, run or port any reader program bundled inside the file? No. We did not read the loaders/ source files (except for listing). We did not execute anything from the file.

## Files read, in order

1. MANIFEST.json
2. SIGNATURE.json
3. LICENSE
4. README.txt
5. geometry/game.glb
6. materials/wood.json
7. physics/bounds.json
8. semantics/semantics.json
9. provenance/provenance.json
10. audio/sfx/crate-impact-hard-surface.json
11. audio/sfx/crate-impact-hard-surface.wav
12. audio/sfx/crate-impact-hard-surface.raw.wav
13. audio/sfx/crate-impact-hard-surface.var2.wav
14. audio/sfx/crate-impact-hard-surface.var3.wav
15. spec/MINI-SPECS.md
16. spec/README.md
17. spec/SPEC.md
18. spec/conventions-map.json
19. spec/examples/restposes.example.hex.txt
20. spec/examples/restposes.example.wkrp
21. spec/facets.json
22. spec/layouts/ENVELOPE.layout.txt
23. spec/layouts/restposes.layout.txt
24. spec/schemas/conventions-map.schema.json
25. spec/schemas/core.audio.effect.schema.json
26. spec/schemas/core.material.schema.json
27. spec/schemas/core.phys.bounds.schema.json
28. spec/schemas/core.provenance.schema.json
29. spec/schemas/core.semantics.schema.json
30. spec/schemas/manifest.schema.json
31. spec/schemas/signature.schema.json
32. loaders/werk_read.py
33. loaders/werk_read.rs
34. loaders/werk_read.c
35. LICENSE
36. README.txt
37. x/splat-foley/segments/seg_00.png
38. poses/rest.wkrp
39. spec/MINI-SPECS.md
40. spec/README.md
41. spec/SPEC.md
42. spec/conventions-map.json
43. spec/examples/restposes.example.hex.txt
44. spec/examples/restposes.example.wkrp
45. spec/facets.json
46. spec/layouts/ENVELOPE.layout.txt
47. spec/layouts/restposes.layout.txt
48. spec/schemas/conventions-map.schema.json
49. spec/schemas/core.audio.effect.schema.json
50. spec/schemas/core.material.schema.json
51. spec/schemas/core.phys.bounds.schema.json
52. spec/schemas/core.provenance.schema.json
53. spec/schemas/core.semantics.schema.json
54. spec/schemas/manifest.schema.json
55. spec/schemas/signature.schema.json
56. spec/MINI-SPECS.md
57. spec/README.md
58. spec/SPEC.md
59. spec/conventions-map.json
60. spec/examples/restposes.example.hex.txt
61. spec/examples/restposes.example.wkrp
62. spec/facets.json
63. spec/layouts/ENVELOPE.layout.txt
64. spec/layouts/restposes.layout.txt
65. spec/schemas/conventions-map.schema.json
66. spec/schemas/core.audio.effect.schema.json
67. spec/schemas/core.material.schema.json
68. spec/schemas/core.phys.bounds.schema.json
69. spec/schemas/core.provenance.schema.json
70. spec/schemas/core.semantics.schema.json
71. spec/schemas/manifest.schema.json
72. spec/schemas/signature.schema.json
73. geometry/game.glb
74. geometry/game.glb
75. physics/bounds.json
76. geometry/game.glb
77. audio/sfx/crate-impact-hard-surface.wav

## Wanted from outside and could not get

We wanted the definition of `spec_sha256` (what exactly it hashes) and the full SPEC.md sections that define it. We could not get them from the file (the relevant section was not in the context we had). We attempted to derive it by hashing spec/ files in various orders; result: unverified.

## Stumbles

- `spec_sha256` definition missing from the documentation we had; we tried several concatenation orders and could not confirm it.
- The canonical JSON rules for `input_params` were initially ambiguous (whether absent means `{}`); the spec section 11 clarified it.
- The Ed25519 verification required implementing from scratch; we used the spec formulas and test vector to validate.
- The `primary.sound` node has multiple WAV files; we selected the one marked `role: best` / `payload_file`.
- Some `input_files` referenced in the manifest (e.g. `geometry/source.glb`) are not present in the container, so their `input_hash` could not be verified.

## Damaged/corrupted data

None encountered.

## Wall-clock sense

Phases: opening and reading manifest ~1s, hash verification ~2s, signature verification ~1s, extraction ~1s, report writing ~1s. Total ~6s (estimated).
