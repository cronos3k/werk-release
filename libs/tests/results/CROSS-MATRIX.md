# werk libs cross-matrix

machine `<lab-workstation>` | Windows-10-10.0.19045-SP0 | python 3.12.8 | node v24.10.0 | started 2026-11-17T08:19:24Z

Writers: py, py1, js, es3, rust. Readers: py, js, es3, werkc, ref-py, ref-c, ref-rs.

## Writers x cases (byte identity) and readers x outputs (verdict + extraction)

| case | form | byte-identical (py/py1/js/es3/rust) | sha256 | full verdict (exit / signature / dead) | py | js | es3 | werkc | ref-py | ref-c | ref-rs |
|---|---|---|---|---|---|---|---|---|---|---|---|
| image-min | zip | **yes** (YYYYY) | `f6b652b253e3f877` | 0 / absent / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| image-full-signed | zip | **yes** (YYYYY) | `4d23494804c0cb8c` | 0 / signed-and-valid / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| image-full-dir | dir | **yes** (YYYYY) | `adfd106fdf8e7c77` | 0 / signed-and-valid / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| mesh-min | zip | **yes** (YYYYY) | `f83ac6006e2610cd` | 0 / absent / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| mesh-full-signed | zip | **yes** (YYYYY) | `7f1855536a17de17` | 0 / signed-and-valid / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| many-nodes | zip | **yes** (YYYYY) | `341b474987c7269c` | 0 / absent / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| empty-payload | zip | **yes** (YYYYY) | `370ccdad3d654f2b` | 0 / absent / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| spec-files | zip | **yes** (YYYYY) | `7bdf57df898776fe` | 0 / absent / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| profile-extras | zip | **yes** (YYYYY) | `22888fe659416303` | 0 / absent / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| large-file-dir | dir | **yes** (YYYYY) | `23d047b0ec0b3a9c` | 0 / absent / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| multi-version | zip | **yes** (YYYYY) | `62d2e09a94504c9d` | 0 / absent / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| signed-append | zip | **yes** (YYYYY) | `c9e047cfb5428736` | 0 / signed-and-valid / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| co-signed | zip | **yes** (YYYYY) | `daecd004c1c0bd3f` | 0 / signed-and-valid / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| tampered-payload | zip | **yes** (YYYYY) | `4a4a9784ae2e8c96` | 1 / signed-and-valid / image-thumb | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| tampered-signature | zip | **yes** (YYYYY) | `227f5e117e953625` | 1 / present-and-invalid / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| tampered-manifest | zip | **yes** (YYYYY) | `f35c8304f3043e88` | 1 / present-and-invalid / none | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| duplicate-entry | zip | **yes** (YYYYY) | `c5d7020b70343cf6` | refused (2) | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| truncated | zip | **yes** (YYYYY) | `91e1a0668c4ac4f6` | refused (2) | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| unsafe-path | zip | **yes** (YYYYY) | `79d40bad76740b0b` | 1 / absent / readme | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| requires-missing | zip | **yes** (YYYYY) | `cd8f2bd04970fde3` | 1 / absent / readme | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |

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

