/* werk.h — the C ABI of werk-core.
 *
 * ONE shared library (werk.dll / libwerk.so / libwerk.dylib) is the whole
 * reference implementation. C and C++ consume this header; Python binds the
 * same library through ctypes with no pip dependencies. There is no second
 * implementation to drift.
 *
 * The format itself is documented in spec/ INSIDE every package. This header
 * documents only the calling convention.
 *
 * ---------------------------------------------------------------------------
 * Rules that will bite you if you skip them
 * ---------------------------------------------------------------------------
 *
 *  1. Every `const char *` and every blob pointer returned here is BORROWED.
 *     It is owned by the werk_package handle and is valid until that handle is
 *     closed or MUTATED. Every mutating call — werk_sign, werk_strip_signature,
 *     werk_stage_file, werk_add_node, werk_append_version — invalidates every
 *     pointer previously handed out for that handle. Copy what you need.
 *     Never free anything this header gives you.
 *
 *  2. A werk_package handle is NOT thread-safe. Use one handle per thread.
 *
 *  3. DAMAGE DOES NOT FAIL A CALL. A package with a corrupt texture and three
 *     unknown node types opens successfully and tells you exactly what died.
 *     That is the island rule (manifesto law 3): check werk_report_* and
 *     werk_node_status, not the return code, to find out what you lost. A
 *     nonzero return means there was no package to speak of.
 *
 *  4. Signatures have THREE states, never two. See werk_signature_state.
 *
 *  5. A prebuilt binary inside a package is INERT DATA. This library will
 *     hash it, list it and hand you its bytes; it will never execute, load,
 *     link or dlopen it, and neither should you without the deliberate,
 *     per-package, user-driven check spec/SPEC.md section 7.1 describes.
 *
 * Build (Windows, from core/):   cargo build --release
 *   -> target/release/werk.dll and target/release/werk.dll.lib
 * Cross-build (from any host with the target installed):
 *   cargo build --release --target x86_64-unknown-linux-gnu   -> libwerk.so
 *   cargo build --release --target aarch64-apple-darwin       -> libwerk.dylib
 * The C ABI is identical on all three; only the file name changes.
 */

#ifndef WERK_H
#define WERK_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#if defined(_WIN32) && defined(WERK_IMPORT)
#  define WERK_API __declspec(dllimport)
#else
#  define WERK_API
#endif

/* --- status codes ------------------------------------------------------- */
/* 0 is success. Negative values are failures; werk_last_error() has detail. */
enum werk_status {
    WERK_OK              =  0,
    WERK_ERR_NOT_FOUND   = -1,  /* the path does not exist                   */
    WERK_ERR_IO          = -2,
    WERK_ERR_CONTAINER   = -3,  /* not a zip and not a directory             */
    WERK_ERR_MANIFEST    = -4,  /* MANIFEST.json absent or not JSON          */
    WERK_ERR_NO_ITEM     = -5,  /* no such node / version / file             */
    WERK_ERR_KEY         = -6,  /* malformed key or signature hex            */
    WERK_ERR_WRITE       = -7,
    WERK_ERR_REJECTED    = -8,  /* the call would break a law (e.g. no note) */
    WERK_ERR_ARGUMENT    = -9,  /* null handle, bad pointer, bad UTF-8       */
    /* Added 2026-10-13 (ruling 9, PROPOSED). Additive: no earlier code moved. */
    WERK_ERR_ZIP64       = -10, /* a zip64 container: refused whole, nothing */
                                /* was read. werk does not use zip64; carry  */
                                /* the package in directory form instead     */
    WERK_ERR_ZIP_METHOD  = -11, /* one entry uses a zip method other than 0  */
                                /* (store) and 8 (deflate), or is encrypted  */
    WERK_ERR_ZIP_ENTRY   = -12  /* one entry is damaged at the zip level: a  */
                                /* deflate stream that does not decode, or   */
                                /* bytes that disagree with the directory    */
};

/* --- open flags --------------------------------------------------------- */
/* Default (0) is the honest, slow thing: verify every hash, interpret every
 * payload, recompute every derived hash. The flags below buy speed by
 * checking less, and a tool that sets them should say which it set. */
enum werk_open_flags {
    WERK_OPEN_DEFAULT        = 0,
    WERK_OPEN_SKIP_VERIFY    = 1u << 0, /* do not hash file contents         */
    WERK_OPEN_SKIP_INTERPRET = 1u << 1, /* do not validate payloads/envelopes*/
    WERK_OPEN_SKIP_DERIVED   = 1u << 2  /* do not recompute input_hash       */
};

