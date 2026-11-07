# Container contents and node graph

Entity: **Wooden crate** — A slatted wooden shipping crate with a complete sound world: twenty generated effects and ambiences, every take and every gate score kept. Conformance fixture #1, built from a real splat-foley run - the geometry, the views, the segment crops and every WAV are that run's actual output. Signed with a publicly derived DEV key that proves the chain works and nothing about authorship.

Profile: `3d-entity/1`. Archive entries: 174.

Meanings are the active versions’ own notes. `requires` is a hard dependency; `enhances` adds a feature without making its target mandatory.

Primary mesh node: `geom-game`. Primary sound node: `audio-crate-impact-hard-surface`.

## Nodes

### `geom-source` — `core.geom.source`

Active version 1. Meaning: The mesh exactly as the splat-foley run produced it: positions, u8 vertex colours, no normals. Kept verbatim because it is the anchor every derivation is checked against, and a rewritten source is not a source.

Files:

- `geometry/source.glb` — 10192 bytes; sha256 `e95288c4ca1b5e0742f496a6e03b02c397fc8c431191101886d8ac2b74ff251f`

Edges:

- None.

### `geom-game` — `core.geom.game`

Active version 1. Meaning: Runtime mesh: area-weighted vertex normals computed and vertex colours converted from sRGB u8 to linear f32, because SPEC 3.10 requires NORMAL and requires COLOR_0 to be linear.

Files:

- `geometry/game.glb` — 16736 bytes; sha256 `eee8b3cbc87703fc945555efec8fdcb0fb133f6c94cf75c8643b57189c4ef2ce`

Edges:

- `enhances` (derived-from) → `geom-source`

### `material-wood` — `core.material`

Active version 1. Meaning: Authored PBR parameters for the crate's only material.

Files:

- `materials/wood.json` — 525 bytes; sha256 `c66b9e725769fd818505022a916110a81c0a7449a789061c366f6b58f145ba61`

Edges:

- `enhances` (shades) → `geom-game`

### `bounds` — `core.phys.bounds`

Active version 1. Meaning: Measured bounds for culling, placement and LOD selection maths.

Files:

- `physics/bounds.json` — 654 bytes; sha256 `866eb5c8c01ea7121bca325d3bd283ddf47fbba6a43cb39cd49edbbadfde6c82`

Edges:

- `requires` (bounds-of) → `geom-game`

### `evidence-views` — `x.splat-foley.views`

Active version 1. Meaning: Six orbit views rendered from the source mesh. They are the pixels the vision model actually saw, kept so the inferred description can be audited rather than trusted.

Files:

- `x/splat-foley/views/view_00.png` — 38511 bytes; sha256 `ccd2293e1fb7d13b1f074a5d3e787a2917710bea7eddfe9c0aaacbdbe6ae2eac`; view
- `x/splat-foley/views/view_01.png` — 17858 bytes; sha256 `3ce20d6f682bfb236db605a8383329d8d5f06d88cb618574061786c47756aa3b`; view
- `x/splat-foley/views/view_02.png` — 43078 bytes; sha256 `f963589129dc2ea2ea233e6ac5195bd1e449b409df035ba26ed4d9a09f545f22`; view
- `x/splat-foley/views/view_03.png` — 37718 bytes; sha256 `90a665a82fcbbf14c0c1aed40d13b64d68ef7d02e9db1c67143e2eeed74dcd84`; view
- `x/splat-foley/views/view_04.png` — 18703 bytes; sha256 `fc45c3563e9194260762ada9aa1279f3181e5a5344d4d38e7752cbd35bbdbd7d`; view
- `x/splat-foley/views/view_05.png` — 42934 bytes; sha256 `3a9c35c669218c5d33adc4d1dc1bdb3c21fe33ef8fc6af299c1e9216a20f5c65`; view

Edges:

- `enhances` (rendered-from) → `geom-source`

### `evidence-segments` — `x.splat-foley.segments`

Active version 1. Meaning: SAM segment crops: the sub-object regions the description and the sound plan were derived from.

Files:

- `x/splat-foley/segments/seg_00.png` — 37183 bytes; sha256 `395fdb67b623688e62f8abf3378ea04cf142716074a506b30d129d61be1553d0`; crop
- `x/splat-foley/segments/seg_01.png` — 2198 bytes; sha256 `0a622401f800ff4456ce1d195b8161614902dc7830e19b60fedaf1f5ed44c4a1`; crop
- `x/splat-foley/segments/seg_02.png` — 40526 bytes; sha256 `51f471e89801bcdb4377359c598f9c921c429c972a56ffef87efc37b38df54b9`; crop
- `x/splat-foley/segments/seg_03.png` — 2390 bytes; sha256 `9b51eabe5a644b82e5034605b70480bee62d581919e0eb7ec2b63ef9882bc68a`; crop
- `x/splat-foley/segments/seg_04.png` — 2493 bytes; sha256 `95a6ac17de0b6d81b5f077b573a3b5e5d9cce3b297f8d90b076442ad7fe71d34`; crop
- `x/splat-foley/segments/seg_05.png` — 1912 bytes; sha256 `bcfad8cfcb1ee39f79b4ac03de8b1d6763a5701255c8b5b997b7f23db2c9ba04`; crop
- `x/splat-foley/segments/seg_06.png` — 1992 bytes; sha256 `a52c756de7888f3e5051a92aaabefb1dd3aa0727a98aaa246779825e58b60247`; crop
- `x/splat-foley/segments/seg_07.png` — 2959 bytes; sha256 `aa1bc9b8b37aa7950364a867b95d205944d5d7384e7a758fc718b1c781c5b412`; crop
- `x/splat-foley/segments/seg_08.png` — 17851 bytes; sha256 `f5efd93a38a1a14718fa133b62d734c9446ddfb6db4045abf2d2c1a0b6fc4c7a`; crop
- `x/splat-foley/segments/seg_09.png` — 2683 bytes; sha256 `c672e0ccd43223102414edca6e0b28e0edcf2e9b76df91560d4ced09e84b836e`; crop

Edges:

- `requires` (cropped-from) → `evidence-views`

### `audio-package` — `core.audio.package`

Active version 1. Meaning: The sound world index: what was described, what was planned, which takes exist and which gate scores they earned - including the ones that were rolled back.

Files:

- `audio/package.json` — 44158 bytes; sha256 `2f51229f5cde2ecebd04ebec700bb9820407a05a4fcaded4a0b777e430d75e09`

Edges:

- `enhances` (described-from) → `evidence-views`
- `enhances` (sounds-for) → `geom-game`

### `audio-crate-dragged-rough-concrete` — `core.audio.effect`

Active version 1. Meaning: Sound for 'wooden crate': dragged across rough concrete. Best take plus every variation and the pre-refinement raw, so an A/B is possible from the file alone.

Files:

