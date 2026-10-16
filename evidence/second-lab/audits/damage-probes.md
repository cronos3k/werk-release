# Independent damage probes

Fifty-eight retained programs or reconstructed runtimes have payload probes. Forty-nine have spec probes.
The 23 available second-lab programs are included. The August executable program remains unavailable.
Nine foreign-format fixtures contain no embedded canonical spec. Their spec probes are not applicable.
Photographs have no byte-addressable embedded payload or spec entry. Both hardcopy decoders have clean recovery checks.

Each ZIP probe changes one uncompressed entry byte. ZIP checksums are recomputed and manifest digests stay unchanged.
FBX probes change one embedded texture byte. glTF probes change one texture-file byte. USDZ probes change one texture-entry byte.
These are payload probes, rather than geometry probes. FBX can reject the texture through its image checksum.
The native probes change one model byte or one spec byte. The runtime does not inspect the spec.
A successful vector comparison does not establish package integrity. Windows blocks Kimi execution on this host.

A false-success flag requires an explicit verification claim that contradicts known changed bytes.
A filename in a listing alone does not identify damage. It must occur with an error or mismatch signal.
Exit zero alone does not establish false success. Success for an intact node is separate from whole-package success.
Foreign formats lack declared payload SHA-256 digests. Their lack of detection is not a false cryptographic claim.
The ledger stores intact extractions by exact byte identity and unchanged foreign-format outputs beside these results.

