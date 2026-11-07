stories15M — a language model that carries its own engine
=========================================================

This is a werk package: ONE FILE that carries an artifact and everything needed
to understand it. This particular one carries a language model, and "everything
needed to understand it" was taken literally.

WHAT IS IN HERE

  model/stories15M.bin       the weights. 15 191 712 parameters, f32, 58 MB.
  model/tokenizer.bin        the vocabulary. 32 000 entries.
  tools/llama2c/             the COMPLETE SOURCE of a runtime that runs it:
                             ~970 lines of C99, no dependencies, no build
                             system, no network.
  spec/layouts/              a byte-exact grammar for each of the two binary
                             formats above.
  testvectors/               what the model MUST produce, deterministically,
                             so you can tell "it ran" from "it ran correctly".
  spec/                      the werk format specification itself.
  loaders/                   three single-file, dependency-free readers for
                             this container: one Python, one Rust, one C.
  recipe/, disclosure/, provenance/, LICENSE
                             where the weights came from, what is model output
                             and what is not, and the three licences that meet
                             in this file.

HOW TO GET TEXT OUT OF IT

  1. Extract. It is a store-mode zip; any zip tool works, or use
     loaders/werk_read.py, which needs nothing but a Python interpreter.
  2. Read tools/llama2c/BUILD-AND-RUN.md. It has the exact compile command for
     each platform, says which of them were measured and on what machine, and
     says which one is upstream's and was not measured here.
  3. Build the runtime from source. There is no binary in this package.
  4. Run it. The invocation is in BUILD-AND-RUN.md §3 and in
     testvectors/vectors.json as an argv array.
  5. Check your output against testvectors/vectors.json. That step is the
     point of the package: a runtime that reads the weights at the wrong
     offsets still emits confident English, and only the vector catches it.

NOTHING HERE RUNS ITSELF

There is no compiled artifact anywhere in this package, and no werk tool
executes anything it finds in one. spec/SPEC.md §7.1 is the rule: source is
always allowed and reading it is the point; a prebuilt binary is inert data and
is never executed automatically under any circumstance, including a valid
signature. This package has no prebuilt binary at all, so every executable byte
you end up with is one you produced from source you can read.

A NOTE ON THE PROFILE

This package declares `profile: "model/1-draft"`. THAT PROFILE DOES NOT EXIST as
a ruled part of the werk specification. It was drafted while building this file,
because the file had nowhere to declare what it was, and the draft is carried
here at spec/PROFILE-MODEL-DRAFT.md together with the manifest schema it
validates against (spec/schemas/manifest.model-draft.schema.json). Section 5 of
the draft lists five places where the existing core doctrine does not fit a
model package — a missing `train` role, a hermeticity rule no model package can
satisfy, a disclosure axis that has one dimension where a model has two, a tool
role vocabulary with no word for "executor", and the absence of the node types
this package had to declare in the `x.` namespace. None of them are fixed. They
were found by building this, which is what fixtures are for.

WHAT THIS PACKAGE IS NOT

Not a benchmark: the test vectors check that execution is CORRECT, not that the
model is good. It is a 15 M-parameter story completer trained on a synthetic
children's-story corpus and it will happily contradict itself in the third
sentence.

Not a training record: the weights are the output of a run this package did not
perform and cannot reproduce. recipe/recipe.json says so, in the format's own
vocabulary, with `reproducibility: "descriptive"`.

Not fast: the carried runtime is scalar C on one core, measured at ~94 tokens
per second. Optimised executors are somebody's product and an extension-tier
concern by design; base doctrine's job is that a stranger can get output at all.