- `audio/sfx/crate-dragged-rough-concrete.json` — 2028 bytes; sha256 `e9d3e07beed14e570d1f43fb129b20cc2a749da56fbbfebbfd7cb3735fd48216`; descriptor, application/json
- `audio/sfx/crate-dragged-rough-concrete.wav` — 192044 bytes; sha256 `b8f7b1ab003fb5b3274581fd52ad80ee298a4b6cb7585c6fff0235b709f71de5`; best, audio/wav
- `audio/sfx/crate-dragged-rough-concrete.var2.wav` — 192044 bytes; sha256 `510ffc5d7e2dddcfab43a5dc70ecaedabf195516af295c7bbec899f570fea17f`; variation, audio/wav
- `audio/sfx/crate-dragged-rough-concrete.var3.wav` — 192044 bytes; sha256 `9b608ac5297b97a8b4a82a005d0fa5ca78d989f5a58468a91c26aea9cb3ecdde`; variation, audio/wav

Edges:

- `enhances` (sounds-for) → `audio-package`

### `audio-crate-impact-hard-surface` — `core.audio.effect`

Active version 1. Meaning: Sound for 'wooden crate': hit by heavy object. Best take plus every variation and the pre-refinement raw, so an A/B is possible from the file alone.

Files:

- `audio/sfx/crate-impact-hard-surface.json` — 1783 bytes; sha256 `2652a7c5bd00c82ea079290d535321193845b146b1948fe207635e52cfc38276`; descriptor, application/json
- `audio/sfx/crate-impact-hard-surface.wav` — 17644 bytes; sha256 `1e634f03aebdb0ee82a4c24a0174d381a0552e6dfb03e996b34de8905359aa5e`; best, audio/wav
- `audio/sfx/crate-impact-hard-surface.raw.wav` — 96044 bytes; sha256 `21ab5fad58956ddd6fdc488a352e14265ce1c92521ec5783b947f2fb14a46d06`; raw, audio/wav
- `audio/sfx/crate-impact-hard-surface.var2.wav` — 96044 bytes; sha256 `2419a71d18dff22ee6efee7bc6d9b56e1666cd14c054cc73a43a6bc7ef34b662`; variation, audio/wav
- `audio/sfx/crate-impact-hard-surface.var3.wav` — 96044 bytes; sha256 `f65e7061bae4cdfd5436c8a087e0ba05685b678176ae8abc5149c08ed7a8cd19`; variation, audio/wav

Edges:

- `enhances` (sounds-for) → `audio-package`

### `audio-crate-kicked-hard` — `core.audio.effect`

Active version 1. Meaning: Sound for 'wooden crate': kicked forcefully. Best take plus every variation and the pre-refinement raw, so an A/B is possible from the file alone.

Files:

- `audio/sfx/crate-kicked-hard.json` — 1764 bytes; sha256 `350e6bb14ed8b36a0c9a3a207c882bf4f41ce7faafa220469ba1e339c7e7fcee`; descriptor, application/json
- `audio/sfx/crate-kicked-hard.wav` — 64044 bytes; sha256 `9a5938c3540e3fc3385c87a42876875887192c468b82281e7c55ec8938bf1aa6`; best, audio/wav
- `audio/sfx/crate-kicked-hard.var2.wav` — 64044 bytes; sha256 `cfc0f04adc256dd695c478f1005fa5be5494b397f511e169b937b8b4bafd7df4`; variation, audio/wav
- `audio/sfx/crate-kicked-hard.var3.wav` — 64044 bytes; sha256 `4b0955523ebcd895400aceaab17f3595a11278a441e39c5f7c4a39108d0f9062`; variation, audio/wav

Edges:

- `enhances` (sounds-for) → `audio-package`

### `audio-crate-scraped-edge` — `core.audio.effect`

Active version 1. Meaning: Sound for 'wooden crate': scraped along edge. Best take plus every variation and the pre-refinement raw, so an A/B is possible from the file alone.

Files:

- `audio/sfx/crate-scraped-edge.json` — 1701 bytes; sha256 `58f6b1d386a53480de860256771a628392adfe578a9a4aca744d66516c48c295`; descriptor, application/json
- `audio/sfx/crate-scraped-edge.wav` — 160044 bytes; sha256 `dfee5847b259ea0329918fd1ecf2338d3cdee0a2ea6f683f8ba3cf20439100c0`; best, audio/wav
- `audio/sfx/crate-scraped-edge.var2.wav` — 160044 bytes; sha256 `dcaaa785bdaf882836f65038f6c18874bc2e764d65ced29e441ad8abc0a4903c`; variation, audio/wav
- `audio/sfx/crate-scraped-edge.var3.wav` — 160044 bytes; sha256 `7afcf10a15f0b6fe6d455c69546a0409b252f3ac23098959db6011e22ed7f12b`; variation, audio/wav

Edges:

- `enhances` (sounds-for) → `audio-package`

### `audio-crate-tipped-over` — `core.audio.effect`

Active version 1. Meaning: Sound for 'wooden crate': tipped over onto side. Best take plus every variation and the pre-refinement raw, so an A/B is possible from the file alone.

Files:

- `audio/sfx/crate-tipped-over.json` — 1784 bytes; sha256 `01d46d5333cf2a337bdb1a0d458f48b4d0af165b10f3f81266ff3daf72669919`; descriptor, application/json
- `audio/sfx/crate-tipped-over.wav` — 106286 bytes; sha256 `1170f4c3715e0e6c3e5a63b63967948029973e9e6762cffb11dace3e55ae8e86`; best, audio/wav
- `audio/sfx/crate-tipped-over.raw.wav` — 128044 bytes; sha256 `6ba19740dfd2c9e127dd111b8f4e43c65cb61798674c5fb842cb14d7a145e0d8`; raw, audio/wav
- `audio/sfx/crate-tipped-over.var2.wav` — 128044 bytes; sha256 `d9777b01c927985707db9b7dbd306d8554ae42769e41feedc7724977ac910089`; variation, audio/wav
- `audio/sfx/crate-tipped-over.var3.wav` — 128044 bytes; sha256 `cb5bfedf9ed1af12bfd8a13efc76b1488599543f66148292057961ee73e364af`; variation, audio/wav

Edges:

- `enhances` (sounds-for) → `audio-package`

### `audio-crate-set-down-hard` — `core.audio.effect`

Active version 1. Meaning: Sound for 'wooden crate': set down firmly. Best take plus every variation and the pre-refinement raw, so an A/B is possible from the file alone.

Files:

- `audio/sfx/crate-set-down-hard.json` — 1653 bytes; sha256 `eec08c90a3c55f505c8d17c49caaa89057ef5a5b8c3ba7d5f8a4cce87fa8688e`; descriptor, application/json
- `audio/sfx/crate-set-down-hard.wav` — 21164 bytes; sha256 `74f60a7b5a82f718196ed3e546785e286795f43e3080f69d08223222d85adcda`; best, audio/wav
- `audio/sfx/crate-set-down-hard.raw.wav` — 64044 bytes; sha256 `7d3ccc13e2ed18f87b1c63de4badc83610337ff847981bb687b6bf432b40d7e5`; raw, audio/wav
- `audio/sfx/crate-set-down-hard.var2.wav` — 64044 bytes; sha256 `b3aa944431625ebc854cd1c4865163d61c9e73e569a7e7982c001f7a26bd0f75`; variation, audio/wav
- `audio/sfx/crate-set-down-hard.var3.wav` — 64044 bytes; sha256 `681cb150a44f212930ff4ec128d07324906bd7b5e6bd8d5933c1bdb4aaca6533`; variation, audio/wav

