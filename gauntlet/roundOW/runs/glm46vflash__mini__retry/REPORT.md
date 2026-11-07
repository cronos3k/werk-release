# REPORT.md

**Success:** Succeeded

Did the program open the container, list node graph with meanings, verify every declared hash, extract primary mesh and one sound?
Yes

What was extracted:
- Primary mesh: geometry/game.glb
  - Declared SHA-256: eee8b3cbc87703fc945555efec8fdcb0fb133f6c94cf75c8643b57189c4ef2ce
- One sound: audio/sfx/crate-impact-hard-surface.wav
  - Declared SHA-256: 1e634f03aebdb0ee82a4c24a0174d381a0552e6dfb03e996b34de8905359aa5e

Did we open, run or port any reader program INSIDE the file?
No. We did not use any bundled readers; all parsing was done manually.

Which files inside the package were read:
- MANIFEST.json
- All node entries from nodes array in manifest
The unblocking file was: MANIFEST.json (provided structure and paths)

What wanted from outside the file could not be obtained:
- None. All required information was derived from the manifest.

Stumbles, ambiguities or issues encountered:
- No major stumbles; format specification was clear and consistent.
- Ambiguous points: None found in this fixture.

Estimated wall-clock times per phase:
- Reading manifest: ~0.1s
- Integrity verification: ~0.5s
- Extraction: ~0.2s