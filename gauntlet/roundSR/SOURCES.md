# roundSR — upstream sources, licences, and how to rebuild the fixture

`gauntlet/roundSR/selfrun-v1.werk` carries five third-party files. They are
carried **byte-identical** to their publishers' distributions, so every sha256
below can be compared against upstream by anyone. `data/` is `.gitignore`d — the
publishers' bytes are theirs and this repository does not redistribute them
outside the fixture — so the fetch is recorded here instead.

## What was fetched, on 2026-08-09

| package path | source | bytes | sha256 |
|---|---|---:|---|
| `model/stories15M.bin` | `https://huggingface.co/karpathy/tinyllamas/resolve/main/stories15M.bin` | 60 816 028 | `cd590644d963867a2b6e5a1107f51fad663c41d79c149fbecbbb1f95fa81f49a` |
| `model/tokenizer.bin` | `https://raw.githubusercontent.com/karpathy/llama2.c/master/tokenizer.bin` | 433 869 | `50a52ef822ee9e83de5ce9d0be0a025a773d019437f58b5ff9dcafb063ece361` |
| `tools/llama2c/run.c` | `https://raw.githubusercontent.com/karpathy/llama2.c/master/run.c` | 38 545 | `9c4f2d5c6ae01b71726d1cc37530d71e60bff0ec7cc012565f16a43c1ca658bd` |
| `tools/llama2c/win.h` | `https://raw.githubusercontent.com/karpathy/llama2.c/master/win.h` | 1 612 | `718d5c4d246a4262e7b8c6caaf7191d3e5d6d73050ec4c54a75916c00df1d833` |
| `tools/llama2c/win.c` | `https://raw.githubusercontent.com/karpathy/llama2.c/master/win.c` | 6 142 | `33a6df145d7c7ad3ff444b61795d54f2823ab04e5705a80e9c89abdbb165abd4` |
| `tools/llama2c/LICENSE-llama2c.txt` | `https://raw.githubusercontent.com/karpathy/llama2.c/master/LICENSE` | 1 063 | `e87b912002f04cdfa837eaf7f70548ab79b9cb62a285495edf575f3da875aec4` |
| `recipe/inputs/llama2c-README.md` | `https://raw.githubusercontent.com/karpathy/llama2.c/master/README.md` | 35 271 | *(in the manifest)* |
| `recipe/inputs/tinyllamas-model-card.md` | `https://huggingface.co/karpathy/tinyllamas/raw/main/README.md` | 205 | `f5d36081d79fc18b2b8ee80fbf05f307c30ea8d6f3ce605c3f393be29f7d8863` |

## Licences

**llama2.c — MIT.** "Copyright (c) 2023 Andrej". The licence file is carried in
the package at `tools/llama2c/LICENSE-llama2c.txt`, verbatim.

**stories15M.bin — MIT, by the publisher's assertion.** There is **no LICENSE
file** in `karpathy/tinyllamas`. What exists is the model card's YAML front
matter (`license: mit`) and the Hugging Face metadata echoing it. The card is
carried verbatim at `recipe/inputs/tinyllamas-model-card.md` so the assertion
travels rather than a paraphrase of it. This is the S12-9 lesson applied
forward: the fixture is handable to a stranger, and the *form* of the grant is
stated, not smoothed over.

**TinyStories (the training corpus) — not carried, terms not established here.**
Published separately by its own authors under its own terms. The package names
it in `recipe/recipe.json`'s `unrecorded[]` and in §3 of its `LICENSE`, and
grants nothing in respect of it.

`git log` for the exact llama2.c revision: not recorded. The files were fetched
from `master` by URL, not from a clone, so the commit id was never in hand.
`repository.revision` in the `core.tool` node says `not-recorded`, which is the
schema's legal honest value, and this sentence is why.

## Rebuilding

```
mkdir -p data/selfrun && cd data/selfrun
curl -sSLO https://raw.githubusercontent.com/karpathy/llama2.c/master/run.c
curl -sSLO https://raw.githubusercontent.com/karpathy/llama2.c/master/win.h
curl -sSLO https://raw.githubusercontent.com/karpathy/llama2.c/master/win.c
curl -sSLO https://raw.githubusercontent.com/karpathy/llama2.c/master/LICENSE
curl -sSLO https://raw.githubusercontent.com/karpathy/llama2.c/master/README.md
curl -sSLO https://raw.githubusercontent.com/karpathy/llama2.c/master/tokenizer.bin
curl -sSL -o stories15M.bin https://huggingface.co/karpathy/tinyllamas/resolve/main/stories15M.bin
curl -sSL -o tinyllamas-README.md https://huggingface.co/karpathy/tinyllamas/raw/main/README.md
cd ../.. && sha256sum data/selfrun/*        # compare against the table above
python gauntlet/roundSR/build_selfrun_fixture.py
python gauntlet/roundSR/verify_selfrun.py
```

Everything else the package needs is committed: `gauntlet/roundSR/pkgsrc/`
(the two layout grammars, the draft profile, `BUILD-AND-RUN.md`, the licence
notice, the readme), `vectors.json`, the two expected-stdout files and
`tokens_instrumentation.diff`.

**The build is deterministic.** Rebuilt from the committed authored sources
against the same upstream bytes it produces the same 62 525 273 bytes and the
same sha256 (`1f8e1270…d51f17`) — measured, twice, on 2026-08-09.

If upstream `master` has moved since, the hashes will differ and the build is
still correct — it will simply be a different fixture, and the table above is
what says so. Re-pin `gauntlet/roundSR/fixture-pin.json` in that case rather
than editing this table.

## Regenerating the test vectors

`vectors.json` is **measured output**, not authored. It was produced by
building the runtime and running it twice; `make_vectors.py` assembles the JSON
from those runs. Regenerating it needs a C compiler and the two runs described
in `pkgsrc/BUILD-AND-RUN.md` §2b and §3, plus the instrumented build described
by `tokens_instrumentation.diff` for the token ids. On any machine other than
the one recorded in `vectors.json`'s `environment`, expect the *text* to match
and record it if it does not — that is the measurement the vector exists to
enable.
