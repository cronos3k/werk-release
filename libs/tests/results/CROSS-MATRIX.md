# werk libs cross-matrix

machine `<lab-workstation>` | Windows-10-10.0.19045-SP0 | python 3.12.8 | node v24.10.0 | started 2026-11-17T10:00:15Z

Writers: py, py1, js, es3, rust. Readers: py, js, es3, werkc, ref-py, ref-c, ref-rs.

## Writers x cases (byte identity) and readers x outputs (verdict + extraction)

| case | form | byte-identical (py/py1/js/es3/rust) | sha256 | full verdict (exit / signature / dead) | py | js | es3 | werkc | ref-py | ref-c | ref-rs |
|---|---|---|---|---|---|---|---|---|---|---|---|
| image-min | zip | **yes** (YYYYY) | `a555e4200f27e0aa` | 0 / absent / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| image-full-signed | zip | **yes** (YYYYY) | `833a18d66ecd94f3` | 0 / signed-and-valid / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| image-full-dir | dir | **yes** (YYYYY) | `af5aa2337cbf2a1f` | 0 / signed-and-valid / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| mesh-min | zip | **yes** (YYYYY) | `4e1f49804e4699c3` | 0 / absent / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| mesh-full-signed | zip | **yes** (YYYYY) | `dceec5e1eef52d16` | 0 / signed-and-valid / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| many-nodes | zip | **yes** (YYYYY) | `c65ff8f3300b5041` | 0 / absent / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| empty-payload | zip | **yes** (YYYYY) | `7e91a991fbb975da` | 0 / absent / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| spec-files | zip | **yes** (YYYYY) | `fd29f4c4d33c13cf` | 0 / absent / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| profile-extras | zip | **yes** (YYYYY) | `fe0847a2a4a00aef` | 0 / absent / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| large-file-dir | dir | **yes** (YYYYY) | `2ef7a9892e8a4240` | 0 / absent / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| multi-version | zip | **yes** (YYYYY) | `a79d2ecea5d796a6` | 0 / absent / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| signed-append | zip | **yes** (YYYYY) | `4eb40e2fe49563a7` | 0 / signed-and-valid / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| co-signed | zip | **yes** (YYYYY) | `49b41b50923d08bd` | 0 / signed-and-valid / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| tampered-payload | zip | **yes** (YYYYY) | `651d6d03fb0afffc` | 1 / signed-and-valid / image-thumb | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| tampered-signature | zip | **yes** (YYYYY) | `c081c6d95c07f7b2` | 1 / present-and-invalid / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| tampered-manifest | zip | **yes** (YYYYY) | `b1abc5aa9776a1fa` | 1 / present-and-invalid / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| duplicate-entry | zip | **yes** (YYYYY) | `211472706a29c996` | refused (2) | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| truncated | zip | **yes** (YYYYY) | `82998a4f8af573a1` | refused (2) | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| unsafe-path | zip | **yes** (YYYYY) | `246a33cbca1839b0` | 1 / absent / readme | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| unsafe-path-multiversion | zip | **yes** (YYYYY) | `edb256128cb6025a` | 1 / absent / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| unsafe-path-payload-file | zip | **yes** (YYYYY) | `8dc893891a35fcef` | 1 / absent / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| unsafe-path-old-version | zip | **yes** (YYYYY) | `198ed25dad56705a` | 1 / absent / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| requires-missing | zip | **yes** (YYYYY) | `fc8b740609078b5b` | 1 / absent / readme | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |

A reader cell is `outputs read with an agreeing verdict and byte-exact extraction / outputs`.

## Fixtures (reader-only)