Edges:

- `enhances` (sounds-for) → `audio-package`

### `audio-plank-dragged-wood-floor` — `core.audio.effect`

Active version 1. Meaning: Sound for 'wooden plank': dragged across wooden floor. Best take plus every variation and the pre-refinement raw, so an A/B is possible from the file alone.

Files:

- `audio/sfx/plank-dragged-wood-floor.json` — 1637 bytes; sha256 `e4f116a78d10379c107bb50afc3350fb6d3db11112776e3c070cf747b4597338`; descriptor, application/json
- `audio/sfx/plank-dragged-wood-floor.wav` — 160044 bytes; sha256 `b5a3d842c5c12da8fd4fe85c0ce641bcca493b6ef45838dfa290acf5214e41e8`; best, audio/wav
- `audio/sfx/plank-dragged-wood-floor.var2.wav` — 160044 bytes; sha256 `0f173628a13a4184aaf95edc0800b729345d35fc5777569d003ca8fd98242105`; variation, audio/wav
- `audio/sfx/plank-dragged-wood-floor.var3.wav` — 160044 bytes; sha256 `a666f6f47f962cf43cf644037df702647a260a9591ca4246de8b671b11fbe82e`; variation, audio/wav

Edges:

- `enhances` (sounds-for) → `audio-package`

### `audio-plank-impact-hard-surface` — `core.audio.effect`

Active version 1. Meaning: Sound for 'wooden plank': struck by heavy object. Best take plus every variation and the pre-refinement raw, so an A/B is possible from the file alone.

Files:

- `audio/sfx/plank-impact-hard-surface.json` — 2246 bytes; sha256 `975918b66703d069b6e8f642fdfb30b251b9760a1f821ad49aa6636733a6bdd9`; descriptor, application/json
- `audio/sfx/plank-impact-hard-surface.wav` — 13802 bytes; sha256 `d23ccbd3e003fdd7c1902d922b4f56b20bd368ee532d1a481a6ef97a66829e8d`; best, audio/wav
- `audio/sfx/plank-impact-hard-surface.raw.wav` — 96044 bytes; sha256 `93299d0a784c97232c1d5fb2d0e03106df85b03344c33f8530568ae316b38387`; raw, audio/wav
- `audio/sfx/plank-impact-hard-surface.var2.wav` — 96044 bytes; sha256 `592f7ee8218845baaa90f7449287d0f07217b1b54b9a080791f704fec694a18e`; variation, audio/wav
- `audio/sfx/plank-impact-hard-surface.var3.wav` — 96044 bytes; sha256 `2c81d214eb6909620995c7d0c586aed7e10e3b37a3b449842e0b91e895591810`; variation, audio/wav

Edges:

- `enhances` (sounds-for) → `audio-package`

### `audio-plank-kicked-hard` — `core.audio.effect`

Active version 1. Meaning: Sound for 'wooden plank': kicked forcefully. Best take plus every variation and the pre-refinement raw, so an A/B is possible from the file alone.

Files:

- `audio/sfx/plank-kicked-hard.json` — 2093 bytes; sha256 `6fcabf90bc500356df8cc411607d11f52cbe68286c58bc00e2c0d575622df94c`; descriptor, application/json
- `audio/sfx/plank-kicked-hard.wav` — 128044 bytes; sha256 `be4798370ae6da3bc6df25a63e6f11edcb117b736b6a120c24dd5cf61fbcc87e`; best, audio/wav
- `audio/sfx/plank-kicked-hard.var2.wav` — 128044 bytes; sha256 `58f6602180e87bbb8c24aacb4359ca52afcf9cd19e1837b5e9a732ba8a86f067`; variation, audio/wav
- `audio/sfx/plank-kicked-hard.var3.wav` — 128044 bytes; sha256 `bed79c8946b6c82b98a471bf51c8a140486e49d97bdbf7a3c2d882ce9b2c66e0`; variation, audio/wav

Edges:

- `enhances` (sounds-for) → `audio-package`

### `audio-plank-scraped-edge` — `core.audio.effect`

Active version 1. Meaning: Sound for 'wooden plank': scraped along edge. Best take plus every variation and the pre-refinement raw, so an A/B is possible from the file alone.

Files:

- `audio/sfx/plank-scraped-edge.json` — 2010 bytes; sha256 `e438f2fb28e7bb332163f9ff3dceb4b40a97cc48cd86a5ddb8724a70ae8dbf41`; descriptor, application/json
- `audio/sfx/plank-scraped-edge.wav` — 51244 bytes; sha256 `2b2b6be0519174fd836e23f11aed0185f9b426f506d17b96acfd08bbc4852f72`; best, audio/wav
- `audio/sfx/plank-scraped-edge.raw.wav` — 160044 bytes; sha256 `d2ae21a52356cee44f541e3b8a65309818bee0bff6fa6d4ebcbef15e0bcf9212`; raw, audio/wav
- `audio/sfx/plank-scraped-edge.var2.wav` — 160044 bytes; sha256 `01886b1051909ab203d4146cb441e78761b942cd3617aaa5622810eaae750640`; variation, audio/wav
- `audio/sfx/plank-scraped-edge.var3.wav` — 160044 bytes; sha256 `ed2187d77ebbde1b38de5b06c1c12cddca2c331e46286a0a9e42b5da98ca62bd`; variation, audio/wav

Edges:

- `enhances` (sounds-for) → `audio-package`

### `audio-corner-joined-beams` — `core.audio.effect`

Active version 1. Meaning: Sound for 'wooden crate corner': pressed under load. Best take plus every variation and the pre-refinement raw, so an A/B is possible from the file alone.

Files:

- `audio/sfx/corner-joined-beams.json` — 1621 bytes; sha256 `68563bc9bdd280fb70a16895ef193d0fa73c77b2d9cb02b2e93de832ba30da2f`; descriptor, application/json
- `audio/sfx/corner-joined-beams.wav` — 89964 bytes; sha256 `901ce417725a16819ec7ebeee77f0058a3af1d7fe35bc13faff616fab3856109`; best, audio/wav
- `audio/sfx/corner-joined-beams.raw.wav` — 192044 bytes; sha256 `4b27181747768bf4b2ea72e18bfc3bdf852dc3426a026407ca068430155846b7`; raw, audio/wav
- `audio/sfx/corner-joined-beams.var2.wav` — 192044 bytes; sha256 `c515d13e8fb0327ef4b5b898cb92be4b132d789d9e28d34ec0c2b34f2b318093`; variation, audio/wav
- `audio/sfx/corner-joined-beams.var3.wav` — 192044 bytes; sha256 `bc5f571af949c8f7798757efe3985bd0c0673a6c0cad0956193819d9f54a3888`; variation, audio/wav

Edges:

- `enhances` (sounds-for) → `audio-package`

