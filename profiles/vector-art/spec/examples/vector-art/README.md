# Examples for profile `vector-art/1`

| file | what it is |
|---|---|
| `write_minimal.py` | Writes a minimal valid capsule with the Python standard library alone: the executable form of `spec/PROFILE-VECTOR-ART.md` §7. `python write_minimal.py <any vector-art/1 capsule> <new.werk>` |
| `read_document.py` | Reads a capsule with the Python standard library alone and prints the document as JSON: the executable form of §6. `--originals DIR` writes each image's own file; `--decode DIR` runs, on every payload in a foreign format, the reference decoder the capsule carries for it. |
| `minimal/document.json`, `minimal/artboard-1.json`, `minimal/layer-1.json` | The three payloads of the minimal capsule, byte for byte (§7.1 gives their sizes and sha256). |
| `payloads/layer-every-kind.json` | A `core.vector.layer` payload that uses every kind of object and every member the schema defines. Each object of the layer (each element of `layer.kind.children`) is on a line of its own, without white space. |
| `payloads/<node type>.json` | One real payload of every other JSON node type, each using every member its schema defines. |
| `effects.md` | The ids and parameters of the live effects VectorCraft writes (`effects[].id`, `effects[].params`). |

Every JSON file here validates against `spec/schemas/<node type>.schema.json`.