/* --- node status -------------------------------------------------------- */
enum werk_node_state {
    WERK_NODE_ALIVE   = 0,
    /* Bytes verified; the type is one this reader does not interpret. Listed
     * and extractable — law 12: you lose that feature and nothing else. */
    WERK_NODE_SKIPPED = 1,
    WERK_NODE_DEAD    = 2
};

/* --- signature state ---------------------------------------------------- */
/* SPEC.md section 6: a tool that collapses ABSENT and INVALID into one
 * warning has defeated the doctrine, so this ABI cannot express the collapse.
 * ABSENT means anonymous, by choice or by stripping, and nothing is broken.
 * INVALID means tampering under an existing signature. */
enum werk_signature {
    WERK_SIG_ABSENT  = 0,
    WERK_SIG_VALID   = 1,
    WERK_SIG_INVALID = 2,
    /* The chain declares an algorithm this library does not implement
     * (SPEC.md section 10.1): not checked, neither valid nor damage. */
    WERK_SIG_UNVERIFIED = 3
};

typedef struct WerkPackage werk_package;

/* --- library ------------------------------------------------------------ */
WERK_API const char *werk_version(void);        /* implementation version    */
WERK_API const char *werk_profile(void);        /* "3d-entity/1"             */
WERK_API const char *werk_last_error(void);     /* thread-local, never NULL  */

/* --- open / close ------------------------------------------------------- */
/* `path` may be a .werk (store-mode zip) OR a directory. Both are the format. */
WERK_API int32_t werk_open(const char *path, uint32_t flags, werk_package **out);
WERK_API void    werk_close(werk_package *pkg);

/* --- package facts ------------------------------------------------------ */
WERK_API const char *werk_entity_name(werk_package *pkg);
WERK_API const char *werk_entity_uuid(werk_package *pkg);
WERK_API const char *werk_package_profile(werk_package *pkg);
/* sha256 of MANIFEST.json's exact bytes, never a reserialisation. */
WERK_API const char *werk_manifest_sha256(werk_package *pkg);
WERK_API const uint8_t *werk_manifest_bytes(werk_package *pkg, size_t *len);
WERK_API int32_t     werk_signature_state(werk_package *pkg);  /* werk_signature */
WERK_API const char *werk_signature_detail(werk_package *pkg);

/* --- load report -------------------------------------------------------- */
/* The report is the point of the API, not an afterthought: it is where a
 * damaged node, an unknown type, a version fallback and a broken signature all
 * announce themselves precisely. */
WERK_API int32_t     werk_report_count(werk_package *pkg);
WERK_API int32_t     werk_report_errors(werk_package *pkg);
WERK_API const char *werk_report_severity(werk_package *pkg, int32_t i); /* info|warn|error */
WERK_API const char *werk_report_code(werk_package *pkg, int32_t i);     /* e.g. "hash-mismatch" */
WERK_API const char *werk_report_node(werk_package *pkg, int32_t i);     /* "" when not node-scoped */
WERK_API const char *werk_report_path(werk_package *pkg, int32_t i);     /* "" when not file-scoped */
WERK_API int32_t     werk_report_version(werk_package *pkg, int32_t i);  /* -1 when not versioned */
WERK_API const char *werk_report_message(werk_package *pkg, int32_t i);

/* --- nodes -------------------------------------------------------------- */
WERK_API int32_t     werk_node_count(werk_package *pkg);
WERK_API int32_t     werk_node_index(werk_package *pkg, const char *node_id);
WERK_API const char *werk_node_id(werk_package *pkg, int32_t n);
WERK_API const char *werk_node_type(werk_package *pkg, int32_t n);
WERK_API int32_t     werk_node_status(werk_package *pkg, int32_t n);     /* werk_node_state */
WERK_API const char *werk_node_status_reason(werk_package *pkg, int32_t n);
WERK_API int32_t     werk_node_active(werk_package *pkg, int32_t n);
/* The version actually usable after any reported fallback; -1 when dead. */
WERK_API int32_t     werk_node_resolved(werk_package *pkg, int32_t n);