### `audio-beam-impact-hard-surface` — `core.audio.effect`

Active version 1. Meaning: Sound for 'wooden beam': struck by heavy object. Best take plus every variation and the pre-refinement raw, so an A/B is possible from the file alone.

Files:

- `audio/sfx/beam-impact-hard-surface.json` — 1740 bytes; sha256 `25777c579f0456b33233fa86e32c28a0a248c4ff716973a66c04d99db3c46a7c`; descriptor, application/json
- `audio/sfx/beam-impact-hard-surface.wav` — 38124 bytes; sha256 `8024bc1d981ebd28fd9c2943ef46ce1b3e786cecb235b69af9523f4a994eae4a`; best, audio/wav
- `audio/sfx/beam-impact-hard-surface.raw.wav` — 96044 bytes; sha256 `a5130ae2126dfcfdcee3c4a89fd179f71f87ffda4d9485d3b853f893360e78b6`; raw, audio/wav
- `audio/sfx/beam-impact-hard-surface.var2.wav` — 96044 bytes; sha256 `f02ab8750ec7fda7f9cbf50e802936bcddcd5eefd0900689dfa7ccd40fab4f9f`; variation, audio/wav
- `audio/sfx/beam-impact-hard-surface.var3.wav` — 96044 bytes; sha256 `4228f758e4bc6d53ba163571a6db1037d5dedd4c4fa6e0569e06ddc8f8a5d5dc`; variation, audio/wav

Edges:

- `enhances` (sounds-for) → `audio-package`

### `audio-beam-kicked-hard` — `core.audio.effect`

Active version 1. Meaning: Sound for 'wooden beam': kicked forcefully. Best take plus every variation and the pre-refinement raw, so an A/B is possible from the file alone.

Files:

- `audio/sfx/beam-kicked-hard.json` — 1878 bytes; sha256 `ec89ef86e9858a7143750cc289719e395d55fbc6696f0e127d62ed6574c2fed2`; descriptor, application/json
- `audio/sfx/beam-kicked-hard.wav` — 79084 bytes; sha256 `f7731f12bd0bed7dec7407ad088b2f505efde515563ca364e7e2bc4af5a94ec9`; best, audio/wav
- `audio/sfx/beam-kicked-hard.raw.wav` — 128044 bytes; sha256 `c698beea9927ef9fd5d7d3676aeb390f7ef70d5008762edd33018de608ed6195`; raw, audio/wav
- `audio/sfx/beam-kicked-hard.var2.wav` — 128044 bytes; sha256 `eddb10fb09b9251561a3a2a0aede36878a83b8a0037a3c41eb5cff60da816ac3`; variation, audio/wav
- `audio/sfx/beam-kicked-hard.var3.wav` — 128044 bytes; sha256 `232b58a7b43438e7f9dd910c4022ea8a1e66bf4c21c63f3587918ba40b3bc252`; variation, audio/wav

Edges:

- `enhances` (sounds-for) → `audio-package`

### `audio-dowel-impact-hard-surface` — `core.audio.effect`

Active version 1. Meaning: Sound for 'wooden dowel': struck by heavy object. Best take plus every variation and the pre-refinement raw, so an A/B is possible from the file alone.

Files:

- `audio/sfx/dowel-impact-hard-surface.json` — 1850 bytes; sha256 `0aa10f1567658804ec140ccc88a37e5d440050731a37eac757e305d9df163de4`; descriptor, application/json
- `audio/sfx/dowel-impact-hard-surface.wav` — 15404 bytes; sha256 `194fd51032e0288eda96960aa5fc4a7420c3120abb714c19a3c7f9792ccae690`; best, audio/wav
- `audio/sfx/dowel-impact-hard-surface.raw.wav` — 96044 bytes; sha256 `eaa572271f866e7e498454043e20c58af3e5054f5bc8693cba1f3e38f89dc149`; raw, audio/wav
- `audio/sfx/dowel-impact-hard-surface.var2.wav` — 96044 bytes; sha256 `23ed29a1d9fc242e21ddce4f3a9cbd3da646af39c38a86cec657d89d8bc0fc2d`; variation, audio/wav
- `audio/sfx/dowel-impact-hard-surface.var3.wav` — 96044 bytes; sha256 `45201965391513d270a6081b3e265db0cd1fd5ed554090b8b6d568469938e96b`; variation, audio/wav

Edges:

- `enhances` (sounds-for) → `audio-package`

### `audio-dowel-kicked-hard` — `core.audio.effect`

Active version 1. Meaning: Sound for 'wooden dowel': kicked forcefully. Best take plus every variation and the pre-refinement raw, so an A/B is possible from the file alone.

Files:

- `audio/sfx/dowel-kicked-hard.json` — 1786 bytes; sha256 `752966720641f4c696ebdc3ce5b2752eac381b9510df892c4fa622f92c2dacef`; descriptor, application/json
- `audio/sfx/dowel-kicked-hard.wav` — 57644 bytes; sha256 `2977f49c46d79c70b4b8655fdd7b66060295ed6a72d56e0a3f403be22fce54e2`; best, audio/wav
- `audio/sfx/dowel-kicked-hard.raw.wav` — 128044 bytes; sha256 `1bada8ba0a5aead92166ed0b9628177682e7fd77450d003c2457b27d62ea208c`; raw, audio/wav
- `audio/sfx/dowel-kicked-hard.var2.wav` — 128044 bytes; sha256 `ebd63fbe05180d6d1dafe49cdf17df3229e0b9daa51da5f337620f182156d740`; variation, audio/wav
- `audio/sfx/dowel-kicked-hard.var3.wav` — 128044 bytes; sha256 `1d70cd06b5af166df42c7ed2f454eef6995a738d3469b20a0193a1061920dbeb`; variation, audio/wav

Edges:

- `enhances` (sounds-for) → `audio-package`

### `audio-front-face-impact-hard-surface` — `core.audio.effect`

Active version 1. Meaning: Sound for 'wooden crate front': struck by heavy object. Best take plus every variation and the pre-refinement raw, so an A/B is possible from the file alone.

Files:

- `audio/sfx/front-face-impact-hard-surface.json` — 1922 bytes; sha256 `92e82770202b480d998c1c1450e635de0d93832ccffb554f678b62eb42851c6e`; descriptor, application/json
- `audio/sfx/front-face-impact-hard-surface.wav` — 13164 bytes; sha256 `1dc5ffa828a98beeeaf63d4140ad49a1b77e8ab1b470c341d6da7343abf23639`; best, audio/wav
- `audio/sfx/front-face-impact-hard-surface.raw.wav` — 96044 bytes; sha256 `4c21f82292a9e6f8e13a89233184f449f05ea9178aa5c6a0258ee06944fe5e54`; raw, audio/wav
- `audio/sfx/front-face-impact-hard-surface.var2.wav` — 96044 bytes; sha256 `2343a9c10b8fb9c325d96e387211a60697e457e9ddb7387806f833c0290eb179`; variation, audio/wav
- `audio/sfx/front-face-impact-hard-surface.var3.wav` — 96044 bytes; sha256 `ad5a427baa6ea0277bfbee570f8f8e5659b498bf85d8dccc28f80997d077f37f`; variation, audio/wav

