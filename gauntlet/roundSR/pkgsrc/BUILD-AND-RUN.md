# BUILD AND RUN — the runtime this package carries

This package contains a language model and the complete source of a runtime
that executes it. This file is the exact procedure: what to compile, with what
command, and what to run to get text out. Every command below is quoted as it
was actually typed; the ones marked **VERIFIED** were run by the package's
author on the machine described in §5 and their output is what
`testvectors/vectors.json` records.

Nothing here is executed for you and nothing in this package executes itself.
`spec/SPEC.md` §7.1 is the rule and it is not softened here: source is always
allowed and reading it is the point; a compiled artifact is inert data. There is
no compiled artifact in this package — every executable byte you end up with,
you produced.

## 1. What you need out of the package

Extract the whole package (it is a store-mode zip; any zip tool, or the
zero-dependency reader in `loaders/`). Four paths matter:

| path | what it is |
|---|---|
| `tools/llama2c/run.c` | the whole runtime, ~970 lines of C99, no dependencies beyond the standard library and libm |
| `tools/llama2c/win.h`, `tools/llama2c/win.c` | a Windows shim providing `mmap`/`munmap`/`clock_gettime`. Needed on Windows ONLY; `run.c` includes `win.h` behind `#if defined _WIN32` |
| `model/stories15M.bin` | the weights, 60 816 028 bytes, f32. Layout: `spec/layouts/llama2c-checkpoint.layout.txt` |
| `model/tokenizer.bin` | the vocabulary, 433 869 bytes. Layout: `spec/layouts/llama2c-tokenizer.layout.txt` |

Toolchain: any hosted C99 compiler. Nothing is downloaded, nothing is
installed, there is no build system, no makefile is required and no network
access is needed at any point.

## 2. Build

Run these from the extracted package root.

### 2a. POSIX — Linux, macOS, WSL, MSYS2's UCRT/MSYS shells

```
cc -O3 -o run tools/llama2c/run.c -lm
```

`win.c` is NOT compiled on POSIX and MUST NOT be: `run.c` takes the
`<sys/mman.h>` branch there. This is upstream llama2.c's own build line
(`gcc -O3 -o run run.c -lm`, from its README, which this package carries at
`recipe/inputs/llama2c-README.md`). **NOT VERIFIED HERE** — the machine in §5
is Windows and had no working POSIX C compiler on it, so this command is
reported as upstream's, unmeasured, and is labelled that way rather than
claimed. If it fails for you, that is a fact worth reporting; the two commands
below are the ones that were measured.

### 2b. Windows, MSVC — **VERIFIED**

From a shell where `cl.exe` is on PATH (run `vcvars64.bat` from your Visual
Studio installation first, or use a "x64 Native Tools Command Prompt"):

```
cl /nologo /O2 /Fe:run.exe tools\llama2c\run.c tools\llama2c\win.c
```

Both `.c` files. `win.c` supplies `mmap`, `munmap` and `clock_gettime`, which
`run.c` calls and which Windows does not have. Measured: exit 0, one warning-free
`Generating Code...`, a 218 624-byte `run.exe`.

### 2c. Windows, mingw-w64 gcc — **VERIFIED TO FAIL, UNMODIFIED**

```
gcc -O3 -o run.exe tools/llama2c/run.c tools/llama2c/win.c -lm
```

does **not** build with mingw-w64 gcc 15.2.0. Measured, both errors, verbatim:

```
win.c:136: error: passing argument 4 of 'VirtualProtect' from incompatible
           pointer type   (uint32_t * vs PDWORD, i.e. unsigned long *)
win.c:175: error: redefinition of 'clock_gettime'
           (mingw's own <pthread_time.h> already defines it inline)
```

Neither is a werk problem and neither is fixed here, because fixing it would
mean shipping a `win.c` whose bytes are not the ones its author published — and
then this package's `sha256` for that file would no longer match upstream, which
is the one property that lets a stranger check where the code came from. The
two changes a consumer needs, if a mingw build is what they want, are one cast
and one `#if !defined(__MINGW32__)` guard, both inside `win.c`, both outside the
scope of this package. Use §2b instead.

Suppressing the first error with `-Wno-incompatible-pointer-types` and renaming
the second with `-Dclock_gettime=...` was also tried, and also fails: the rename
applies to mingw's own inline definition too. Recorded so nobody spends the
twenty minutes again.

## 3. Run

```
./run model/stories15M.bin -z model/tokenizer.bin -t 0.0 -n 64 -i "Once upon a time"
```

(on Windows, `run.exe model\stories15M.bin -z model\tokenizer.bin -t 0.0 -n 64 -i "Once upon a time"`)