| Attempt | Input basis | Payload exit | Names damage | False verification success | Intact payloads extracted | Spec exit | Names damage | False verification success |
|---|---|---|---|---|---|---|---|---|
| author/roundDS/dsv4__envel | original recorded bytes | 1 | no | no | 0 | 0 | yes | no |
| author/roundDS/dsv4__mini | original recorded bytes | 0 | yes | no | 1 | 0 | yes | no |
| author/roundDS/dsv4__selfrun | Retained MSVC command on the current host | 0/0 | no | no | not applicable | 0/0 | no | no |
| author/roundDS/dsv4__splat__retry | original recorded bytes | 0 | yes | no | 0 | 0 | yes | no |
| author/roundGF/gemma-4-e4b__gsplat | original recorded bytes | 1 | no | no | 0 | 1 | no | no |
| author/roundGF/glm-4.6v-flash__gsplat | original recorded bytes | 0 | no | no | 0 | 0 | no | no |
| author/roundGF/qwen3-coder-30b__selfrun | not rerun | not applicable | unknown or not applicable | unknown or not applicable | not applicable | not applicable | unknown or not applicable | unknown or not applicable |
| author/roundOW/ebai27b__mini | labelled current-fixture substitute | 1 | no | no | 0 | 1 | no | no |
| author/roundOW/ebai27b__mini__retry | labelled current-fixture substitute | 0 | yes | no | 1 | 0 | yes | no |
| author/roundOW/glm46vflash__mini | labelled current-fixture substitute | 0 | no | yes | 0 | 0 | no | yes |
| author/roundOW/glm46vflash__mini__retry | labelled current-fixture substitute | 0 | yes | no | 0 | 0 | yes | no |
| author/roundOW/glm47flash__mini | not rerun | not applicable | unknown or not applicable | unknown or not applicable | not applicable | not applicable | unknown or not applicable | unknown or not applicable |
| author/roundOW/glm47flash__mini__retry | labelled current-fixture substitute | 0 | no | no | 1 | 0 | no | no |
| author/roundOW/llama31-8b__envel | labelled current-fixture substitute | 1 | no | no | 0 | 1 | no | no |
| author/roundOW/llama31-8b__mini | labelled current-fixture substitute | 0 | no | no | 0 | 0 | no | no |
| author/roundOW/llama31-8b__mini__retry | labelled current-fixture substitute | 0 | no | no | 0 | 0 | no | no |
| author/roundOW/postfix-gemma4e4b__mini | original recorded bytes | 0 | yes | no | 0 | 0 | yes | no |
| author/roundOW/postfix-gemma4e4b__mini__retry | original recorded bytes | 1 | yes | no | 1 | 0 | yes | no |
| author/roundOW/postfix-glm46vflash__mini | original recorded bytes | 0 | yes | no | 1 | 0 | no | no |
| author/roundOW/postfix-llama31-8b__mini | original recorded bytes | 0 | no | no | 1 | 0 | no | no |
| author/roundOW/postfix-llama31-8b__mini__retry | original recorded bytes | 0 | yes | no | 0 | 0 | yes | no |
| author/roundOW/postfix-nemotron4b__mini | original recorded bytes | 1 | no | no | 0 | 1 | no | no |
| author/roundOW/postfix-nemotron4b__mini__retry | original recorded bytes | 0 | no | no | 0 | 0 | no | no |
| author/roundOW/postfix-qwen4b__mini | original recorded bytes | 1 | no | no | 0 | 1 | no | no |
| author/roundOW/postfix-qwen4b__mini__retry | original recorded bytes | 1 | yes | no | 0 | 1 | yes | no |
| author/roundOW/qwen3coder30b__envel | labelled current-fixture substitute | 0 | no | yes | 0 | 0 | no | yes |
| author/roundOW/qwen3coder30b__mini | labelled current-fixture substitute | 0 | no | yes | 1 | 0 | no | no |
| author/roundOW/qwen4b__mini | labelled current-fixture substitute | 1 | no | no | 0 | 1 | no | no |
| author/roundOW/qwen4b__mini__retry | labelled current-fixture substitute | 1 | no | no | 0 | 1 | no | no |
| author/round1/python | not rerun | unavailable | unknown or not applicable | unknown or not applicable | not applicable | unavailable | unknown or not applicable | unknown or not applicable |
| author/round1/javascript | not rerun | unavailable | unknown or not applicable | unknown or not applicable | not applicable | unavailable | unknown or not applicable | unknown or not applicable |
| author/round1/rust | not rerun | unavailable | unknown or not applicable | unknown or not applicable | not applicable | unavailable | unknown or not applicable | unknown or not applicable |
| author/round1/c | not rerun | unavailable | unknown or not applicable | unknown or not applicable | not applicable | unavailable | unknown or not applicable | unknown or not applicable |
| author/round2/python | labelled current-fixture substitute | 1 | yes | no | 2 | 1 | yes | no |
| author/round2/rust | labelled current-fixture substitute | 0 | yes | no | 2 | 0 | yes | no |
| author/round3/splat | not rerun | unavailable | unknown or not applicable | unknown or not applicable | not applicable | unavailable | unknown or not applicable | unknown or not applicable |
| author/roundXV/openai | labelled current-fixture substitute | 1 | no | no | 1 | 1 | no | no |
| author/roundXV/openai-gsplat | labelled current-fixture substitute | 1 | no | no | 0 | 1 | no | no |
| author/roundXV/moonshot | labelled current-fixture substitute | 2 | yes | no | 1 | 2 | yes | no |
| author/roundXV/moonshot-gsplat | labelled current-fixture substitute | 0 | yes | no | 0 | 0 | yes | no |
| author/roundSR/codex | Retained MSVC command on the current host | 0/0 | no | no | not applicable | 0/0 | no | no |
| author/roundSR/kimi | MSVC substitute for the original MinGW recipe | None/None | no | no | not applicable | None/None | no | no |
| author/roundHC/attempt1 | original recorded scanned page | not applicable | unknown or not applicable | unknown or not applicable | not applicable | not applicable | unknown or not applicable | unknown or not applicable |
| author/roundGF/hc-kimi | original recorded scanned page | not applicable | unknown or not applicable | unknown or not applicable | not applicable | not applicable | unknown or not applicable | unknown or not applicable |
| second/batch1/r1-t1 | original recorded bytes | 1 | yes | no | 1 | 1 | yes | no |
| second/batch1/r1-t2 | original recorded bytes | 1 | yes | no | 1 | 1 | yes | no |
| second/batch1/r1-t3 | original recorded bytes | 1 | yes | no | 1 | 1 | yes | no |
| second/batch1/env-t1 | original recorded bytes | 1 | yes | no | 0 | 1 | yes | no |
| second/batch2/xv-t1 | original recorded bytes | 1 | yes | no | 1 | 1 | yes | no |
| second/batch2/xv-t2 | original recorded bytes | 1 | yes | no | 1 | 1 | yes | no |
| second/batch2/xv-t3 | original recorded bytes | 1 | yes | no | 1 | 1 | yes | no |
| second/batch2/splat-t1 | original recorded bytes | 0 | yes | no | 0 | 0 | yes | no |
| second/batch2/splat-t2 | original recorded bytes | 1 | yes | no | 0 | 1 | yes | no |
| second/batch2/env-t2 | original recorded bytes | 1 | yes | no | 0 | 0 | yes | no |
| second/batch2/env-t3 | original recorded bytes | 1 | yes | no | 0 | 1 | yes | no |
| second/negative-control/werk-t1 | original recorded bytes | 1 | yes | no | 1 | 1 | yes | no |
| second/negative-control/werk-t2 | original recorded bytes | 1 | yes | no | 1 | 0 | yes | no |
| second/negative-control/werk-t3 | original recorded bytes | 1 | yes | no | 1 | 1 | yes | no |
| second/negative-control/fbx-t1 | original recorded bytes | 1 | no | unknown or not applicable | 1 | not applicable | unknown or not applicable | unknown or not applicable |
| second/negative-control/fbx-t2 | original recorded bytes | 1 | no | unknown or not applicable | 1 | not applicable | unknown or not applicable | unknown or not applicable |
| second/negative-control/fbx-t3 | original recorded bytes | 1 | no | unknown or not applicable | 0 | not applicable | unknown or not applicable | unknown or not applicable |
| second/negative-control/gltf-t1 | original recorded bytes | 0 | no | unknown or not applicable | 5 | not applicable | unknown or not applicable | unknown or not applicable |
| second/negative-control/gltf-t2 | original recorded bytes | 0 | no | unknown or not applicable | 2 | not applicable | unknown or not applicable | unknown or not applicable |
| second/negative-control/gltf-t3 | original recorded bytes | 0 | no | unknown or not applicable | 5 | not applicable | unknown or not applicable | unknown or not applicable |
| second/negative-control/usdz-t1 | original recorded bytes | 0 | no | unknown or not applicable | 0 | not applicable | unknown or not applicable | unknown or not applicable |
| second/negative-control/usdz-t2 | original recorded bytes | 0 | no | unknown or not applicable | 1 | not applicable | unknown or not applicable | unknown or not applicable |
| second/negative-control/usdz-t3 | original recorded bytes | 0 | no | unknown or not applicable | 0 | not applicable | unknown or not applicable | unknown or not applicable |
| second/august/mesh-image | not rerun | unavailable | unknown or not applicable | unknown or not applicable | not applicable | unavailable | unknown or not applicable | unknown or not applicable |

Confirmed false claims occur in three author programs. Two falsely claim whole-package integrity for both damage types.
The third falsely claims the changed primary sound was verified. Exact evidence and output hashes are in the ledger and in [damage-evidence.json](damage-evidence.json).