Edges:

- `enhances` (sounds-for) → `audio-package`

### `audio-front-face-kicked-hard` — `core.audio.effect`

Active version 1. Meaning: Sound for 'wooden crate front': kicked forcefully. Best take plus every variation and the pre-refinement raw, so an A/B is possible from the file alone.

Files:

- `audio/sfx/front-face-kicked-hard.json` — 1855 bytes; sha256 `a52e18a4f07b8ca07b8bf7da8b11d08514a58b5866783ddff4939db187d6eb02`; descriptor, application/json
- `audio/sfx/front-face-kicked-hard.wav` — 128044 bytes; sha256 `640a50af4deeeaec7d34cad3fba7614732c76a7ea6b04151e79369a0de066bbb`; best, audio/wav
- `audio/sfx/front-face-kicked-hard.var2.wav` — 128044 bytes; sha256 `772b518013c2ba1d8eb91aa3a7482061d259831967c00085e390bd28c867f632`; variation, audio/wav
- `audio/sfx/front-face-kicked-hard.var3.wav` — 128044 bytes; sha256 `f3874022963632232dad607e4c009bb19908ee81e37ff8df359486081507dd93`; variation, audio/wav

Edges:

- `enhances` (sounds-for) → `audio-package`

### `audio-crate-wind-forest` — `core.audio.ambience`

Active version 1. Meaning: Sound for 'wooden crate': wind blowing through gaps. Best take plus every variation and the pre-refinement raw, so an A/B is possible from the file alone.

Files:

- `audio/sfx/crate-wind-forest.json` — 1436 bytes; sha256 `0ac3f53c944a1829f583957f22d2b81bdedd55c610a5fbb52e9b0e92ecc7c2dc`; descriptor, application/json
- `audio/sfx/crate-wind-forest.wav` — 473004 bytes; sha256 `6e780ce5a8e8e48642079e287664f3fba9a6c2301eefbb063a4ec56fc2b420e2`; best, audio/wav
- `audio/sfx/crate-wind-forest.raw.wav` — 480044 bytes; sha256 `c08a86d4c98e272470a00babc1ce3b869d612395793437252faf23daf40833f9`; raw, audio/wav
- `audio/sfx/crate-wind-forest.var2.wav` — 480044 bytes; sha256 `a873568343351aa2befdaa141a8fda18bcfd8ff9a72798521eee50399475b927`; variation, audio/wav
- `audio/sfx/crate-wind-forest.var3.wav` — 480044 bytes; sha256 `5d5f45e2a6b7e9a09a846651c8f9485b78c0a350e8ae0d7c95b28db1b15d642f`; variation, audio/wav

Edges:

- `enhances` (sounds-for) → `audio-package`

### `audio-crate-wind-desert` — `core.audio.ambience`

Active version 1. Meaning: Sound for 'wooden crate': wind blowing across open surface. Best take plus every variation and the pre-refinement raw, so an A/B is possible from the file alone.

Files:

- `audio/sfx/crate-wind-desert.json` — 1703 bytes; sha256 `d9865cbc9acaa3d0e5b0fc12c1e106f4511b6511e8cf1174525f1eb83bb74a3f`; descriptor, application/json
- `audio/sfx/crate-wind-desert.wav` — 473004 bytes; sha256 `6de984b62575da77655a528ae15837430b9b8c8a12e515e6290e198fdeaaec12`; best, audio/wav
- `audio/sfx/crate-wind-desert.raw.wav` — 480044 bytes; sha256 `1aa69c70fb54c2818d1bdec52945610d8a6315d3d0aeb1b115c3400ceffcf01d`; raw, audio/wav
- `audio/sfx/crate-wind-desert.var2.wav` — 480044 bytes; sha256 `24a859865bde260f5f1dd4a128bdef55f35cd43775d31449ae2bbb80ae48c629`; variation, audio/wav
- `audio/sfx/crate-wind-desert.var3.wav` — 480044 bytes; sha256 `1b38dd93b29ef1de2a51d78552f2252c1dbb30a06f6ca36c53fc602e6199b710`; variation, audio/wav

Edges:

- `enhances` (sounds-for) → `audio-package`

### `audio-crate-wind-forest-dense` — `core.audio.ambience`

Active version 1. Meaning: Sound for 'wooden crate': wind blowing through dense forest. Best take plus every variation and the pre-refinement raw, so an A/B is possible from the file alone.

Files:

- `audio/sfx/crate-wind-forest-dense.json` — 1529 bytes; sha256 `4e4295e37a7e74cb3b3c3eabd6c9fe270c4fa657d6fa15aefc4382ee106a7faf`; descriptor, application/json
- `audio/sfx/crate-wind-forest-dense.wav` — 480044 bytes; sha256 `c5e10681d86d740ee3bf8f7c492badee6113ef1d8524abde9386ad962ede6c31`; best, audio/wav
- `audio/sfx/crate-wind-forest-dense.var2.wav` — 480044 bytes; sha256 `1631e41367104aa849b38015826a3c615d1f5cc62d5f928e01444e7bcaec855a`; variation, audio/wav
- `audio/sfx/crate-wind-forest-dense.var3.wav` — 480044 bytes; sha256 `131fa75a665ea22c956879532e6a194f7d6577c28af62cd752439ddcedb501d4`; variation, audio/wav

Edges:

- `enhances` (sounds-for) → `audio-package`

### `semantics` — `core.semantics`

Active version 1. Meaning: Hand-authored facet tags, palette and search text. This node alone renders a browser listing (law 9).

Files:

- `semantics/semantics.json` — 2589 bytes; sha256 `d5be6dc01dcc5ec0e047b1552df016f498a24318bf45a6a59508125fc60ce156`

Edges:

- `enhances` (describes) → `geom-game`

### `props` — `core.props`

Active version 1. Meaning: Authored simulation properties for the crate's wood, with every value carrying its own unit and stamp.

Files:

- `properties/properties.json` — 3470 bytes; sha256 `0864247b109bc656ab44cc84b9a633e6b312328743e94dade5eda74a24f4508e`

Edges:

- `enhances` (properties-of) → `material-wood`

### `provenance` — `core.provenance`

Active version 1. Meaning: Who made what, from what, with which models, and which gates it had to pass.

Files:

- `provenance/provenance.json` — 4264 bytes; sha256 `dcfdceb4551b3c6c6443ddc14d940d4d0c8176fabd6de2e3c7398baf3def0af0`

Edges:

- None.

### `spec` — `core.spec`

Active version 1. Meaning: The format specification, its schemas and its binary layout grammars, travelling inside the file it describes (law 2).

Files:

- `spec/MINI-SPECS.md` — 33241 bytes; sha256 `c84e668b8b6870d72d26b3810f4b1645cf5d10bfa390757f99cdc93fd3b95bda`
- `spec/PROFILE-IMAGE.md` — 12698 bytes; sha256 `f664710d59b9c33a8cd33727a49d15780b30a559cbc9480f6182bc0523296a6e`
- `spec/README.md` — 10319 bytes; sha256 `a480b73d020a446f8cc016fa0d5e4893ba9bc388396e44d88780403bd4db10eb`
- `spec/SPEC.md` — 99291 bytes; sha256 `69abcae9668f90fd2fda5d64d3b1b4096b333a0967dcd2461b9de08546dbc46d`
- `spec/X-C2PA-EXPORT.md` — 7461 bytes; sha256 `2b3421f5dd51cc885762754d0ce865c6ee5b9cc11428d8a7945f59a2b7485306`
- `spec/conventions-map.image.json` — 2416 bytes; sha256 `ae4116c7c5c61b6342e0ecdc875ed42015179254e7012007cfe1e3c3b0b273cc`
- `spec/conventions-map.json` — 9269 bytes; sha256 `1d0aa2edcb95dda2ddf366248d9572dedc2cc81ff6954920b131812ef43b7b37`
- `spec/examples/MANIFEST.example.json` — 20608 bytes; sha256 `dbfd2a76434e48adcb20fb009ba4d52ddb67b0189fd3e857d1fa054ba0b7e558`
- `spec/examples/make-examples.py` — 26764 bytes; sha256 `c5d2eef5a129124a7e6a2cbe9533115f0f49bd3872c8dc48021d14651ff63576`
- `spec/examples/restposes.example.hex.txt` — 4415 bytes; sha256 `08cec9d6bf054544e1a168aad43f84f113c98a0753b857992775081452d98600`
- `spec/examples/restposes.example.wkrp` — 560 bytes; sha256 `6c2c44d5492a4e4f1dbcf5b4c30beb5ada4825ffba7ab7e5010040494ee15f95`
- `spec/extensions/x.cub.v1.baked.layout.txt` — 9359 bytes; sha256 `ba64dfd8bf845e128216e132fa05bad979f65fd66c2c3fa0eccdab7ce95aea71`
- `spec/extensions/x.cub.v1.md` — 8783 bytes; sha256 `0b36de4fa7783301d49dd20483fd43ed7a12e4f06b22c54282981391912b5f42`
- `spec/facets.json` — 11978 bytes; sha256 `f73949dd1cab2d827148eef12c4fa56017b4b06fdd4566f89a561ee5ef7dbba1`
- `spec/layouts/ENVELOPE.layout.txt` — 25287 bytes; sha256 `0e569e6a0baa2bc8b7ca5118ba8bb46329f040ad31bf2564ff6002f961b74f6c`
- `spec/layouts/animclip.layout.txt` — 16800 bytes; sha256 `ee4a9db15b32a3540fc4dabbc07cf9f91e3f24b3bdad6d0f02711da9e674b9e6`
- `spec/layouts/embedding.layout.txt` — 13909 bytes; sha256 `f75de7f5d380f122c6d363ce144e529d165f0cccdcf12dea934cac9be62b2b85`
- `spec/layouts/flowfield.layout.txt` — 6263 bytes; sha256 `f8d2e9cc571b22fa0748dcb8cb47aa3235d8cfcea92467801a18ddf2b104903a`
- `spec/layouts/gsplat.layout.txt` — 23310 bytes; sha256 `a68bcd79797b7f86f9ed22167a03d2cddc919e72cf2d86b8997e283c71766dfc`
- `spec/layouts/imposter.layout.txt` — 10446 bytes; sha256 `29649f2aa83078fbb13731f0481eb8e26c96f9ea54a821a6dfbef805ed31236f`
- `spec/layouts/points.layout.txt` — 16663 bytes; sha256 `6b36a38432a4468655c0c176c02788b39c23db8ea33e2b3af69011a4d59c4899`
- `spec/layouts/restposes.layout.txt` — 5958 bytes; sha256 `cc2d00b870a12ccedf76ac1fbd61dc5b19712e8c067c2d0f85f50033620efaf5`
- `spec/layouts/skeleton.layout.txt` — 5964 bytes; sha256 `f9656db427660fd781cb7d3732013ff6958f3b816cc9ba93403e37b6e1295dc1`
- `spec/schemas/conventions-map.schema.json` — 4614 bytes; sha256 `97e8cae5199506e0ade43b14e51f0bc3569c8be4dc0e18b8ba56f9cada1afe7f`
- `spec/schemas/core.anim.clip.schema.json` — 9585 bytes; sha256 `2e3d87f8447bd3ab21da0c0b34ad0ab24e95bcd4cfb28a4ba2edfdddadbafc36`
- `spec/schemas/core.audio.effect.schema.json` — 8628 bytes; sha256 `04ec3b581af20448c0a0e4ea093101e46e8079b0e07c87c9aafdf32415e9efd5`
- `spec/schemas/core.audio.package.schema.json` — 7320 bytes; sha256 `d45aa59c656693f9bf93c09245b9d80e6101d06e765f63215f4faa6116670545`
- `spec/schemas/core.destruct.schema.json` — 6319 bytes; sha256 `87142e399b83e6f5abffe8655302d45f27b32781766f0821826accb41e97ff32`
- `spec/schemas/core.disclosure.schema.json` — 11515 bytes; sha256 `ac1df873ac607e1bc4778f1a97bbec5fb13b7177e715b93e5ef60eb57164c785`
- `spec/schemas/core.imposter.schema.json` — 6708 bytes; sha256 `5b5c3875a91274e38e41e99a55d3041438c0471a584699290c7a6b76ce9f6306`
- `spec/schemas/core.material.schema.json` — 4823 bytes; sha256 `487505e761fc02d5cd8cde8494a7ede233b4d6edc3ee57d8e9c8c6e68590baa6`
- `spec/schemas/core.phys.body.schema.json` — 6157 bytes; sha256 `d0d462fc17e21805da5c075fd83eeccda4946367c5f4381651544b89555de4ac`
- `spec/schemas/core.phys.bounds.schema.json` — 3164 bytes; sha256 `acf0c228fd2b4b4cc46771b85af5bd62c49d14e88468c7b268d07f4e8f0e3a2e`
- `spec/schemas/core.phys.colliders.schema.json` — 4116 bytes; sha256 `70dd20d638bef9146588222bec3000ab9e0d2430d1dd96fbfda6a5ffacd62794`
- `spec/schemas/core.props.schema.json` — 11666 bytes; sha256 `95a8124f54346735946431d7de34cb665eec8ca7450a794831d6aee99affa2e3`
- `spec/schemas/core.provenance.schema.json` — 6140 bytes; sha256 `d99d7cec51ac6b114896c58f6428ecd573ead0f9288dcac084e8d38183811935`
- `spec/schemas/core.recipe.schema.json` — 26485 bytes; sha256 `19b723bf06c66ccf15948100350c4857e0694a5850e1e111e35a894c416e0f30`
- `spec/schemas/core.retarget.bind.schema.json` — 13337 bytes; sha256 `e8cacdd8a72e7e33100507cbe187ffe91f0ec98516bb52ea08ee6addf298f480`
- `spec/schemas/core.semantics.schema.json` — 6917 bytes; sha256 `3e6fb595e77cae734631e4f67759f470e6fc11acee4a54e8ca6a3deaaef9c68f`
- `spec/schemas/core.skeleton.schema.json` — 11464 bytes; sha256 `7e0f7aec2a7616e7ab4d94c96ac82cf3496af2d3758b9bbf13d866663782c7f8`
- `spec/schemas/core.tool.config.schema.json` — 7321 bytes; sha256 `f386341239a744cf81140a79d7a780d1d2d6faebf613bceab55a7d909f750b1f`
- `spec/schemas/core.tool.schema.json` — 10894 bytes; sha256 `beb9c08f08a597c9aa8b796bdffa678d8305d9bf53aff54003b40a4a2a2b9b2e`
- `spec/schemas/facets.schema.json` — 3593 bytes; sha256 `6a5304c901b8f3c2ff30734c0784fa074a111a4312b634b74351cbe234299f87`
- `spec/schemas/manifest.image.schema.json` — 27420 bytes; sha256 `98ea85796f5bdaed35556105389dd663ee2865ae29abfcb9db9ddaecf6314d75`
- `spec/schemas/manifest.schema.json` — 44155 bytes; sha256 `63f2b8b1b7bbd2de9a2d76d7b4225fc3fe76278870425f5e3a13347694b7f011`
- `spec/schemas/signature.schema.json` — 11209 bytes; sha256 `cde6abccc1a071ec0e33ffeabf1f7b7131805a2339fd055566cd3b76c5e92b13`
- `spec/schemas/x.c2pa.export.schema.json` — 4935 bytes; sha256 `bc1a5c7486f4c90e5331316e122d26f82680601e53bce7142d9b59576ab4600d`
- `spec/skeleton/canonical-humanoid-v1.json` — 22429 bytes; sha256 `7b5415347d0456f164b08abf5b4114f5db00215d6ed71d6f841412825a8fd481`
- `spec/skeleton/core.hands.v1.json` — 26112 bytes; sha256 `5e1b90841b8a6b701c3d9f07a9a8f09caec97c544975979f01e972464d40e15a`
- `spec/skeleton/derive-canonical-humanoid.py` — 19852 bytes; sha256 `20f5c3504c87f9c56ae82120fcdb5f006bd565194576e4b818452934069d6c35`