/* --- versions (index v is POSITIONAL, 0..werk_version_count-1) ---------- */
WERK_API int32_t     werk_version_count(werk_package *pkg, int32_t n);
WERK_API int32_t     werk_version_number(werk_package *pkg, int32_t n, int32_t v);
WERK_API const char *werk_version_note(werk_package *pkg, int32_t n, int32_t v);
WERK_API const char *werk_version_epistemic(werk_package *pkg, int32_t n, int32_t v);
WERK_API const char *werk_version_created(werk_package *pkg, int32_t n, int32_t v);
WERK_API const char *werk_version_input_hash(werk_package *pkg, int32_t n, int32_t v);

/* --- files -------------------------------------------------------------- */
WERK_API int32_t     werk_file_count(werk_package *pkg, int32_t n, int32_t v);
WERK_API const char *werk_file_path(werk_package *pkg, int32_t n, int32_t v, int32_t f);
WERK_API const char *werk_file_sha256(werk_package *pkg, int32_t n, int32_t v, int32_t f);
WERK_API const char *werk_file_role(werk_package *pkg, int32_t n, int32_t v, int32_t f);
WERK_API const char *werk_file_media_type(werk_package *pkg, int32_t n, int32_t v, int32_t f);
WERK_API uint64_t    werk_file_size(werk_package *pkg, int32_t n, int32_t v, int32_t f);

/* --- blobs -------------------------------------------------------------- */
/* Borrowed pointer + length. See rule 1 above. */
WERK_API int32_t werk_blob(werk_package *pkg, const char *path,
                           const uint8_t **data, size_t *len);

/* --- verify / write ----------------------------------------------------- */
/* Number of ERROR-severity report entries: 0 means every declared hash held. */
WERK_API int32_t werk_verify(werk_package *pkg);
/* Byte-exact re-emission, store mode, preview-first entry order. Re-writing an
 * untouched package reproduces it byte for byte. */
WERK_API int32_t werk_write_zip(werk_package *pkg, const char *dest);
/* Returns the number of files written, or a negative status. */
WERK_API int32_t werk_materialize_dir(werk_package *pkg, const char *dest);

/* --- signing ------------------------------------------------------------ */
/* Appends an Ed25519 entry to the custody chain, or starts one. `signed_at` is
 * RFC 3339 UTC with a Z suffix and IS part of the signed message, so it must be
 * reproduced byte for byte when verifying. `role` and `note` may be "".
 *
 * REFUSAL YOU SHOULD READ: SIGNATURE.json carries ONE manifest_sha256 and every
 * entry signs that same value, so a chain cannot span two manifest states. If
 * the manifest changed after the chain was anchored, this returns
 * WERK_ERR_REJECTED rather than silently producing a file whose earlier links
 * no longer verify. */
WERK_API int32_t werk_sign(werk_package *pkg,
                           const char *secret_key_hex,
                           const char *name, const char *uri, const char *kind,
                           const char *role, const char *note,
                           const char *signed_at);
/* Make the package anonymous. A legitimate state, and a visibly different one
 * from "present and invalid". */
WERK_API int32_t werk_strip_signature(werk_package *pkg);

/* --- mutation ----------------------------------------------------------- */
/* Stage payload bytes first, then describe the node that owns them. */
WERK_API int32_t werk_stage_file(werk_package *pkg, const char *path,
                                 const uint8_t *data, size_t len);

/* spec_json for werk_add_node:
 *   {"node_id":"...","type":"core.tex","part_id":null,"material_id":null,
 *    "meta":{...},"edges":[{"to":"...","kind":"enhances"}],
 *    "version":{"files":[{"path":"...","media_type":"...","role":"..."}],
 *               "note":"why this exists — MANDATORY, >= 8 characters",
 *               "producer":{"tool":"...","version":"..."},
 *               "epistemic":"authored|measured|inferred",
 *               "created":"2026-08-08T09:00:00Z",
 *               "input_files":[...],"input_params":{}}}
 * sha256 and size are computed from the staged bytes; you never declare them.
 * epistemic "measured"/"inferred" REQUIRES a non-empty ordered input_files, and
 * input_hash is computed for you (law 5). A note under 8 characters is
 * rejected (law 6). */
WERK_API int32_t werk_add_node(werk_package *pkg, const char *spec_json);

/* spec_json is the "version" object above. Returns the new version number, or a
 * negative status. The node's `active` moves to the new version. */
WERK_API int32_t werk_append_version(werk_package *pkg, const char *node_id,
                                     const char *spec_json);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* WERK_H */
