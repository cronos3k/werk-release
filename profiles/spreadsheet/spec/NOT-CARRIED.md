# Reference specification files this package does not carry

This package belongs to an ArtCraft profile. Its `spec/` holds the part of the werk reference
specification that a package of such a profile can reach (`spec/CRAFT-BASE.md` section 1.1):
the container, manifest, version and signature rules, the mini-specs, the envelope grammar and
the base node types. `spec/SPEC.md` and `spec/README.md` also describe - and name the files
of - the node families of the reference profiles `3d-entity/1` and `image/1`. No node of
this package is of such a family, so those files are NOT in this package. They are listed
here so that a reference to one of them is answered inside the package: it is absent by
rule, not lost; its sha256 identifies the exact file in the werk reference tree.

| file | bytes | sha256 | defines only |
|---|---:|---|---|
| `spec/PROFILE-IMAGE.md` | 13433 | `bc9481b5d541dcd88512427184248663eb9ec3676372c127727e5f0b93692295` | profile image/1 |
| `spec/X-C2PA-EXPORT.md` | 7461 | `2b3421f5dd51cc885762754d0ce865c6ee5b9cc11428d8a7945f59a2b7485306` | the C2PA export extension of the reference profiles |
| `spec/conventions-map.image.json` | 2416 | `ae4116c7c5c61b6342e0ecdc875ed42015179254e7012007cfe1e3c3b0b273cc` | profile image/1 |
| `spec/conventions-map.json` | 9269 | `1d0aa2edcb95dda2ddf366248d9572dedc2cc81ff6954920b131812ef43b7b37` | the manifest, conventions and worked examples of profile 3d-entity/1 |
| `spec/examples/MANIFEST.example.json` | 20080 | `c421d2e85a9455f0be794ca8ee673f727a7ef67485d631e374f95c4a6d6ce61a` | the manifest, conventions and worked examples of profile 3d-entity/1 |
| `spec/examples/gsplat.example.hex.txt` | 9796 | `e5cc7d5b0310543cb06b2853d3e6ca5b19f68df9474ecf916b1a256f906788a3` | a node family of profile 3d-entity/1 (animation, audio, physics, geometry, imposters, materials, properties) |
| `spec/examples/gsplat.example.wkgs` | 1120 | `9a3af3dfde695e34cbeb8972a8d3f2453454226ba6ab9c69a6c5a0a199fe19ee` | a node family of profile 3d-entity/1 (animation, audio, physics, geometry, imposters, materials, properties) |
| `spec/examples/make-examples.py` | 57655 | `9b7503dd774b7a9d68f8d42e8428353a5d98db826d408a15c37778f116b7ad40` | the manifest, conventions and worked examples of profile 3d-entity/1 |
| `spec/examples/restposes.example.hex.txt` | 4308 | `80bfad056ad4e2da65517da2486d2706216642dec603dd26cb3074125824d051` | the canonical humanoid skeleton and rest poses of profile 3d-entity/1 |
| `spec/examples/restposes.example.wkrp` | 560 | `6c2c44d5492a4e4f1dbcf5b4c30beb5ada4825ffba7ab7e5010040494ee15f95` | the canonical humanoid skeleton and rest poses of profile 3d-entity/1 |
| `spec/extensions/x.cub.v1.baked.layout.txt` | 9359 | `ba64dfd8bf845e128216e132fa05bad979f65fd66c2c3fa0eccdab7ce95aea71` | the x.cub.v1 extension of profile 3d-entity/1 |
| `spec/extensions/x.cub.v1.md` | 8783 | `0b36de4fa7783301d49dd20483fd43ed7a12e4f06b22c54282981391912b5f42` | the x.cub.v1 extension of profile 3d-entity/1 |
| `spec/facets.json` | 11978 | `f73949dd1cab2d827148eef12c4fa56017b4b06fdd4566f89a561ee5ef7dbba1` | the facet index of profile 3d-entity/1 |
| `spec/layouts/animclip.layout.txt` | 16800 | `ee4a9db15b32a3540fc4dabbc07cf9f91e3f24b3bdad6d0f02711da9e674b9e6` | a node family of profile 3d-entity/1 (animation, audio, physics, geometry, imposters, materials, properties) |
| `spec/layouts/flowfield.layout.txt` | 6263 | `f8d2e9cc571b22fa0748dcb8cb47aa3235d8cfcea92467801a18ddf2b104903a` | a node family of profile 3d-entity/1 (animation, audio, physics, geometry, imposters, materials, properties) |
| `spec/layouts/gsplat.layout.txt` | 23918 | `1f42951c887259e9c69c1437792b5674e0d0c7d90595e41e207c0aac138a6195` | a node family of profile 3d-entity/1 (animation, audio, physics, geometry, imposters, materials, properties) |
| `spec/layouts/imposter.layout.txt` | 10446 | `29649f2aa83078fbb13731f0481eb8e26c96f9ea54a821a6dfbef805ed31236f` | a node family of profile 3d-entity/1 (animation, audio, physics, geometry, imposters, materials, properties) |
| `spec/layouts/points.layout.txt` | 16663 | `6b36a38432a4468655c0c176c02788b39c23db8ea33e2b3af69011a4d59c4899` | a node family of profile 3d-entity/1 (animation, audio, physics, geometry, imposters, materials, properties) |
| `spec/layouts/restposes.layout.txt` | 5958 | `cc2d00b870a12ccedf76ac1fbd61dc5b19712e8c067c2d0f85f50033620efaf5` | the canonical humanoid skeleton and rest poses of profile 3d-entity/1 |
| `spec/layouts/skeleton.layout.txt` | 5964 | `f9656db427660fd781cb7d3732013ff6958f3b816cc9ba93403e37b6e1295dc1` | the canonical humanoid skeleton and rest poses of profile 3d-entity/1 |
| `spec/schemas/core.anim.clip.schema.json` | 9585 | `2e3d87f8447bd3ab21da0c0b34ad0ab24e95bcd4cfb28a4ba2edfdddadbafc36` | a node family of profile 3d-entity/1 (animation, audio, physics, geometry, imposters, materials, properties) |
| `spec/schemas/core.audio.effect.schema.json` | 8628 | `04ec3b581af20448c0a0e4ea093101e46e8079b0e07c87c9aafdf32415e9efd5` | a node family of profile 3d-entity/1 (animation, audio, physics, geometry, imposters, materials, properties) |
| `spec/schemas/core.audio.package.schema.json` | 7320 | `d45aa59c656693f9bf93c09245b9d80e6101d06e765f63215f4faa6116670545` | a node family of profile 3d-entity/1 (animation, audio, physics, geometry, imposters, materials, properties) |
| `spec/schemas/core.destruct.schema.json` | 6319 | `87142e399b83e6f5abffe8655302d45f27b32781766f0821826accb41e97ff32` | a node family of profile 3d-entity/1 (animation, audio, physics, geometry, imposters, materials, properties) |
| `spec/schemas/core.imposter.schema.json` | 6708 | `5b5c3875a91274e38e41e99a55d3041438c0471a584699290c7a6b76ce9f6306` | a node family of profile 3d-entity/1 (animation, audio, physics, geometry, imposters, materials, properties) |
| `spec/schemas/core.material.schema.json` | 4823 | `487505e761fc02d5cd8cde8494a7ede233b4d6edc3ee57d8e9c8c6e68590baa6` | a node family of profile 3d-entity/1 (animation, audio, physics, geometry, imposters, materials, properties) |
| `spec/schemas/core.phys.body.schema.json` | 6157 | `d0d462fc17e21805da5c075fd83eeccda4946367c5f4381651544b89555de4ac` | a node family of profile 3d-entity/1 (animation, audio, physics, geometry, imposters, materials, properties) |
| `spec/schemas/core.phys.bounds.schema.json` | 3164 | `acf0c228fd2b4b4cc46771b85af5bd62c49d14e88468c7b268d07f4e8f0e3a2e` | a node family of profile 3d-entity/1 (animation, audio, physics, geometry, imposters, materials, properties) |
| `spec/schemas/core.phys.colliders.schema.json` | 4116 | `70dd20d638bef9146588222bec3000ab9e0d2430d1dd96fbfda6a5ffacd62794` | a node family of profile 3d-entity/1 (animation, audio, physics, geometry, imposters, materials, properties) |
| `spec/schemas/core.props.schema.json` | 11666 | `95a8124f54346735946431d7de34cb665eec8ca7450a794831d6aee99affa2e3` | a node family of profile 3d-entity/1 (animation, audio, physics, geometry, imposters, materials, properties) |
| `spec/schemas/core.retarget.bind.schema.json` | 13337 | `e8cacdd8a72e7e33100507cbe187ffe91f0ec98516bb52ea08ee6addf298f480` | the canonical humanoid skeleton and rest poses of profile 3d-entity/1 |
| `spec/schemas/core.skeleton.schema.json` | 11464 | `7e0f7aec2a7616e7ab4d94c96ac82cf3496af2d3758b9bbf13d866663782c7f8` | the canonical humanoid skeleton and rest poses of profile 3d-entity/1 |
| `spec/schemas/facets.schema.json` | 3593 | `6a5304c901b8f3c2ff30734c0784fa074a111a4312b634b74351cbe234299f87` | the facet index of profile 3d-entity/1 |
| `spec/schemas/manifest.image.schema.json` | 28381 | `3c6bad61fd8be8f6e7c228c7c68ebd58a725e59e37a4ed219e28e6f530dc5533` | profile image/1 |
| `spec/schemas/manifest.schema.json` | 46174 | `d649cb09a8cfe1b16d27c3d8b910b0cccc074ef9b08dbfed788a51e09f8bf451` | the manifest, conventions and worked examples of profile 3d-entity/1 |
| `spec/schemas/x.c2pa.export.schema.json` | 4935 | `bc1a5c7486f4c90e5331316e122d26f82680601e53bce7142d9b59576ab4600d` | the C2PA export extension of the reference profiles |
| `spec/skeleton/canonical-humanoid-v1.json` | 21250 | `c9543cd8b3f89d8c8e704b866f96fa2cc77fd4ba3eef3b7b56699dd5be21d1c6` | the canonical humanoid skeleton and rest poses of profile 3d-entity/1 |
| `spec/skeleton/core.hands.v1.json` | 24702 | `23dd1a6cb1e78439966328f3aa5090ef8e8fd24888851e4b78e972d5e4d1182f` | the canonical humanoid skeleton and rest poses of profile 3d-entity/1 |
| `spec/skeleton/derive-canonical-humanoid.py` | 19852 | `20f5c3504c87f9c56ae82120fcdb5f006bd565194576e4b818452934069d6c35` | the canonical humanoid skeleton and rest poses of profile 3d-entity/1 |

484404 bytes in all. The sections of `spec/SPEC.md` that concern only those families are 3.2-3.7, 3.9, 3.10,
3.14-3.16, 4 and 8, and section 10.2 as far as it describes `spec/conventions-map.json`; everything else in
`spec/SPEC.md` applies to this package as `spec/CRAFT-BASE.md` says.