Edges:

- None.

### `loader-python` — `core.loader`

Active version 1. Meaning: A single-file, dependency-free reader for this package, carried as payload so the file brings its own reader (law 1).

Files:

- `loaders/werk_read.py` — 42226 bytes; sha256 `8274359b795405b481d535572e3ec8930c29da20140f23e356c6fef84f162b84`

Edges:

- None.

### `loader-rust` — `core.loader`

Active version 1. Meaning: A single-file, dependency-free reader for this package, carried as payload so the file brings its own reader (law 1).

Files:

- `loaders/werk_read.rs` — 98761 bytes; sha256 `f2ef9ba2badd94a1312cd9a42649386e017197bdc3cb0d5106f1ae745d173e62`

Edges:

- None.

### `loader-c` — `core.loader`

Active version 1. Meaning: A single-file, dependency-free reader for this package, carried as payload so the file brings its own reader (law 1).

Files:

- `loaders/werk_read.c` — 111051 bytes; sha256 `dcafb38877b1be2b13cbba1daedc1209ff15eb07fa9a6332e37e78ec119e4292`

Edges:

- None.

### `license` — `core.license`

Active version 1. Meaning: The full licence text, embedded, never a link (law 7).

Files:

- `LICENSE` — 2132 bytes; sha256 `5cf4c8595ca919f21c891d41cb5391c389c188206f705bb01bbc746f10990c53`

Edges:

- None.

### `readme` — `core.readme`

Active version 1. Meaning: One page for a human who opened this file and wants to know what it is.

Files:

- `README.txt` — 1264 bytes; sha256 `f7923cb1f38316f610d8198a2797775ceeb4b07cc6b07d405ee6e8932ccc1564`

Edges:

- None.

## Physical archive order

