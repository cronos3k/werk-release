# Release pins

Everything a pre-registration needs to name the exact bytes of this release.
Measured from the working tree of the commit below with
`sha256` over the whole file; sizes in bytes.

| | |
|---|---|
| pinned commit | `5a51fef` (branch `main`) |
| tree | `754250a7ce403cdc56cefd0701431169f89730fa` |
| `spec_sha256` of the release `spec/` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` |
| bootstrap loader `loaders/werk_read.py` | `f639dd417689e60bac2852bcc5e79bda5776c513407d419b3033ed31837c2794` (64 265 B) |

A later commit that leaves `spec/`, `loaders/`, `fixtures/`, `gauntlet/` and
`RELEASE-ASSETS.md` untouched carries the same bytes; check with
`python fixtures/record_fixtures.py --check` and `python tools/release_assets.py --check`.

## Fixtures (`fixtures/fixtures.json`)

| key | path | bytes | sha256 | spec_sha256 | in git |
|---|---|---:|---|---|---|
| `crate-v1` | `fixtures/crate-v1.werk` | 13 967 673 | `ef0430d7e24faf5e16141358ae9b15610e9dd4b8b1854dd78f9dd2265ebe5d45` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | no: release asset |
| `crate-v1-damaged` | `fixtures/crate-v1-damaged.werk` | 13 968 825 | `ecfbd1a587f9a5e9abe10abbd2074c80626ae7c5dcd6b8202994f7c6d82a63a3` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | no: release asset |
| `crate-tex-v1` | `fixtures/crate-tex-v1.werk` | 1 166 981 | `c9867dd70dbe85f052f60e705f79c80e5eca1448ff5c4fb9b8a925b31f4d6adc` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | yes |
| `ista-varun-v1` | `fixtures/ista-varun-v1.werk` | 10 883 368 | `44cfd0e2c702b34874b3c1e15d1edd5609c358c7b2fff8c92db60edc44b81239` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | no: release asset |
| `humanoid-retarget-v1` | `fixtures/humanoid-retarget-v1.werk` | 1 796 361 | `4cada7ecf7789fb00ab2e56580f66648bfe813fa5fffa291a9631eae017aa28d` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | yes |
| `gsplat-v1` | `fixtures/gsplat-v1.werk` | 30 521 757 | `2320f775e9f1d7eefdb66a23ef8e6d002b52c3d24074cf85990edc24da7fdb11` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | no: release asset |
| `crate-synthetic` | `tests/fixtures/crate.werk` | 879 740 | `790c5c2514802b3ed04e511b82965b1107f290fc0e8633774f6a7d6a1a2f4d2b` | `58324e2d409f05e4c7d0b5980c93db19dcc400211bb8d0e13df25560e1a3445d` | yes |
| `mini-v1` | `gauntlet/roundOW/mini-v1.werk` | 1 136 212 | `5d73533124153c8d2406d6d5f0858a3918cbbe7097f24000a1097fffcb45fa97` | `611191fec35b8839e511b8b4075f818330c93ca035485b894247ec54a9fe12ad` | yes |
| `mini-v1-historical` | `gauntlet/roundOW/historical/mini-v1-f7bdcc85.werk` | 960 061 | `f7bdcc853009504b1d31b2934a7a8294cbf0e6f227c95f7de1e81af0947e9837` | `5ada229078738ce45d1b65e1a9ba5eb2df0a10ea261254da21c46df73831d4ad` | yes |
| `crate-cc0-lean-v1` | `fixtures/crate-cc0-lean-v1.werk` | 1 545 537 | `8839a16d69cc03729fac7673b3b05bf23f9504a0987f00d2ee71ee7a2faabb8e` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | yes |
| `crate-cc0-lean-v1-damaged` | `fixtures/crate-cc0-lean-v1-damaged.werk` | 1 546 740 | `7e81f6553e02d14644e6eea0735ac027b25148b867969d4e363b9b98f7fee92b` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | yes |
| `crate-cc0-full-v1` | `fixtures/crate-cc0-full-v1.werk` | 1 606 343 | `394a1001aa4accb90c5ebbe76ad8f91648475404fd59313e290489bec0e1b40b` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | yes |
| `crate-cc0-full-v1-damaged` | `fixtures/crate-cc0-full-v1-damaged.werk` | 1 607 546 | `cfd83bc03b07edc75d17bb0a8519e57d37b77b344d4e36618561b863c1bd85ac` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | yes |
| `image-cc0-v1` | `fixtures/image-cc0-v1.werk` | 5 805 849 | `015fc1fdee9506fb9b0a968673c6a41c2e528d315f71b803ca0c288e82a1efd6` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | no: release asset |
| `image-cc0-v1-damaged` | `fixtures/image-cc0-v1-damaged.werk` | 5 806 898 | `71a60282cd7b382baba229ba9f85e7a0ffc09286dd6c7b5a12e0835c212e874a` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | no: release asset |
| `gsplat-cc0-v1` | `fixtures/gsplat-cc0-v1.werk` | 1 782 586 | `58dad3cc787f89375278f2d671ec78361c5846f736d39852747587ce56ebb3bf` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | yes |
| `gsplat-cc0-v1-damaged` | `fixtures/gsplat-cc0-v1-damaged.werk` | 1 783 636 | `e2d739efda48753f52cd00b0e45a18204a27628ba69c29157a9501757b414912` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | yes |
| `crate-cc0-lean-v1-deflated` | `fixtures/crate-cc0-lean-v1-deflated.werk` | 648 535 | `2ba181bed2dbbd2f45f2481d19ecc6930f43200627c371627eafb822a5008af8` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | yes |

`crate-synthetic` and `mini-v1` carry a trimmed `spec/` tree (byte-identical
documents, fewer of them), so their `spec_sha256` hashes that subset.
`mini-v1-historical` is the earlier `mini-v1.werk` every recorded trial ran on
(earlier spec revision, three dangling edges); it is kept, never rebuilt.

## Release assets (files kept out of git, `RELEASE-ASSETS.md`)

| path | bytes | sha256 |
|---|---:|---|
| `fixtures/crate-v1.werk` | 13 967 673 | `ef0430d7e24faf5e16141358ae9b15610e9dd4b8b1854dd78f9dd2265ebe5d45` |
| `fixtures/crate-v1-damaged.werk` | 13 968 825 | `ecfbd1a587f9a5e9abe10abbd2074c80626ae7c5dcd6b8202994f7c6d82a63a3` |
| `fixtures/ista-varun-v1.werk` | 10 883 368 | `44cfd0e2c702b34874b3c1e15d1edd5609c358c7b2fff8c92db60edc44b81239` |
| `fixtures/gsplat-v1.werk` | 30 521 757 | `2320f775e9f1d7eefdb66a23ef8e6d002b52c3d24074cf85990edc24da7fdb11` |
| `fixtures/image-cc0-v1.werk` | 5 805 849 | `015fc1fdee9506fb9b0a968673c6a41c2e528d315f71b803ca0c288e82a1efd6` |
| `fixtures/image-cc0-v1-damaged.werk` | 5 806 898 | `71a60282cd7b382baba229ba9f85e7a0ffc09286dd6c7b5a12e0835c212e874a` |
| `gauntlet/roundSR/selfrun-v1.werk` | 62 525 273 | `1f8e1270b89371a5acc80aa854db3572631f7dac9a053fd045da0af112d51f17` |
| `gauntlet/roundHC/pages/scanned/page-01.jpg` | 2 234 907 | `a0631045c383e9f897446394bfeee2898bec48ee1e35bec5171f14145c726b54` |
| `gauntlet/roundHC/pages/scanned/page-02.jpg` | 2 214 471 | `fef9d5ed0b2894a1f39c6688d0f37bf9a3c67cc97292b58323f635dc45bf4c14` |
| `gauntlet/roundHC/pages/scanned/page-03.jpg` | 2 434 135 | `e25dad576258f466615a0b64bd5844de55c42f8acfa79cff40806cd082727560` |
| `evidence/second-lab/roundNC-binaries.tar.gz` | 2 328 731 | `71847a908a7ef68859e57e34381f132b183778e19927bda9b4e962a9c49cd036` |

## External and historical files (not hosted with this release)

| name | bytes | sha256 | note |
|---|---:|---|---|
| second-lab-reruns-2026-10-12 | not measured here | `ec069bba92ac9196f35465d16f2f1f91a6fdbd36abfb40cc5f70bd5462e99889` | author-lab asset, not downloaded or verified for this release |
| crate-v1.werk (historical) | 13 684 477 | `0a7a7341d5d508c75925a8c3be0b6c8ccdcced607d9bdd0b26f04e264f029106` | the bytes the second-lab trials ran on |
| gsplat-v1.werk (historical) | 30 235 611 | `ede0aee6cc5659af741059b747dc3f3459db220234e7ffb95c4437c02337090a` | the bytes the second-lab trials ran on |

## Libraries (`libs/`) and vendored copies

| file | bytes | sha256 |
|---|---:|---|
| `libs/python/werk_single.py` | 666 312 | `ff3de49babadffa942469a8d6103cac0ecd13804b847b75cabe70acb3a680600` |
| `libs/js/dist/werk.js` | 1 939 406 | `fdee63c45e71433196d96095d9acf9f6d34adc790dd109e2529ea405cf8e282a` |
| `libs/js/dist/werk.jsx` | 1 945 026 | `14c0afffb805f6d494f7bcbbb4cf3e9910095e0513bde5462f3a58254f33198d` |
| `libs/bundle/bundle.json` | 18 175 | `a8af4de3d4e5edd61d4a05a4035b7bd79a668869f76169d173996e6e786164c8` |

Bundle `source_rev`: `509ebf83be6dd998a255cceca234ceca0b8ac025`.

## Checks run on this commit (Windows 10 workstation, 2026-11-17)

| check | result |
|---|---|
| `tests/run_gate.py`, `_a`, `_3b`, `_6`, `_9`, `_12` | 11, 14, 19, 34, 17, 19 PASS; 0 FAIL |
| `plugins/blender/test_gate.py` (Blender 4.2.1) | 20 PASS, 0 FAIL |
| `store/tests` (pytest) | 59 passed, 0 failed |
| `tests/run_gate_cc0_public.py`, `_cc0_image`, `_cc0_gsplat` | 20, 11, 11 PASS; 0 FAIL |
| `tests/fixture_pin.py` | 18 of 18 match |
| `tests/run_gate_artcraft.py`, `_container`, `_magic`, `_reference`, `_writing` | 90, 25, 22, 19, 26 PASS; 0 FAIL |
| `cargo test --release` in `core/` | 90 passed, 0 failed |
| `libs/tests/cross_matrix.py --fixtures fixtures` | 23 cases (new: `unsafe-path-multiversion`, `unsafe-path-payload-file`, `unsafe-path-old-version`) + 15 fixtures, 0 failures |
| `libs/tests/damage_agree.py` | 1 532 variants: libs 1 532, werkc 1 524, ref-py 1 532, ref-c 1 531, ref-rs 1 531 agree; 0 crashes (unchanged; the known gaps of `libs/README.md`) |
| `libs/tests/test_vectors.py`, `test_api.py` (3.12, 3.8), `js/tests/api_smoke.js`, `es3_check.js`, float spelling (`cargo test --bin werkc`) | 20, 27, 27, 15 PASS, 0 FAIL; ES3 0 problems; 2 passed (run at `93b2f88`: same libraries, loaders and fixtures) |
| plug-in re-gates on the re-vendored library (`git archive c5276a1`, same libraries and fixtures; Unreal re-run on `5a51fef`, see its `GATE-RESULTS.md`) | Unreal 5.8.2 147 PASS / 0 FAIL / 4 NOT-RUN; Office 2016 60 / 0; Blender `gate_release.py` 98 / 0; GIMP 3.2.4 34 / 0 / 3 NOTE |

The repository gates ran on the working tree at `ea58f7a` (this commit's
fixtures and libraries; `a00312d` added the refreshed test-result files and
the README count, `5a51fef` the one-line GCC spelling fix in the Unreal
plug-in's engine-free core, which the Windows gates also compile). Not re-run on the re-vendored library:
Photoshop, Illustrator, After Effects (Adobe re-gates wait for the final
freeze). The three-machine runs of this release are recorded in the release
evidence.
