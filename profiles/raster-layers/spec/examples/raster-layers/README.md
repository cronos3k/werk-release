# Worked examples for `raster-layers/1`

Every file here is real: the JSON payloads validate against the schemas in `spec/schemas/`,
and the binaries are read by the reference reader of `spec/layouts/ENVELOPE.layout.txt` §7.
They are small on purpose; they are not the files of the document you are holding.

| file | what it is |
|---|---|
| `write_minimal.py` | a complete writer in standard-library Python: the executable form of `spec/PROFILE-RASTER-LAYERS.md` §7. Run it against any `raster-layers/1` capsule to get a new, minimal one. |
| `document.example.json` | a structure node (`core.raster.document`): a canvas, a tree with a group, channels, a path, a comp |
| `layer.raster.example.json` | a pixel layer with a mask and a drop shadow |
| `layer.text.example.json` | a text layer with two character runs and its rendered cache |
| `layer.adjustment.example.json` | a Curves adjustment layer |
| `layer.smart.example.json` | a smart object with an embedded source and one smart filter |
| `channel.example.json` | a spot colour channel |
| `pattern.example.json` | a pattern |
| `path.example.json` | a saved path: a closed triangle |
| `comp.example.json` | a layer comp |
| `text-styles.example.json` | one character style and one paragraph style |
| `variables.example.json` | two variables and one data set |
| `metadata.example.json` | XMP and one text entry |
| `surface.example.wkx` | a surface's index file: 8-bit gray, one tile at (0, 0) |
| `surface.example.hex.txt` | every byte of it, annotated |
| `tiles.example.wkxz` | that surface's tile file as it is stored: a zlib stream of a tile envelope |
| `tiles.example.hex.txt` | the envelope inside it byte by byte, the sha256 of each stage, and how to find any sample |
| `lut3d.example.wkx` | an identity colour lookup table with 2 points per axis |
| `lut3d.example.hex.txt` | every byte of it, annotated |
| `psd-blocks.example.wkx` | a pack of two verbatim Photoshop blocks |
| `psd-blocks.example.hex.txt` | every byte of it, annotated |

The example surface's pixel (x, y) has the gray value (x + 3·y) mod 256, so a decoder can
check itself: the sample at row 2, column 5 is 11.
