# Release pins

Everything a pre-registration needs to name the exact bytes of this release.
Measured from the working tree of the commit below with
`sha256` over the whole file; sizes in bytes.

| | |
|---|---|
| pinned commit | `606b7b4895eca1560df6f560ca0cba03ca9a384f` (branch `main`) |
| tree | `8cb5322c5069f6b9b2085fd35acf7a2aa3ca1903` |
| `spec_sha256` of the release `spec/` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` |
| bootstrap loader `loaders/werk_read.py` | `d8c633e4af1fa35f57c45c5d0ab0ecf197263d1bb6c51f12f1b03dc036de63f7` (63 944 B) |

A later commit that leaves `spec/`, `loaders/`, `fixtures/`, `gauntlet/` and
`RELEASE-ASSETS.md` untouched carries the same bytes; check with
`python fixtures/record_fixtures.py --check` and `python tools/release_assets.py --check`.

## Fixtures (`fixtures/fixtures.json`)

| key | path | bytes | sha256 | spec_sha256 | in git |
|---|---|---:|---|---|---|
| `crate-v1` | `fixtures/crate-v1.werk` | 13 967 352 | `661b0ae30cd128513091990eb8a11e9783cbce962f6049658f126dbee04f277e` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | no: release asset |
| `crate-v1-damaged` | `fixtures/crate-v1-damaged.werk` | 13 968 504 | `45a60598297c2e8ac0380c64408a53c3928affaf997f12dae29c261ac1242a1a` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | no: release asset |
| `crate-tex-v1` | `fixtures/crate-tex-v1.werk` | 1 166 660 | `84da0ec25c0ef64afe8ce18050f4913c79481333ffd3c808774aca28f16d6470` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | yes |
| `ista-varun-v1` | `fixtures/ista-varun-v1.werk` | 10 883 047 | `8dd4d655ead6ea9c644960e56d5666b08d7c31bc50565d107076a7a14f7c4afd` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | no: release asset |
| `humanoid-retarget-v1` | `fixtures/humanoid-retarget-v1.werk` | 1 796 040 | `bff166166918b15fe81bfd8351feb60f877d734cf495aff75ee786277ae09941` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | yes |
| `gsplat-v1` | `fixtures/gsplat-v1.werk` | 30 521 436 | `9214bb4bdb1fbcd6136676d1b75334b77b0620f5e879fa843c70bf160beb5c81` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | no: release asset |
| `crate-synthetic` | `tests/fixtures/crate.werk` | 879 419 | `f427abb9dc46a9f75391724d070c55a9c7e83e16657bb531b0ae0c85d9de57fa` | `58324e2d409f05e4c7d0b5980c93db19dcc400211bb8d0e13df25560e1a3445d` | yes |
| `mini-v1` | `gauntlet/roundOW/mini-v1.werk` | 1 135 891 | `510fae4c9e8b1af75e31c9a19eab279bbe785127de2240551efa11be59b4afe8` | `611191fec35b8839e511b8b4075f818330c93ca035485b894247ec54a9fe12ad` | yes |
| `mini-v1-historical` | `gauntlet/roundOW/historical/mini-v1-f7bdcc85.werk` | 960 061 | `f7bdcc853009504b1d31b2934a7a8294cbf0e6f227c95f7de1e81af0947e9837` | `5ada229078738ce45d1b65e1a9ba5eb2df0a10ea261254da21c46df73831d4ad` | yes |
| `crate-cc0-lean-v1` | `fixtures/crate-cc0-lean-v1.werk` | 1 545 216 | `b22af08a18e84686130a350812ecfc83be82b87039a57a68a1552c9cc4fa44aa` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | yes |
| `crate-cc0-lean-v1-damaged` | `fixtures/crate-cc0-lean-v1-damaged.werk` | 1 546 419 | `473f6cc0654dd4484d8e04f682836264acac6853b33baef658b9e45da499f2ac` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | yes |
| `crate-cc0-full-v1` | `fixtures/crate-cc0-full-v1.werk` | 1 606 022 | `376cc517f3814bd620f9495c0537265e8f3cb0d412683e92f5476b05d5072b49` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | yes |
| `crate-cc0-full-v1-damaged` | `fixtures/crate-cc0-full-v1-damaged.werk` | 1 607 225 | `0625b7a38858650b0ec0e61d1bb6407ab600a86b69183b465bae6a307d700640` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | yes |
| `image-cc0-v1` | `fixtures/image-cc0-v1.werk` | 5 805 528 | `b8222720e46aa183d241e70c65b87e98acc25fbbfad5d435f3125f2294db1895` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | no: release asset |
| `image-cc0-v1-damaged` | `fixtures/image-cc0-v1-damaged.werk` | 5 806 577 | `17fce14223e2578e720f3a38938798d4b470eace12bad433ed8fa3229590caef` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | no: release asset |
| `gsplat-cc0-v1` | `fixtures/gsplat-cc0-v1.werk` | 1 782 265 | `8624695616ad55a0e3cb404d5c87da87c97e2b1e9264f2d7e1ea665e22f0d84a` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | yes |
| `gsplat-cc0-v1-damaged` | `fixtures/gsplat-cc0-v1-damaged.werk` | 1 783 315 | `10e6f06a9640248766704f431e587485e93fd05cd8a049dd4340455631c5ba48` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | yes |
| `crate-cc0-lean-v1-deflated` | `fixtures/crate-cc0-lean-v1-deflated.werk` | 648 450 | `debe6dcb3e20d626eeaace177ecf43199865637b2088ec59e65c08c670e2d943` | `55882f4b05e7fee1c1113662499dc5c62297020c23aa5d271c42ccb8791d40b3` | yes |

`crate-synthetic` and `mini-v1` carry a trimmed `spec/` tree (byte-identical
documents, fewer of them), so their `spec_sha256` hashes that subset.
`mini-v1-historical` is the earlier `mini-v1.werk` every recorded trial ran on
(earlier spec revision, three dangling edges); it is kept, never rebuilt.

## Release assets (files kept out of git, `RELEASE-ASSETS.md`)

| path | bytes | sha256 |
|---|---:|---|
| `fixtures/crate-v1.werk` | 13 967 352 | `661b0ae30cd128513091990eb8a11e9783cbce962f6049658f126dbee04f277e` |
| `fixtures/crate-v1-damaged.werk` | 13 968 504 | `45a60598297c2e8ac0380c64408a53c3928affaf997f12dae29c261ac1242a1a` |
| `fixtures/ista-varun-v1.werk` | 10 883 047 | `8dd4d655ead6ea9c644960e56d5666b08d7c31bc50565d107076a7a14f7c4afd` |
| `fixtures/gsplat-v1.werk` | 30 521 436 | `9214bb4bdb1fbcd6136676d1b75334b77b0620f5e879fa843c70bf160beb5c81` |
| `fixtures/image-cc0-v1.werk` | 5 805 528 | `b8222720e46aa183d241e70c65b87e98acc25fbbfad5d435f3125f2294db1895` |
| `fixtures/image-cc0-v1-damaged.werk` | 5 806 577 | `17fce14223e2578e720f3a38938798d4b470eace12bad433ed8fa3229590caef` |
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
| `libs/python/werk_single.py` | 664 802 | `d7cc89cc6cd6b636a52bede42c7c20c3a6703fd2c4d981ec3a64225247e7649a` |
| `libs/js/dist/werk.js` | 1 937 737 | `ebf195d80a8df7aa57ce8046bbf6a2cb8ee7b245ed84a3b46f8e0bd9c5626899` |
| `libs/js/dist/werk.jsx` | 1 943 357 | `6a4fbb10c033991aef319b7497506cd6dad3bb64ad4b8018fdd445400a26d23f` |
| `libs/bundle/bundle.json` | 18 175 | `757ebe565a0138ad1f09e8ee8035a66b9b36b00466abeacf605d31cbca3be6ac` |

Bundle `source_rev`: `bc2352940fb120c09a6da063cc8723357b5d89fc`.
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
| `libs/tests/cross_matrix.py --fixtures fixtures` | 20 cases + 15 fixtures, 0 failures |
| `libs/tests/damage_agree.py` | 1 532 variants: libs 1 532, werkc 1 524, ref-py 1 532, ref-c 1 531, ref-rs 1 531 agree; 0 crashes (the known gaps of `libs/README.md`) |
| `libs/tests/test_vectors.py`, `test_api.py` (3.12, 3.8), `js/tests/api_smoke.js`, `es3_check.js` | 20, 27, 27, 15 PASS, 0 FAIL; ES3 0 problems |
| `plugins/blender/gate_release.py` (re-vendored library) | 98 PASS, 0 FAIL |
| `plugins/gimp/gate.py` (GIMP 3.2.4, re-vendored library) | 34 PASS, 0 FAIL, 3 NOTE |
| `evidence/second-lab/trials/check_trials.py --fixtures <historical>` | 11 of 11 trials reproduce their output bytes |

Not re-run on the re-vendored library (their `GATE-RESULTS.md` record runs
on `werk_single.py` `08242050…` / `werk.jsx` `b38b1990…`): Unreal 5.8.2,
Office 2016, Photoshop 2020, Illustrator 2020, After Effects 2020. Not run at
all here: Linux and the other lab machines, `rubric_check.py` (needs the
external re-runs asset).
