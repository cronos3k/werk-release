# x.c2pa.export — the intended C2PA mapping, and what it is not

Status: **STUB. Nothing here has been implemented, generated or validated.**
Schema: `spec/schemas/x.c2pa.export.schema.json`.
This document exists so that the intent is written down honestly rather than
implied by a logo.

---

## 1. What has actually been done

| | |
|---|---|
| A mapping table has been written | **yes** — section 3 below |
| A C2PA manifest has ever been emitted by a werk tool | **no** |
| Any mapping here has been run through a C2PA validator | **no** |
| The C2PA specification text was consulted while writing this | **no** — it was written from the author's working knowledge of C2PA 2.x, offline, and is therefore a first draft to be checked against the specification before anyone relies on a single row of it |
| werk's signature chain is a C2PA claim signature | **no**, and section 4 says why that is a *different* model rather than a worse one |

Every row above is the reason this node type lives in `x.*` and not in
`core.*`. Law 12: a reader that does not know `x.c2pa.export` skips it and
loses nothing, and no `core.*` node depends on it. If the mapping turns out to
be wrong in every row, the format is unharmed.

## 2. Why map at all, and where the line is

C2PA and werk answer different questions and the overlap is smaller than it
first looks.

* C2PA answers **"can a consumer trust this provenance claim?"** — hence
  certificates, trust lists, hard bindings to the pixels, and a validation
  status that a viewer is expected to act on.
* werk answers **"is everything needed to understand and re-make this thing
  inside the file?"** — hence the recipe, the embedded input media, the
  layout grammars, the bootstrap readers.

So the export direction that makes sense is **werk → C2PA**: a werk package
knows more about how a thing was made than a C2PA manifest has fields for, and
exporting the subset C2PA can express costs nothing and loses detail
predictably. The reverse direction — importing a C2PA manifest into a werk
package — is *not* mapped here, because a C2PA manifest arrives with an
external trust context (which certificate, which trust list, validated when)
that a hermetic file cannot carry without lying about what it can check.

The doctrine of `core.disclosure` applies unchanged and is worth restating in
this context: **the format ships facts; the viewer applies jurisdiction.**
An exported C2PA manifest would be one more set of facts. It would still be
the viewer's business what to do about them.

## 3. The mapping, first draft

| werk | C2PA (as understood, unverified) | fidelity | note |
|---|---|---|---|
| `core.disclosure` → `ai_generated: true` | an action whose `digitalSourceType` is the IPTC *trainedAlgorithmicMedia* term | approximate | C2PA describes the source *type* of an asset; werk describes whether a model produced the content. The two coincide for a whole-work generation and diverge for `generation_scope: "partial"`. |
| `core.recipe` → `steps[].model.id` | `c2pa.actions` → the acting software agent for that action | lossy | a chain of several model steps flattens into a list of actions; werk's step ordering and per-step inputs have no direct counterpart. |
| `core.recipe` → `steps[].inputs[]` (embedded media) | `c2pa.ingredient` assertions | lossy | C2PA ingredients reference other assets, normally by hash and often by URL. werk *carries* the input bytes. Exporting keeps the hash and drops the guarantee. |
| `core.recipe` → `steps[].prompt.positive` | a custom assertion, or a generative-AI action parameter | approximate | there is no stable, universally-implemented place for a prompt. Anything chosen here is a bet. |
| `core.recipe` → `reproducibility` | *(nothing)* | — | see gaps. |
| `core.provenance` → producers, inputs, costs | `c2pa.actions` + custom assertions | lossy | |
| manifest per-file `sha256` | `c2pa.hash.data` style hard binding | approximate | werk hashes every file in a package and binds them through the manifest; C2PA binds a claim to one asset's bytes. A package is not an asset. |
| `SIGNATURE.json` chain | claim signature | **not equivalent** | see section 4. |
| `license` (embedded full text) | a rights assertion | lossy | C2PA rights assertions normally reference a licence; werk embeds the text, because law 7 forbids the link. |
| `core.semantics`, `core.embedding` | *(nothing)* | — | see gaps. |

## 4. The signature gap, stated plainly

werk's `SIGNATURE.json` chain proves that **the named keys signed the named
manifest states**. It has no root of trust — `SPEC.md` §6 says so in the file
itself. C2PA's claim signature is validated against a certificate chain and a
trust list, and a C2PA viewer is expected to *act* on the validation result.

These are not the same claim with different strength. They are different
claims:

* werk: *this content and this key go together, and here is the whole history
  of who signed what.* Whether the key belongs to someone you trust is a
  question the file explicitly refuses to answer.
* C2PA: *an authority you already trust vouches that this signer is who they
  say they are.*

A werk → C2PA export therefore **cannot** carry the werk chain across as a
claim signature. It would have to be re-signed by a certificate the exporter
holds, and the werk chain would travel — if at all — as an assertion *about*
signatures rather than as a signature. Any tool that implies otherwise is
misreporting both formats.

## 5. Gaps, both directions

**werk facts with no C2PA counterpart**

* The `reproducibility` grade (`deterministic` / `stochastic` /
  `descriptive`) and its mandatory reason. This is the single most useful
  field in `core.recipe` and there is nowhere to put it.
* The `unrecorded[]` array — the explicit list of what was *not* captured.
* Embedded input media as *payload* rather than as a reference.
* Layout grammars, embedded schemas, bootstrap readers: the whole
  self-description layer (law 2) has no analogue, because C2PA is not trying
  to make a file readable in fifty years, it is trying to make a claim
  checkable today.
* Multiple coexisting versions of one node (law 6).
* `core.embedding` and `core.semantics`.

**C2PA obligations werk does not meet**

* A certificate chain and a trust list, and the validation status that
  follows from them (section 4).
* A hard binding to one asset's bytes, and the manifest-store-inside-the-file
  placement rules that go with it (JUMBF boxes in JPEG/PNG/etc.). A werk
  package is a container of many files; a C2PA manifest is normally embedded
  in the asset itself.
* Redaction and the rules governing what a later actor may remove from a
  claim. werk has compaction (law 6: explicit, signed, logged) which is a
  related idea with different semantics.
* Anything about identity assertions.

## 6. If someone implements this

Three requirements, in this order:

1. Read the C2PA specification and rewrite section 3 against the text. Treat
   the current table as a set of hypotheses, and expect several rows to be
   wrong.
2. Emit a manifest and run it through a real validator. Record the result in
   the node's `validation` block; set `status` to `generated-unvalidated`
   until a validator has actually accepted it.
3. Keep the export out of `core.*`. The moment werk's constitution needs
   another consortium's schema to be complete, law 1 has been broken from the
   inside.