Flags that matter:

| flag | meaning |
|---|---|
| first positional | path to the checkpoint. Required. |
| `-z <path>` | tokenizer path. **Required here**, because run.c's default is `tokenizer.bin` in the CURRENT DIRECTORY and this package puts it in `model/`. Omitting it is the single most likely way to fail. |
| `-t <float>` | temperature. **`-t 0.0` selects greedy argmax and makes the run deterministic.** Any other value samples and the output will not match the test vectors. |
| `-n <int>` | number of steps. |
| `-i <string>` | the prompt. |
| `-s <int>` | RNG seed. Irrelevant at `-t 0.0`; the sampler is never consulted. |

The generated text goes to **stdout**. A timing line (`achieved tok/s: …`) goes
to **stderr** and is not part of any test vector.

## 4. Check your result against the package

`testvectors/vectors.json` is the correctness anchor. It records, for two
temperature-0 runs, the exact command line, the exact stdout, its sha256, and
the exact sequence of token ids. Verify like this:

1. Run the command in `vectors[i].argv`.
2. Take stdout, **replace CRLF with LF**, and compare against
   `vectors[i].stdout_text` — or hash it and compare against
   `vectors[i].stdout_sha256_lf`.
3. It should match byte for byte.

The CRLF normalisation is not a fudge. `run.c` writes to a text-mode stream, so
the newlines inside the generated story come out as `\n` on POSIX and `\r\n` on
Windows from an identical model computation. The hash is therefore declared over
the LF form and the byte count of the LF form is given too
(`stdout_bytes_lf`). The raw Windows-console hash of the first vector is
recorded separately as `stdout_sha256_crlf` so that the normalisation can itself
be checked rather than taken on trust.

`vectors[i].token_ids` is the stronger anchor: token ids are integers and no
newline convention touches them. They were captured by a two-line
instrumentation of `run.c`, and that instrumentation travels in this package as
`testvectors/tokens_instrumentation.diff` so you can reproduce the capture
instead of believing it. **The unmodified `run.c` does not print token ids** —
matching `stdout_sha256_lf` is the check you can do without patching anything,
and it is sufficient.

### If it does not match

Floating-point summation order is the expected cause and it is a real one: the
runtime is scalar C, but a compiler is free to vectorise the reductions in
`rmsnorm`, `softmax` and `matmul`, and `-ffast-math` or an aggressive `-O` on a
different target will reassociate them. A greedy argmax over 32 000 logits is
usually robust to that, and it is not guaranteed to be. So:

* a run that matches **is** strong evidence the whole chain is right;
* a run that **diverges after N tokens** is evidence of arithmetic reassociation,
  not necessarily of a broken reader. Report N and your compiler flags.
* a run that produces **fluent English but a different story from token 1** means
  the prompt encoding differs — check §5 of the tokenizer layout grammar (the
  BOS token and the dummy-prefix space).
* a run that produces **garbage from token 1** means the weights are being read
  at the wrong offsets — check the dead RoPE tables in §4 of the checkpoint
  layout grammar.

## 5. The machine the vectors were produced on

Recorded because "it matched" is only a measurement if you know against what.

| | |
|---|---|
| OS | Microsoft Windows 10 Enterprise, 10.0.19045, x64 |
| CPU | AMD Ryzen Threadripper 3970X (32 core) |
| compiler | Microsoft (R) C/C++ Optimizing Compiler Version **19.38.33143** for x64 (Visual Studio 2022 Community) |
| build command | `cl /nologo /O2 /Fe:run.exe run.c win.c` |
| binary | `run.exe`, 218 624 bytes |
| throughput | 93.75 tok/s on vector 1, 94.51 tok/s on vector 2 (from the runtime's own stderr line) |

No GPU is involved anywhere. This is a 15 M-parameter model in f32 on one CPU
core.

## 6. What this package does NOT contain

Stated so nobody looks for it:

* **no training code and no training data.** The weights are the output of a
  training run this package did not perform and cannot reproduce.
  `recipe/recipe.json` records what is known about that run — the architecture,
  the dataset by name, the publisher — with `reproducibility: "descriptive"`
  and an `unrecorded[]` list, which is the format's way of saying "this is a
  truthful record and it is not a reproduction recipe".
* **no compiled binary.** By doctrine, see the top of this file.
* **no quantised variant.** The checkpoint is f32 throughout.
* **no chat template.** `run.c` has a `-m chat` mode; the model in this package
  is a story completer trained on TinyStories and was never instruction-tuned,
  so chat mode will produce a story with the chat scaffolding wrapped around it.