1. `MANIFEST.json`
2. `SIGNATURE.json`
3. `LICENSE`
4. `README.txt`
5. `loaders/werk_read.c`
6. `loaders/werk_read.py`
7. `loaders/werk_read.rs`
8. `spec/MINI-SPECS.md`
9. `spec/PROFILE-IMAGE.md`
10. `spec/README.md`
11. `spec/SPEC.md`
12. `spec/X-C2PA-EXPORT.md`
13. `spec/conventions-map.image.json`
14. `spec/conventions-map.json`
15. `spec/examples/MANIFEST.example.json`
16. `spec/examples/make-examples.py`
17. `spec/examples/restposes.example.hex.txt`
18. `spec/examples/restposes.example.wkrp`
19. `spec/extensions/x.cub.v1.baked.layout.txt`
20. `spec/extensions/x.cub.v1.md`
21. `spec/facets.json`
22. `spec/layouts/ENVELOPE.layout.txt`
23. `spec/layouts/animclip.layout.txt`
24. `spec/layouts/embedding.layout.txt`
25. `spec/layouts/flowfield.layout.txt`
26. `spec/layouts/gsplat.layout.txt`
27. `spec/layouts/imposter.layout.txt`
28. `spec/layouts/points.layout.txt`
29. `spec/layouts/restposes.layout.txt`
30. `spec/layouts/skeleton.layout.txt`
31. `spec/schemas/conventions-map.schema.json`
32. `spec/schemas/core.anim.clip.schema.json`
33. `spec/schemas/core.audio.effect.schema.json`
34. `spec/schemas/core.audio.package.schema.json`
35. `spec/schemas/core.destruct.schema.json`
36. `spec/schemas/core.disclosure.schema.json`
37. `spec/schemas/core.imposter.schema.json`
38. `spec/schemas/core.material.schema.json`
39. `spec/schemas/core.phys.body.schema.json`
40. `spec/schemas/core.phys.bounds.schema.json`
41. `spec/schemas/core.phys.colliders.schema.json`
42. `spec/schemas/core.props.schema.json`
43. `spec/schemas/core.provenance.schema.json`
44. `spec/schemas/core.recipe.schema.json`
45. `spec/schemas/core.retarget.bind.schema.json`
46. `spec/schemas/core.semantics.schema.json`
47. `spec/schemas/core.skeleton.schema.json`
48. `spec/schemas/core.tool.config.schema.json`
49. `spec/schemas/core.tool.schema.json`
50. `spec/schemas/facets.schema.json`
51. `spec/schemas/manifest.image.schema.json`
52. `spec/schemas/manifest.schema.json`
53. `spec/schemas/signature.schema.json`
54. `spec/schemas/x.c2pa.export.schema.json`
55. `spec/skeleton/canonical-humanoid-v1.json`
56. `spec/skeleton/core.hands.v1.json`
57. `spec/skeleton/derive-canonical-humanoid.py`
58. `semantics/semantics.json`
59. `audio/sfx/crate-impact-hard-surface.wav`
60. `materials/wood.json`
61. `physics/bounds.json`
62. `properties/properties.json`
63. `provenance/provenance.json`
64. `geometry/game.glb`
65. `geometry/source.glb`
66. `audio/package.json`
67. `audio/sfx/beam-impact-hard-surface.json`
68. `audio/sfx/beam-impact-hard-surface.raw.wav`
69. `audio/sfx/beam-impact-hard-surface.var2.wav`
70. `audio/sfx/beam-impact-hard-surface.var3.wav`
71. `audio/sfx/beam-impact-hard-surface.wav`
72. `audio/sfx/beam-kicked-hard.json`
73. `audio/sfx/beam-kicked-hard.raw.wav`
74. `audio/sfx/beam-kicked-hard.var2.wav`
75. `audio/sfx/beam-kicked-hard.var3.wav`
76. `audio/sfx/beam-kicked-hard.wav`
77. `audio/sfx/corner-joined-beams.json`
78. `audio/sfx/corner-joined-beams.raw.wav`
79. `audio/sfx/corner-joined-beams.var2.wav`
80. `audio/sfx/corner-joined-beams.var3.wav`
81. `audio/sfx/corner-joined-beams.wav`
82. `audio/sfx/crate-dragged-rough-concrete.json`
83. `audio/sfx/crate-dragged-rough-concrete.var2.wav`
84. `audio/sfx/crate-dragged-rough-concrete.var3.wav`
85. `audio/sfx/crate-dragged-rough-concrete.wav`
86. `audio/sfx/crate-impact-hard-surface.json`
87. `audio/sfx/crate-impact-hard-surface.raw.wav`
88. `audio/sfx/crate-impact-hard-surface.var2.wav`
89. `audio/sfx/crate-impact-hard-surface.var3.wav`
90. `audio/sfx/crate-kicked-hard.json`
91. `audio/sfx/crate-kicked-hard.var2.wav`
92. `audio/sfx/crate-kicked-hard.var3.wav`
93. `audio/sfx/crate-kicked-hard.wav`
94. `audio/sfx/crate-scraped-edge.json`
95. `audio/sfx/crate-scraped-edge.var2.wav`
96. `audio/sfx/crate-scraped-edge.var3.wav`
97. `audio/sfx/crate-scraped-edge.wav`
98. `audio/sfx/crate-set-down-hard.json`
99. `audio/sfx/crate-set-down-hard.raw.wav`
100. `audio/sfx/crate-set-down-hard.var2.wav`
101. `audio/sfx/crate-set-down-hard.var3.wav`
102. `audio/sfx/crate-set-down-hard.wav`
103. `audio/sfx/crate-tipped-over.json`
104. `audio/sfx/crate-tipped-over.raw.wav`
105. `audio/sfx/crate-tipped-over.var2.wav`
106. `audio/sfx/crate-tipped-over.var3.wav`
107. `audio/sfx/crate-tipped-over.wav`
108. `audio/sfx/crate-wind-desert.json`
109. `audio/sfx/crate-wind-desert.raw.wav`
110. `audio/sfx/crate-wind-desert.var2.wav`
111. `audio/sfx/crate-wind-desert.var3.wav`
112. `audio/sfx/crate-wind-desert.wav`
113. `audio/sfx/crate-wind-forest-dense.json`
114. `audio/sfx/crate-wind-forest-dense.var2.wav`
115. `audio/sfx/crate-wind-forest-dense.var3.wav`
116. `audio/sfx/crate-wind-forest-dense.wav`
117. `audio/sfx/crate-wind-forest.json`
118. `audio/sfx/crate-wind-forest.raw.wav`
119. `audio/sfx/crate-wind-forest.var2.wav`
120. `audio/sfx/crate-wind-forest.var3.wav`
121. `audio/sfx/crate-wind-forest.wav`
122. `audio/sfx/dowel-impact-hard-surface.json`
123. `audio/sfx/dowel-impact-hard-surface.raw.wav`
124. `audio/sfx/dowel-impact-hard-surface.var2.wav`
125. `audio/sfx/dowel-impact-hard-surface.var3.wav`
126. `audio/sfx/dowel-impact-hard-surface.wav`
127. `audio/sfx/dowel-kicked-hard.json`
128. `audio/sfx/dowel-kicked-hard.raw.wav`
129. `audio/sfx/dowel-kicked-hard.var2.wav`
130. `audio/sfx/dowel-kicked-hard.var3.wav`
131. `audio/sfx/dowel-kicked-hard.wav`
132. `audio/sfx/front-face-impact-hard-surface.json`
133. `audio/sfx/front-face-impact-hard-surface.raw.wav`
134. `audio/sfx/front-face-impact-hard-surface.var2.wav`
135. `audio/sfx/front-face-impact-hard-surface.var3.wav`
136. `audio/sfx/front-face-impact-hard-surface.wav`
137. `audio/sfx/front-face-kicked-hard.json`
138. `audio/sfx/front-face-kicked-hard.var2.wav`
139. `audio/sfx/front-face-kicked-hard.var3.wav`
140. `audio/sfx/front-face-kicked-hard.wav`
141. `audio/sfx/plank-dragged-wood-floor.json`
142. `audio/sfx/plank-dragged-wood-floor.var2.wav`
143. `audio/sfx/plank-dragged-wood-floor.var3.wav`
144. `audio/sfx/plank-dragged-wood-floor.wav`
145. `audio/sfx/plank-impact-hard-surface.json`
146. `audio/sfx/plank-impact-hard-surface.raw.wav`
147. `audio/sfx/plank-impact-hard-surface.var2.wav`
148. `audio/sfx/plank-impact-hard-surface.var3.wav`
149. `audio/sfx/plank-impact-hard-surface.wav`
150. `audio/sfx/plank-kicked-hard.json`
151. `audio/sfx/plank-kicked-hard.var2.wav`
152. `audio/sfx/plank-kicked-hard.var3.wav`
153. `audio/sfx/plank-kicked-hard.wav`
154. `audio/sfx/plank-scraped-edge.json`
155. `audio/sfx/plank-scraped-edge.raw.wav`
156. `audio/sfx/plank-scraped-edge.var2.wav`
157. `audio/sfx/plank-scraped-edge.var3.wav`
158. `audio/sfx/plank-scraped-edge.wav`
159. `x/splat-foley/segments/seg_00.png`
160. `x/splat-foley/segments/seg_01.png`
161. `x/splat-foley/segments/seg_02.png`
162. `x/splat-foley/segments/seg_03.png`
163. `x/splat-foley/segments/seg_04.png`
164. `x/splat-foley/segments/seg_05.png`
165. `x/splat-foley/segments/seg_06.png`
166. `x/splat-foley/segments/seg_07.png`
167. `x/splat-foley/segments/seg_08.png`
168. `x/splat-foley/segments/seg_09.png`
169. `x/splat-foley/views/view_00.png`
170. `x/splat-foley/views/view_01.png`
171. `x/splat-foley/views/view_02.png`
172. `x/splat-foley/views/view_03.png`
173. `x/splat-foley/views/view_04.png`
174. `x/splat-foley/views/view_05.png`