| fixture | agree | py verdict (exit / signature / dead) | py | js | es3 | werkc | ref-py | ref-c | ref-rs |
|---|---|---|---|---|---|---|---|---|---|
| crate-cc0-full-v1-damaged.werk | yes | 1 / signed-and-valid / audio-cc0-click | 1/signed-/1 | 1/signed-/1 | 1/signed-/1 | 1/signed-/1 | 1/unverif/1 | 1/unverif/1 | 1/unverif/1 |
| crate-cc0-full-v1.werk | yes | 0 / signed-and-valid / none | 0/signed-/0 | 0/signed-/0 | 0/signed-/0 | 0/signed-/0 | 0/unverif/0 | 0/unverif/0 | 0/unverif/0 |
| crate-cc0-lean-v1-damaged.werk | yes | 1 / signed-and-valid / disclosure-cc0 | 1/signed-/1 | 1/signed-/1 | 1/signed-/1 | 1/signed-/1 | 1/unverif/1 | 1/unverif/1 | 1/unverif/1 |
| crate-cc0-lean-v1-deflated.werk | yes | 0 / signed-and-valid / none | 0/signed-/0 | 0/signed-/0 | 0/signed-/0 | 0/signed-/0 | 0/unverif/0 | 0/unverif/0 | 0/unverif/0 |
| crate-cc0-lean-v1.werk | yes | 0 / signed-and-valid / none | 0/signed-/0 | 0/signed-/0 | 0/signed-/0 | 0/signed-/0 | 0/unverif/0 | 0/unverif/0 | 0/unverif/0 |
| crate-tex-v1.werk | yes | 0 / absent / none | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 | 0/absent/0 |
| crate-v1-damaged.werk | yes | 1 / signed-and-valid / audio-crate-impact-hard-surface | 1/signed-/1 | 1/signed-/1 | 1/signed-/1 | 1/signed-/1 | 1/unverif/1 | 1/unverif/1 | 1/unverif/1 |
| crate-v1.werk | yes | 0 / signed-and-valid / none | 0/signed-/0 | 0/signed-/0 | 0/signed-/0 | 0/signed-/0 | 0/unverif/0 | 0/unverif/0 | 0/unverif/0 |
| gsplat-cc0-v1-damaged.werk | yes | 1 / signed-and-valid / points-dc | 1/signed-/1 | 1/signed-/1 | 1/signed-/1 | 1/signed-/1 | 1/unverif/1 | 1/unverif/1 | 1/unverif/1 |
| gsplat-cc0-v1.werk | yes | 0 / signed-and-valid / none | 0/signed-/0 | 0/signed-/0 | 0/signed-/0 | 0/signed-/0 | 0/unverif/0 | 0/unverif/0 | 0/unverif/0 |
| gsplat-v1.werk | yes | 0 / signed-and-valid / none | 0/signed-/0 | 0/signed-/0 | 0/signed-/0 | 0/signed-/0 | 0/unverif/0 | 0/unverif/0 | 0/unverif/0 |
| humanoid-retarget-v1.werk | yes | 0 / signed-and-valid / none | 0/signed-/0 | 0/signed-/0 | 0/signed-/0 | 0/signed-/0 | 0/unverif/0 | 0/unverif/0 | 0/unverif/0 |
| image-cc0-v1-damaged.werk | yes | 1 / signed-and-valid / disclosure | 1/signed-/1 | 1/signed-/1 | 1/signed-/1 | 1/signed-/1 | 1/unverif/1 | 1/unverif/1 | 1/unverif/1 |
| image-cc0-v1.werk | yes | 0 / signed-and-valid / none | 0/signed-/0 | 0/signed-/0 | 0/signed-/0 | 0/signed-/0 | 0/unverif/0 | 0/unverif/0 | 0/unverif/0 |
| ista-varun-v1.werk | yes | 0 / signed-and-valid / none | 0/signed-/0 | 0/signed-/0 | 0/signed-/0 | 0/signed-/0 | 0/unverif/0 | 0/unverif/0 | 0/unverif/0 |

Fixture cells: `exit/signature/dead-count` per reader; bootstrap loaders run with `--strict`.

## Failures: 0

