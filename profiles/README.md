# Profiles carried in their packages

Six profiles of the ArtCraft applications, brought into the release without a change to
`spec/` (release spec digest `55882f4b…`, measured again after this folder was added). Each is
a profile in the sense of SPEC §2.2: **a profile is defined by documents that travel in the
package.** A package of one of these profiles carries, as files of its `core.spec` node:

* the whole release `spec/` and `loaders/`, unchanged (the release library vendors them);
* the profile's narrative (`spec/PROFILE-<NAME>.md`, manifest `profile_spec`), its manifest
  schema (manifest `manifest_schema`), its conventions map (`conventions_map`), the schemas and
  layouts of its payloads (`schemas`, `layouts`), and the ArtCraft base rules
  (`spec/CRAFT-BASE.md`, `spec/NOT-CARRIED.md`) — the files under `profiles/<name>/spec/`;
* for every foreign encoding a payload uses, the format definition (SPEC §3.18,
  `spec/formats/<id>.md`, manifest `formats`) and its reference implementation as a `core.tool`
  node, source only (SPEC §3.17) — from `profiles/_formats/`;
* the profile's release reference reader, as `core.tool` node `reader-<name>`, source only.

A reader that does not know the profile validates the manifest against the base schema and the
package's own schema, reports one `unsupported-profile` warning, skips the profile's node types
(listed, hash-verified, extractable), and validates every JSON payload the `schemas` map names
(SPEC §2.2 steps 1-6). Nothing in a package is ever run.

| profile | from | definition | reference reader | builder | fixture |
|---|---|---|---|---|---|
| `raster-layers/1` | PhotoCraft | [raster-layers/](raster-layers/) [PROFILE.md](raster-layers/PROFILE.md) | `read_raster_layers.py` | `build_raster_layers.py` | `fixtures/raster-layers-v1.werk` |
| `vector-art/1` | VectorCraft | [vector-art/](vector-art/) [PROFILE.md](vector-art/PROFILE.md) | `read_vector_art.py` | `build_vector_art.py` | `fixtures/vector-art-v1.werk` |
| `motion-comp/1` | EffectCraft | [motion-comp/](motion-comp/) [PROFILE.md](motion-comp/PROFILE.md) | `read_motion_comp.py` | `build_motion_comp.py` | `fixtures/motion-comp-v1.werk` |
| `rich-document/1` | WordCraft | [rich-document/](rich-document/) [PROFILE.md](rich-document/PROFILE.md) | `read_rich_document.py` | `build_rich_document.py` | `fixtures/rich-document-v1.werk` |
| `spreadsheet/1` | GridCraft | [spreadsheet/](spreadsheet/) [PROFILE.md](spreadsheet/PROFILE.md) | `read_spreadsheet.py` | `build_spreadsheet.py` | `fixtures/spreadsheet-v1.werk` |
| `presentation/1` | DeckCraft | [presentation/](presentation/) [PROFILE.md](presentation/PROFILE.md) | `read_presentation.py` | `build_presentation.py` | `fixtures/presentation-v1.werk` |

Each `PROFILE.md` says where the normative text is, what the node kinds are, and what the
reference reader outputs. The narrative documents under `<name>/spec/` are the norm.

## Reuse across packages, by content

The fixtures share bytes the way an application suite would: the rich-document picture and the
deck's photograph are the raster-layers composite PNG, byte for byte; the deck embeds the whole
vector-art package (a `core.media.asset` of encoding `zip`) and uses that package's own preview
as the picture's rendition. Equal bytes, equal sha256: a content store keeps one copy
(`profiles/PINS.md` lists the shared hashes).

## Files

```
profiles/
  README.md  PINS.md  VENDORED.json  ALIGNMENT.json
  _formats/            zlib-deflate and zip definitions + reference tools (from the ArtCraft format library)
  <name>/spec/         the profile's definition files (they travel in every package)
  <name>/HOW-TO-READ.md   the package-root reading guide (carried in the readme node)
  <name>/PROFILE.md    summary, and what the reference reader outputs
  <name>/read_<name>.py   reference reader: Python 3.8+, standard library only, one file
  <name>/build_<name>.py  builder of the fixture, with the release library (libs/python)
  fixtures/            the six fixtures + fixtures.json
  results/             what was run on them (see PINS.md)
  tools/               vendor_artcraft.py, align_profiles.py, profilekit.py, build_fixtures.py,
                       verify_fixtures.py, cross_readers.py, damage_profiles.py,
                       probe_blocklist.py, check_readers.py, container_block.py
```

## Rebuild and check

```
python profiles/tools/build_fixtures.py --check            # rebuild all six, compare with the pins
python profiles/tools/verify_fixtures.py --werkc <werkc>   # werkc, python/js/es3 libs, loader, reference readers
python libs/tests/cross_matrix.py --fixtures profiles/fixtures --only none --werkc <werkc>
python profiles/tools/damage_profiles.py --out <scratch> --werkc <werkc>
python profiles/tools/cross_readers.py                     # reference readers vs a second implementation
python profiles/tools/probe_blocklist.py --werkc <werkc> --out <scratch>
python profiles/tools/check_readers.py
```

The builders are deterministic (two builds, identical bytes). Their zlib streams come from the
zlib they run with (1.3.1 for the pins); another zlib may compress differently, which changes
the fixture's bytes and none of what a reader extracts.

## Provenance and the edits

`tools/vendor_artcraft.py` copied every `spec/` file the ArtCraft sample packages of each app
carry that the release `spec/` does not have (`VENDORED.json`: source package and sha256 of
each). Files the release `spec/` already has (SPEC.md, MINI-SPECS.md, README.md,
ENVELOPE.layout.txt, core.revisions.schema.json, the signature examples) are not copied: a
package written by the release library carries the release copies. `tools/align_profiles.py`
made one edit per profile, recorded in `ALIGNMENT.json`: the manifest schema's `core.loader`
capability list gains `summarize-points` and `summarize-gsplat`, which the release loaders
declare (the ArtCraft schemas predate them and refused the release loader nodes). One more
edit is to a file that is not specification: the raster-layers package-root guide
(`HOW-TO-READ.md`, a file of the readme node) said the file was saved by PhotoCraft; it now
says "a raster-layers/1 writer".

## Gaps

* `motion-comp/1`: six definition files the EffectCraft sample does not carry were taken from the
  EffectCraft repository, four of them generated by the application's own schema code
  ([motion-comp/PROFILE.md](motion-comp/PROFILE.md) §1); they are not covered by any fixture.
* Format definitions for embedded originals other than `zlib-deflate` and `zip` (`jpeg`, `gif`,
  `bmp`, `tiff`, `webp`, `sfnt`, `icc`, `emf-wmf`, `cfb`, `ovba`, `opc`, `vectorcraft-native`)
  are in the ArtCraft format library and not in this release; no fixture uses them.
* The reference readers do not draw, lay out text, resolve styles or evaluate formulas; each
  `PROFILE.md` lists what its reader does not do. A dead structure node makes them refuse
  (exit 2) instead of rebuilding the structure from the manifest as the narratives describe.
* The ArtCraft applications have not been rebased on the release (W6); the round trip that ran
  is PhotoCraft's, in a mirror built on the release core (`PINS.md`).
