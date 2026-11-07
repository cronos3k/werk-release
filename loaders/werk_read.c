/*
 * werk_read.c -- zero-dependency bootstrap reader for the werk artifact
 *                container, profile 3d-entity/1.
 *
 * =====================================================================
 * WHAT THIS FILE IS
 * =====================================================================
 * A werk package carries a working reader inside itself (SPEC.md law 1,
 * section 7).  This is the C one.  It is a *bootstrap* loader: read-only,
 * simplified, deliberately unoptimised, and written to be audited by a
 * human in one sitting.  It is not the reference implementation.
 *
 * It is written FRESH FROM THE SPECIFICATION and shares no code with the
 * Python or Rust loaders that sit beside it in loaders/.  That is on
 * purpose: three independent readers written from the same document are a
 * test of the document.
 *
 * =====================================================================
 * SPECIFICATION FILES THIS IMPLEMENTS
 * =====================================================================
 *   spec/SPEC.md
 *       section 1   container (directory OR store-mode zip; both are the format)
 *       section 2   MANIFEST.json
 *       section 5   versioning, active/fallback, degradation
 *       section 7   embedded loaders, core.loader, the honest capability list
 *       section 10  the reader checklist, steps 1-9
 *   spec/MINI-SPECS.md
 *       section 3   JSON (the restricted profile: no BOM, no comments,
 *                   no trailing commas, no NaN/Infinity, no duplicate keys)
 *       section 5   zip: EOCD, central directory, local file header
 *       section 11  SHA-256 and its three test vectors (--selftest)
 *   spec/schemas/manifest.schema.json
 *       the shape walked below, including $defs/loaderMeta
 *   spec/layouts/ENVELOPE.layout.txt
 *       sections 1-7: magic / u32 LE version / u32 LE header_len /
 *       MessagePack header / declared payload sections   (--envelope)
 *
 * =====================================================================
 * THE CAPABILITIES THIS LOADER DECLARES
 * =====================================================================
 * Honest and narrow beats aspirational (SPEC.md section 7).  The next
 * line is the machine-readable statement of the list, and it is what a
 * writer that embeds this file reads to fill `meta.capabilities`:
 *
 * WERK-LOADER-CAPABILITIES: read-manifest verify-hashes read-envelope materialize
 *
 * The core.loader node meta block for this file is exactly:
 *
 *   "meta": {
 *     "language":      "c",
 *     "form":          "source",
 *     "entrypoint":    "loaders/werk_read.c",
 *     "toolchain":     "c99",
 *     "build_command": "cc -std=c99 -O2 -o werk_read loaders/werk_read.c",
 *     "dependencies":  [],
 *     "capabilities":  ["read-manifest", "verify-hashes", "read-envelope",
 *                       "materialize"]
 *   }
 *
 * It does NOT declare read-geometry, read-textures, read-audio,
 * read-skeleton, read-animation or verify-signature, and it does not
 * pretend to: a PNG needs an inflate implementation
 * (MINI-SPECS.md section 7) and a signature needs Ed25519, which
 * MINI-SPECS.md section 12 explicitly says not to write from a
 * description.  Where a signature is present this reader reports its
 * presence and says, in the same breath, that it did not verify it.  It
 * never reports "signed-and-valid".
 *
 * =====================================================================
 * SAFETY PROPERTIES (audit these first)
 * =====================================================================
 *  * READ-ONLY with respect to the package.  The package file/directory is
 *    opened "rb" and never "wb".  The only bytes this program ever writes
 *    are (a) to stdout, and (b) under the directory given to
 *    --extract --out, which must be somewhere else.
 *  * It NEVER executes anything: no system(), no exec, no dlopen, no
 *    LoadLibrary.  SPEC.md section 7.1 forbids running a packaged binary
 *    and this reader cannot, structurally.
 *  * It never fetches anything: no sockets, no network headers.
 *  * It never follows a path that is not listed in some node version's
 *    files[] (SPEC.md section 10 step 9).  --cat additionally permits
 *    MANIFEST.json and SIGNATURE.json, which by construction are the two
 *    files no node lists.
 *  * Every package-relative path is checked before use: no leading slash,
 *    no drive letter, no backslash, no ".." segment, no embedded NUL.
 *
 * =====================================================================
 * THE ISLAND RULE (SPEC.md section 5, section 10 step 8)
 * =====================================================================
 * A corrupt file, a missing file, an unsupported compression method, a
 * malformed node record or an unknown node type NEVER aborts the load.
 * The node is marked dead or skipped, one precise report line is emitted,
 * and every other node still loads.  A `requires` edge into a dead node,
 * or to a node absent from nodes[], kills the source node too,
 * transitively; an `enhances` edge into a dead or absent node costs
 * exactly one feature and is only reported.
 *
 * Exit status (SPEC.md section 10.1; until ruling 9 of 2026-10-13 this
 * file returned 1 for an unreadable container, which the table calls 2):
 *    0  the container opened and MANIFEST.json parsed -- even if every
 *       node in it is dead.  Dead nodes are a property of the package,
 *       not an error in reading it.
 *    1  the container opened and there is an error: --strict was given
 *       and at least one node is dead, OR a conventions value is one this
 *       reader does not support (SPEC.md section 10 step 3 says refuse,
 *       do not guess), OR --selftest failed.
 *    2  CONTAINER-SCOPED REFUSAL, nothing was loaded: not a zip, a zip64
 *       container, no or unparseable MANIFEST.json.  Also a command line
 *       this program cannot act on -- no package was loaded then either.
 *
 * =====================================================================
 * LIMITS, STATED RATHER THAN HIDDEN
 * =====================================================================
 *  * Zip method 8 (deflate) IS read (ruling 9 of 2026-10-13), by the
 *    inflate in section 5a, written from MINI-SPECS.md section 7.1; the
 *    result is checked against the directory's size and CRC-32 before it
 *    is returned.  Any other method, and an encrypted entry, is refused by
 *    name for that entry only (zip-entry-unsupported), never guessed.
 *  * Zip64 is not implemented and by ruling will not be.  A zip64
 *    container is refused WHOLE and by name (zip64-unsupported, exit
 *    status 2) and nothing is read from it.  A package past the zip32
 *    ceiling is carried in directory form, which is the same format.
 *  * For a profile this file does not have built in it says so in ONE
 *    unsupported-profile line, checks the six base conventions it itself
 *    depends on, and still lists, hash-verifies and extracts every file
 *    (SPEC.md section 10.3).
 *  * The whole of any file being verified is held in memory at once.
 *    Offsets use long, so containers above LONG_MAX bytes are refused.
 *  * The JSON parser is a walker, not a validator.  It enforces the
 *    MINI-SPECS.md section 3 restrictions it can see locally (no BOM, no
 *    duplicate keys, no NaN/Infinity, no comments, no trailing commas) but
 *    it does not check MANIFEST.json against manifest.schema.json.  A
 *    reader that needs schema validation is past the bootstrap stage.
 *  * The only platform-conditional code in this file is directory creation
 *    for --extract and putting stdout into binary mode for --cat.  Both
 *    are isolated in the block immediately below.  Everything else is
 *    plain C99 and the C standard library.
 *
 * =====================================================================
 * BUILD
 * =====================================================================
 *   gcc  -std=c99 -O2 -Wall -Wextra -o werk_read werk_read.c
 *   cl   /nologo /O2 /W3 werk_read.c
 *
 * =====================================================================
 * USAGE
 * =====================================================================
 *   werk_read <package.werk|dir> --list
 *   werk_read <package.werk|dir> --verify
 *   werk_read <package.werk|dir> --report
 *   werk_read <package.werk|dir> --extract <node_id> --out <dir>
 *   werk_read <package.werk|dir> --cat <package/relative/path>
 *   werk_read <package.werk|dir> --envelope <package/relative/path>
 *   werk_read --selftest
 *   (add --strict to any package mode to exit nonzero when a node is dead)
 */

#define _CRT_SECURE_NO_WARNINGS 1

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdarg.h>
#include <stddef.h>
#include <limits.h>

/* ------------------------------------------------------------------ */
/* The entire platform-conditional surface of this file.               */
/* C99 has no way to create a directory and no way to put a stream into*/
/* binary mode, so these two operations, and only these two, need a    */
/* host header.  Everything else below is portable C99.                */
/* ------------------------------------------------------------------ */
#if defined(_WIN32)
#  include <direct.h>            /* _mkdir                      */
#  include <io.h>                /* _setmode, _fileno           */
#  include <fcntl.h>             /* _O_BINARY                   */
#  define WR_MKDIR(p) _mkdir(p)
#  define WR_STDOUT_BINARY() ((void)_setmode(_fileno(stdout), _O_BINARY))
#else
#  include <sys/stat.h>          /* mkdir                       */
#  define WR_MKDIR(p) mkdir((p), 0777)
#  define WR_STDOUT_BINARY() ((void)0)   /* no text mode to escape */
#endif

/* ================================================================== */
/* 1. Small utilities                                                  */
/* ================================================================== */

static void *xmalloc(size_t n)
{
    void *p = malloc(n ? n : 1);
    if (!p) { fprintf(stderr, "werk_read: out of memory\n"); exit(1); }
    return p;
}

static void *xrealloc(void *q, size_t n)
{
    void *p = realloc(q, n ? n : 1);
    if (!p) { fprintf(stderr, "werk_read: out of memory\n"); exit(1); }
    return p;
}

static char *xstrdup(const char *s)
{
    size_t n = strlen(s) + 1;
    char *p = (char *)xmalloc(n);
    memcpy(p, s, n);
    return p;
}

/* A growable list of owned strings, used for the load report. */
typedef struct {
    char  **v;
    size_t  n, cap;
} strlist;

static void sl_init(strlist *s) { s->v = NULL; s->n = 0; s->cap = 0; }

static void sl_push(strlist *s, char *owned)
{
    if (s->n == s->cap) {
        s->cap = s->cap ? s->cap * 2 : 16;
        s->v = (char **)xrealloc(s->v, s->cap * sizeof(char *));
    }
    s->v[s->n++] = owned;
}

static void sl_free(strlist *s)
{
    size_t i;
    for (i = 0; i < s->n; i++) free(s->v[i]);
    free(s->v);
    sl_init(s);
}

/* printf into a freshly allocated string and append it to the list. */
static void sl_addf(strlist *s, const char *fmt, ...)
{
    va_list ap;
    int     need;
    char   *buf;

    va_start(ap, fmt);
    need = vsnprintf(NULL, 0, fmt, ap);
    va_end(ap);
    if (need < 0) return;

    buf = (char *)xmalloc((size_t)need + 1);
    va_start(ap, fmt);
    vsnprintf(buf, (size_t)need + 1, fmt, ap);
    va_end(ap);
    sl_push(s, buf);
}

/* ================================================================== */
/* 2. SHA-256  --  FIPS 180-4                                          */
/*                                                                     */
/* MINI-SPECS.md section 11: 32-bit words, big-endian, message padded  */
/* with 0x80 then zeros then the 64-bit big-endian bit length, block   */
/* size 64 bytes, 64 rounds.  The eight initial state words are the    */
/* fractional parts of the square roots of the first eight primes; the */
/* 64 round constants are the fractional parts of the cube roots of    */
/* the first sixty-four primes.  Both are written out literally so     */
/* that nothing here has to be derived.                                */
/* ================================================================== */

typedef struct {
    uint32_t      h[8];
    unsigned char blk[64];
    size_t        blen;     /* bytes currently buffered in blk */
    uint64_t      total;    /* total message bytes seen        */
} sha256_ctx;

static const uint32_t SHA256_K[64] = {
    0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u,
    0x3956c25bu, 0x59f111f1u, 0x923f82a4u, 0xab1c5ed5u,
    0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u,
    0x72be5d74u, 0x80deb1feu, 0x9bdc06a7u, 0xc19bf174u,
    0xe49b69c1u, 0xefbe4786u, 0x0fc19dc6u, 0x240ca1ccu,
    0x2de92c6fu, 0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau,
    0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u,
    0xc6e00bf3u, 0xd5a79147u, 0x06ca6351u, 0x14292967u,
    0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu, 0x53380d13u,
    0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u,
    0xa2bfe8a1u, 0xa81a664bu, 0xc24b8b70u, 0xc76c51a3u,
    0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u,
    0x19a4c116u, 0x1e376c08u, 0x2748774cu, 0x34b0bcb5u,
    0x391c0cb3u, 0x4ed8aa4au, 0x5b9cca4fu, 0x682e6ff3u,
    0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u,
    0x90befffau, 0xa4506cebu, 0xbef9a3f7u, 0xc67178f2u
};

#define ROTR32(x, n) (((x) >> (n)) | ((x) << (32 - (n))))

static void sha256_block(sha256_ctx *c, const unsigned char *p)
{
    uint32_t w[64], a, b, cc, d, e, f, g, h, t1, t2;
    int      i;

    for (i = 0; i < 16; i++) {
        w[i] = ((uint32_t)p[i * 4    ] << 24) |
               ((uint32_t)p[i * 4 + 1] << 16) |
               ((uint32_t)p[i * 4 + 2] <<  8) |
               ((uint32_t)p[i * 4 + 3]      );
    }
    for (i = 16; i < 64; i++) {
        uint32_t s0 = ROTR32(w[i - 15], 7) ^ ROTR32(w[i - 15], 18) ^ (w[i - 15] >> 3);
        uint32_t s1 = ROTR32(w[i -  2], 17) ^ ROTR32(w[i - 2], 19) ^ (w[i -  2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }

    a = c->h[0]; b = c->h[1]; cc = c->h[2]; d = c->h[3];
    e = c->h[4]; f = c->h[5]; g  = c->h[6]; h = c->h[7];

    for (i = 0; i < 64; i++) {
        uint32_t S1  = ROTR32(e, 6) ^ ROTR32(e, 11) ^ ROTR32(e, 25);
        uint32_t ch  = (e & f) ^ ((~e) & g);
        uint32_t S0  = ROTR32(a, 2) ^ ROTR32(a, 13) ^ ROTR32(a, 22);
        uint32_t maj = (a & b) ^ (a & cc) ^ (b & cc);
        t1 = h + S1 + ch + SHA256_K[i] + w[i];
        t2 = S0 + maj;
        h = g; g = f; f = e; e = d + t1;
        d = cc; cc = b; b = a; a = t1 + t2;
    }

    c->h[0] += a; c->h[1] += b; c->h[2] += cc; c->h[3] += d;
    c->h[4] += e; c->h[5] += f; c->h[6] += g;  c->h[7] += h;
}

static void sha256_init(sha256_ctx *c)
{
    c->h[0] = 0x6a09e667u; c->h[1] = 0xbb67ae85u;
    c->h[2] = 0x3c6ef372u; c->h[3] = 0xa54ff53au;
    c->h[4] = 0x510e527fu; c->h[5] = 0x9b05688cu;
    c->h[6] = 0x1f83d9abu; c->h[7] = 0x5be0cd19u;
    c->blen  = 0;
    c->total = 0;
}

static void sha256_update(sha256_ctx *c, const void *data, size_t len)
{
    const unsigned char *p = (const unsigned char *)data;
    c->total += (uint64_t)len;

    if (c->blen) {
        size_t want = 64 - c->blen;
        size_t take = len < want ? len : want;
        memcpy(c->blk + c->blen, p, take);
        c->blen += take; p += take; len -= take;
        if (c->blen == 64) { sha256_block(c, c->blk); c->blen = 0; }
    }
    while (len >= 64) { sha256_block(c, p); p += 64; len -= 64; }
    if (len) { memcpy(c->blk, p, len); c->blen = len; }
}

static void sha256_final(sha256_ctx *c, unsigned char out[32])
{
    uint64_t      bits = c->total * 8u;
    unsigned char pad[72];
    size_t        padlen;
    int           i;

    /* 0x80, then zeros, so that (total + padlen + 8) % 64 == 0 */
    padlen = (c->blen < 56) ? (56 - c->blen) : (120 - c->blen);
    memset(pad, 0, sizeof pad);
    pad[0] = 0x80;
    for (i = 0; i < 8; i++)
        pad[padlen + i] = (unsigned char)((bits >> (56 - 8 * i)) & 0xffu);
    sha256_update(c, pad, padlen + 8);

    for (i = 0; i < 8; i++) {
        out[i * 4    ] = (unsigned char)((c->h[i] >> 24) & 0xffu);
        out[i * 4 + 1] = (unsigned char)((c->h[i] >> 16) & 0xffu);
        out[i * 4 + 2] = (unsigned char)((c->h[i] >>  8) & 0xffu);
        out[i * 4 + 3] = (unsigned char)((c->h[i]      ) & 0xffu);
    }
}

/* Lowercase hex, 64 characters plus NUL -- the encoding werk uses
   everywhere (MINI-SPECS.md section 11). */
static void sha256_hex(const void *data, size_t len, char out[65])
{
    static const char HEX[] = "0123456789abcdef";
    sha256_ctx    c;
    unsigned char d[32];
    int           i;

    sha256_init(&c);
    sha256_update(&c, data, len);
    sha256_final(&c, d);
    for (i = 0; i < 32; i++) {
        out[i * 2    ] = HEX[(d[i] >> 4) & 0xf];
        out[i * 2 + 1] = HEX[ d[i]       & 0xf];
    }
    out[64] = '\0';
}

static int inflate_raw(const unsigned char *src, size_t n,
                       unsigned char *out, size_t cap, size_t *out_n);

/* The three test vectors of MINI-SPECS.md section 11, plus a fourth
   (one million 'a') that exercises multi-block streaming, plus the three
   DEFLATE vectors of section 7.1.  Returns 0 on success. */
static int sha256_selftest(void)
{
    static const struct { const char *in; const char *want; } V[] = {
        { "",
          "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" },
        { "abc",
          "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad" },
        { "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq",
          "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1" }
    };
    static const char *MILLION_A =
        "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0";

    int  bad = 0;
    int  i;
    char got[65];

    printf("werk_read --selftest : SHA-256, FIPS 180-4\n");
    printf("  vectors from spec/MINI-SPECS.md section 11\n\n");

    for (i = 0; i < (int)(sizeof V / sizeof V[0]); i++) {
        int ok;
        sha256_hex(V[i].in, strlen(V[i].in), got);
        ok = (strcmp(got, V[i].want) == 0);
        if (!ok) bad++;
        printf("  [%s] sha256(%s%.*s%s)\n", ok ? "OK" : "FAIL",
               V[i].in[0] ? "\"" : "(empty)",
               V[i].in[0] ? (int)strlen(V[i].in) : 0, V[i].in,
               V[i].in[0] ? "\"" : "");
        printf("         want %s\n", V[i].want);
        printf("         got  %s\n", got);
    }

    /* Streaming check: one million 'a', fed in awkward chunk sizes so the
       64-byte block buffer is exercised at every alignment. */
    {
        sha256_ctx    c;
        unsigned char d[32];
        unsigned char chunk[997];
        long          left = 1000000;
        int           ok, k;
        static const char HEX[] = "0123456789abcdef";

        memset(chunk, 'a', sizeof chunk);
        sha256_init(&c);
        while (left > 0) {
            size_t take = (size_t)((left < (long)sizeof chunk) ? left : (long)sizeof chunk);
            sha256_update(&c, chunk, take);
            left -= (long)take;
        }
        sha256_final(&c, d);
        for (k = 0; k < 32; k++) {
            got[k * 2    ] = HEX[(d[k] >> 4) & 0xf];
            got[k * 2 + 1] = HEX[ d[k]       & 0xf];
        }
        got[64] = '\0';
        ok = (strcmp(got, MILLION_A) == 0);
        if (!ok) bad++;
        printf("  [%s] sha256(1000000 x 'a')  (streaming path)\n",
               ok ? "OK" : "FAIL");
        printf("         want %s\n", MILLION_A);
        printf("         got  %s\n", got);
    }

    /* MINI-SPECS.md section 7.1: one DEFLATE vector per block type.  The
       inputs were produced by an unrelated encoder (zlib); the expected
       outputs are the bytes that were handed to it. */
    {
        static const unsigned char STORED[16] = {
            0x01, 0x0b, 0x00, 0xf4, 0xff, 0x77, 0x65, 0x72, 0x6b, 0x20, 0x73, 0x74,
            0x6f, 0x72, 0x65, 0x64 };
        static const unsigned char FIXED[7] = {
            0x4b, 0x4c, 0x4a, 0x4e, 0x44, 0x45, 0x00 };
        static const unsigned char DYNAMIC[81] = {
            0x8d, 0x89, 0xbb, 0x0d, 0x80, 0x30, 0x0c, 0x05, 0x57, 0xf1, 0x00, 0xc0,
            0x00, 0x6c, 0x63, 0x39, 0x4e, 0xf2, 0x44, 0x3e, 0x92, 0x63, 0x88, 0xd8,
            0x9e, 0x82, 0x92, 0x86, 0xe6, 0x74, 0xba, 0x9b, 0x6a, 0x07, 0xcd, 0x9f,
            0x18, 0x5a, 0xe2, 0x2a, 0x6c, 0x76, 0xa3, 0x25, 0x0a, 0x48, 0x70, 0x2e,
            0xc4, 0xe6, 0x88, 0x2c, 0x3e, 0x76, 0xf2, 0xac, 0x14, 0x51, 0x94, 0x30,
            0x5e, 0xef, 0x56, 0xd9, 0x97, 0x4f, 0x0f, 0x5d, 0xce, 0xaa, 0xcd, 0xd9,
            0xd1, 0xdb, 0x77, 0xb3, 0x49, 0xc6, 0xa5, 0x1b, 0x3d };
        static const struct {
            const char *name; const unsigned char *in; size_t n; const char *want;
        } D[3] = {
            { "stored",  STORED,  sizeof STORED,
              "ce0a40dc0a2c99da888b60c8a20a5dfbd5aae7dd238f8d15fc15eeedf940a8e5" },
            { "fixed",   FIXED,   sizeof FIXED,
              "916f4626f2d02e07085873c17f8115790840519094e94114b706573c9749331f" },
            { "dynamic", DYNAMIC, sizeof DYNAMIC,
              "09b86fc31af218f9bae56da09eb8a03c49ba5b22acae373d69613d5a793eb26e" }
        };
        unsigned char out[512];
        int           q;

        printf("\n  vectors from spec/MINI-SPECS.md section 7.1 (DEFLATE)\n\n");
        for (q = 0; q < 3; q++) {
            size_t n  = 0;
            int    ok = inflate_raw(D[q].in, D[q].n, out, sizeof out, &n);
            if (ok) {
                sha256_hex(out, n, got);
                ok = (strcmp(got, D[q].want) == 0);
            }
            if (!ok) bad++;
            printf("  [%s] inflate, %s block (%lu bytes in)\n",
                   ok ? "OK" : "FAIL", D[q].name, (unsigned long)D[q].n);
        }
    }

    printf("\n%s\n", bad ? "SELFTEST FAIL" : "SELFTEST OK");
    return bad ? 1 : 0;
}

/* ================================================================== */
/* 3. JSON  --  MINI-SPECS.md section 3                                */
/*                                                                     */
/* A walker, not a validator.  It parses the restricted profile werk    */
/* uses and rejects what that profile forbids and a parser can see:     */
/* a byte-order mark, comments, trailing commas, single quotes, NaN and */
/* Infinity, and duplicate keys within one object (MINI-SPECS.md        */
/* section 3 says a reader MUST reject a duplicate key rather than pick */
/* a winner).  Numbers are kept as both a double and, when the token    */
/* had no fraction and no exponent, an exact long long.                 */
/* ================================================================== */

typedef enum { J_NULL, J_BOOL, J_NUM, J_STR, J_ARR, J_OBJ } jtype;

typedef struct jval {
    jtype  t;

    int    b;            /* J_BOOL                                     */

    double num;          /* J_NUM                                      */
    long long inum;      /* J_NUM, exact when is_int                   */
    int    is_int;

    char  *str;          /* J_STR, NUL-terminated UTF-8                */
    size_t slen;

    struct jval **item;  /* J_ARR                                      */
    size_t nitem;

    char        **key;   /* J_OBJ, parallel arrays                     */
    struct jval **val;
    size_t        nmemb;
} jval;

typedef struct {
    const char *p;
    size_t      n, i;
    int         depth;
    char        err[192];
} jparser;

#define J_MAX_DEPTH 200

static jval *j_new(jtype t)
{
    jval *v = (jval *)xmalloc(sizeof *v);
    memset(v, 0, sizeof *v);
    v->t = t;
    return v;
}

static void json_free(jval *v)
{
    size_t i;
    if (!v) return;
    switch (v->t) {
    case J_STR: free(v->str); break;
    case J_ARR:
        for (i = 0; i < v->nitem; i++) json_free(v->item[i]);
        free(v->item);
        break;
    case J_OBJ:
        for (i = 0; i < v->nmemb; i++) { free(v->key[i]); json_free(v->val[i]); }
        free(v->key); free(v->val);
        break;
    default: break;
    }
    free(v);
}

static void j_fail(jparser *ps, const char *msg)
{
    if (!ps->err[0])
        snprintf(ps->err, sizeof ps->err, "%s at byte offset %lu",
                 msg, (unsigned long)ps->i);
}

static void j_ws(jparser *ps)
{
    /* MINI-SPECS.md section 3: only these four characters are whitespace.
       No comments exist in werk JSON, so a '/' here is an error, and the
       value parser will report it as an unexpected character. */
    while (ps->i < ps->n) {
        char c = ps->p[ps->i];
        if (c == ' ' || c == '\t' || c == '\n' || c == '\r') ps->i++;
        else break;
    }
}

static jval *j_value(jparser *ps);

/* Append the UTF-8 encoding of one code point (MINI-SPECS.md section 2). */
static void j_utf8(char **buf, size_t *len, size_t *cap, unsigned long cp)
{
    unsigned char tmp[4];
    int           k = 0;

    if (cp <= 0x7fUL) {
        tmp[k++] = (unsigned char)cp;
    } else if (cp <= 0x7ffUL) {
        tmp[k++] = (unsigned char)(0xc0u | (cp >> 6));
        tmp[k++] = (unsigned char)(0x80u | (cp & 0x3fu));
    } else if (cp <= 0xffffUL) {
        tmp[k++] = (unsigned char)(0xe0u | (cp >> 12));
        tmp[k++] = (unsigned char)(0x80u | ((cp >> 6) & 0x3fu));
        tmp[k++] = (unsigned char)(0x80u | (cp & 0x3fu));
    } else {
        tmp[k++] = (unsigned char)(0xf0u | (cp >> 18));
        tmp[k++] = (unsigned char)(0x80u | ((cp >> 12) & 0x3fu));
        tmp[k++] = (unsigned char)(0x80u | ((cp >> 6) & 0x3fu));
        tmp[k++] = (unsigned char)(0x80u | (cp & 0x3fu));
    }
    if (*len + (size_t)k + 1 > *cap) {
        *cap = (*cap ? *cap * 2 : 32) + (size_t)k + 1;
        *buf = (char *)xrealloc(*buf, *cap);
    }
    memcpy(*buf + *len, tmp, (size_t)k);
    *len += (size_t)k;
}

static int j_hex4(jparser *ps, unsigned long *out)
{
    unsigned long v = 0;
    int           k;
    if (ps->i + 4 > ps->n) return 0;
    for (k = 0; k < 4; k++) {
        char c = ps->p[ps->i + k];
        v <<= 4;
        if      (c >= '0' && c <= '9') v |= (unsigned long)(c - '0');
        else if (c >= 'a' && c <= 'f') v |= (unsigned long)(c - 'a' + 10);
        else if (c >= 'A' && c <= 'F') v |= (unsigned long)(c - 'A' + 10);
        else return 0;
    }
    ps->i += 4;
    *out = v;
    return 1;
}

/* Parse a string token; ps->i must be at the opening quote. */
static char *j_string(jparser *ps, size_t *out_len)
{
    char  *buf = NULL;
    size_t len = 0, cap = 0;

    if (ps->i >= ps->n || ps->p[ps->i] != '"') {
        /* Catch the single-quote mistake explicitly: MINI-SPECS.md
           section 3 bans it and a bare "expected string" would hide it. */
        if (ps->i < ps->n && ps->p[ps->i] == '\'')
            j_fail(ps, "single-quoted string (JSON strings use double quotes)");
        else if (ps->i < ps->n && ps->p[ps->i] == '/')
            j_fail(ps, "comment (comments are illegal in werk JSON)");
        else
            j_fail(ps, "expected a string");
        return NULL;
    }
    ps->i++;

    for (;;) {
        unsigned char c;
        if (ps->i >= ps->n) { j_fail(ps, "unterminated string"); goto bad; }
        c = (unsigned char)ps->p[ps->i];

        if (c == '"') { ps->i++; break; }

        if (c < 0x20) { j_fail(ps, "raw control character in string"); goto bad; }

        if (c == '\\') {
            char e;
            ps->i++;
            if (ps->i >= ps->n) { j_fail(ps, "unterminated escape"); goto bad; }
            e = ps->p[ps->i++];
            switch (e) {
            case '"':  j_utf8(&buf, &len, &cap, 0x22); break;
            case '\\': j_utf8(&buf, &len, &cap, 0x5c); break;
            case '/':  j_utf8(&buf, &len, &cap, 0x2f); break;
            case 'b':  j_utf8(&buf, &len, &cap, 0x08); break;
            case 'f':  j_utf8(&buf, &len, &cap, 0x0c); break;
            case 'n':  j_utf8(&buf, &len, &cap, 0x0a); break;
            case 'r':  j_utf8(&buf, &len, &cap, 0x0d); break;
            case 't':  j_utf8(&buf, &len, &cap, 0x09); break;
            case 'u': {
                unsigned long cp;
                if (!j_hex4(ps, &cp)) { j_fail(ps, "bad \\u escape"); goto bad; }
                if (cp >= 0xd800UL && cp <= 0xdbffUL) {
                    /* high surrogate: a low surrogate must follow
                       (MINI-SPECS.md section 3) */
                    unsigned long lo;
                    if (ps->i + 1 >= ps->n ||
                        ps->p[ps->i] != '\\' || ps->p[ps->i + 1] != 'u') {
                        j_fail(ps, "high surrogate not followed by \\u");
                        goto bad;
                    }
                    ps->i += 2;
                    if (!j_hex4(ps, &lo)) { j_fail(ps, "bad \\u escape"); goto bad; }
                    if (lo < 0xdc00UL || lo > 0xdfffUL) {
                        j_fail(ps, "high surrogate not followed by a low surrogate");
                        goto bad;
                    }
                    cp = 0x10000UL + ((cp - 0xd800UL) << 10) + (lo - 0xdc00UL);
                } else if (cp >= 0xdc00UL && cp <= 0xdfffUL) {
                    j_fail(ps, "lone low surrogate");
                    goto bad;
                }
                j_utf8(&buf, &len, &cap, cp);
                break;
            }
            default:
                j_fail(ps, "unknown escape sequence");
                goto bad;
            }
            continue;
        }

        /* Any other byte is copied verbatim.  Multi-byte UTF-8 sequences
           pass through unchanged, which is what we want: werk hashes bytes. */
        j_utf8(&buf, &len, &cap, (unsigned long)c);
        ps->i++;
    }

    if (len + 1 > cap) { cap = len + 1; buf = (char *)xrealloc(buf, cap); }
    buf[len] = '\0';
    if (out_len) *out_len = len;
    return buf;

bad:
    free(buf);
    return NULL;
}

static jval *j_number(jparser *ps)
{
    size_t start = ps->i;
    int    isint = 1;
    jval  *v;
    char  *tok;
    char  *end;

    if (ps->i < ps->n && ps->p[ps->i] == '-') ps->i++;

    /* MINI-SPECS.md section 3: int = '0' | digit1-9 *digit.  A leading
       zero followed by another digit is not legal JSON. */
    if (ps->i >= ps->n) { j_fail(ps, "truncated number"); return NULL; }
    if (ps->p[ps->i] == '0') {
        ps->i++;
    } else if (ps->p[ps->i] >= '1' && ps->p[ps->i] <= '9') {
        while (ps->i < ps->n && ps->p[ps->i] >= '0' && ps->p[ps->i] <= '9') ps->i++;
    } else {
        /* NaN / Infinity / -Infinity land here; they are banned outright. */
        j_fail(ps, "not a number (NaN and Infinity are illegal in werk JSON)");
        return NULL;
    }

    if (ps->i < ps->n && ps->p[ps->i] == '.') {
        isint = 0;
        ps->i++;
        if (ps->i >= ps->n || ps->p[ps->i] < '0' || ps->p[ps->i] > '9') {
            j_fail(ps, "digit required after decimal point");
            return NULL;
        }
        while (ps->i < ps->n && ps->p[ps->i] >= '0' && ps->p[ps->i] <= '9') ps->i++;
    }
    if (ps->i < ps->n && (ps->p[ps->i] == 'e' || ps->p[ps->i] == 'E')) {
        isint = 0;
        ps->i++;
        if (ps->i < ps->n && (ps->p[ps->i] == '+' || ps->p[ps->i] == '-')) ps->i++;
        if (ps->i >= ps->n || ps->p[ps->i] < '0' || ps->p[ps->i] > '9') {
            j_fail(ps, "digit required in exponent");
            return NULL;
        }
        while (ps->i < ps->n && ps->p[ps->i] >= '0' && ps->p[ps->i] <= '9') ps->i++;
    }

    tok = (char *)xmalloc(ps->i - start + 1);
    memcpy(tok, ps->p + start, ps->i - start);
    tok[ps->i - start] = '\0';

    v = j_new(J_NUM);
    /* strtod is locale-sensitive for the decimal point.  This program
       never calls setlocale(), so it stays in the "C" locale, where the
       separator is '.' -- which is the only separator werk JSON uses
       (MINI-SPECS.md section 13). */
    v->num = strtod(tok, &end);
    if (isint) {
        v->is_int = 1;
        v->inum   = strtoll(tok, &end, 10);
    }
    free(tok);
    return v;
}

static int j_lit(jparser *ps, const char *word)
{
    size_t k = strlen(word);
    if (ps->i + k <= ps->n && memcmp(ps->p + ps->i, word, k) == 0) {
        ps->i += k;
        return 1;
    }
    return 0;
}

static jval *j_value(jparser *ps)
{
    char c;

    if (++ps->depth > J_MAX_DEPTH) {
        j_fail(ps, "nesting too deep");
        ps->depth--;
        return NULL;
    }
    j_ws(ps);
    if (ps->i >= ps->n) { j_fail(ps, "unexpected end of input"); ps->depth--; return NULL; }
    c = ps->p[ps->i];

    if (c == '{') {
        jval  *o = j_new(J_OBJ);
        size_t cap = 0;
        ps->i++;
        j_ws(ps);
        if (ps->i < ps->n && ps->p[ps->i] == '}') { ps->i++; ps->depth--; return o; }
        for (;;) {
            char  *k;
            size_t klen;
            jval  *v;
            size_t q;

            j_ws(ps);
            k = j_string(ps, &klen);
            if (!k) { json_free(o); ps->depth--; return NULL; }

            /* Duplicate keys are illegal; reject rather than pick a winner. */
            for (q = 0; q < o->nmemb; q++) {
                if (strcmp(o->key[q], k) == 0) {
                    j_fail(ps, "duplicate object key (illegal in werk JSON)");
                    free(k); json_free(o); ps->depth--; return NULL;
                }
            }

            j_ws(ps);
            if (ps->i >= ps->n || ps->p[ps->i] != ':') {
                j_fail(ps, "expected ':' after object key");
                free(k); json_free(o); ps->depth--; return NULL;
            }
            ps->i++;

            v = j_value(ps);
            if (!v) { free(k); json_free(o); ps->depth--; return NULL; }

            if (o->nmemb == cap) {
                cap = cap ? cap * 2 : 8;
                o->key = (char **)xrealloc(o->key, cap * sizeof(char *));
                o->val = (jval **)xrealloc(o->val, cap * sizeof(jval *));
            }
            o->key[o->nmemb] = k;
            o->val[o->nmemb] = v;
            o->nmemb++;

            j_ws(ps);
            if (ps->i < ps->n && ps->p[ps->i] == ',') {
                ps->i++;
                j_ws(ps);
                if (ps->i < ps->n && ps->p[ps->i] == '}') {
                    j_fail(ps, "trailing comma in object");
                    json_free(o); ps->depth--; return NULL;
                }
                continue;
            }
            if (ps->i < ps->n && ps->p[ps->i] == '}') { ps->i++; break; }
            j_fail(ps, "expected ',' or '}'");
            json_free(o); ps->depth--; return NULL;
        }
        ps->depth--;
        return o;
    }

    if (c == '[') {
        jval  *a = j_new(J_ARR);
        size_t cap = 0;
        ps->i++;
        j_ws(ps);
        if (ps->i < ps->n && ps->p[ps->i] == ']') { ps->i++; ps->depth--; return a; }
        for (;;) {
            jval *v = j_value(ps);
            if (!v) { json_free(a); ps->depth--; return NULL; }
            if (a->nitem == cap) {
                cap = cap ? cap * 2 : 8;
                a->item = (jval **)xrealloc(a->item, cap * sizeof(jval *));
            }
            a->item[a->nitem++] = v;

            j_ws(ps);
            if (ps->i < ps->n && ps->p[ps->i] == ',') {
                ps->i++;
                j_ws(ps);
                if (ps->i < ps->n && ps->p[ps->i] == ']') {
                    j_fail(ps, "trailing comma in array");
                    json_free(a); ps->depth--; return NULL;
                }
                continue;
            }
            if (ps->i < ps->n && ps->p[ps->i] == ']') { ps->i++; break; }
            j_fail(ps, "expected ',' or ']'");
            json_free(a); ps->depth--; return NULL;
        }
        ps->depth--;
        return a;
    }

    if (c == '"') {
        size_t len;
        char  *s = j_string(ps, &len);
        jval  *v;
        if (!s) { ps->depth--; return NULL; }
        v = j_new(J_STR);
        v->str  = s;
        v->slen = len;
        ps->depth--;
        return v;
    }

    if (c == 't') {
        if (j_lit(ps, "true"))  { jval *v = j_new(J_BOOL); v->b = 1; ps->depth--; return v; }
    } else if (c == 'f') {
        if (j_lit(ps, "false")) { jval *v = j_new(J_BOOL); v->b = 0; ps->depth--; return v; }
    } else if (c == 'n') {
        if (j_lit(ps, "null"))  { jval *v = j_new(J_NULL);           ps->depth--; return v; }
    } else if (c == '-' || (c >= '0' && c <= '9')) {
        jval *v = j_number(ps);
        ps->depth--;
        return v;
    } else if (c == '/') {
        j_fail(ps, "comment (comments are illegal in werk JSON)");
        ps->depth--;
        return NULL;
    } else if (c == 'N' || c == 'I') {
        /* MINI-SPECS.md section 3: a JSON number in werk is always finite. */
        j_fail(ps, "NaN or Infinity (a werk JSON number is always finite)");
        ps->depth--;
        return NULL;
    }

    j_fail(ps, "unexpected character");
    ps->depth--;
    return NULL;
}

/* Is p[0..n) well-formed UTF-8 (MINI-SPECS.md section 2): no overlong
   form, no surrogate, nothing above U+10FFFF?  Returns the offset of the
   first bad byte, or n when every byte is good.  werk JSON is UTF-8, and
   SPEC.md section 10.1's `text_encoding` row makes a manifest that is not a
   container-scoped refusal -- a reader that walks the bytes anyway reads a
   different document from the one every other reader refuses (finding N7:
   this loader used to verify such a package and exit 0). */
static size_t utf8_bad_at(const unsigned char *p, size_t n)
{
    size_t i = 0;
    while (i < n) {
        unsigned c = p[i];
        size_t   k, need;
        unsigned long cp;
        if (c < 0x80) { i++; continue; }
        if (c >= 0xc2 && c <= 0xdf)      { need = 1; cp = c & 0x1f; }
        else if (c >= 0xe0 && c <= 0xef) { need = 2; cp = c & 0x0f; }
        else if (c >= 0xf0 && c <= 0xf4) { need = 3; cp = c & 0x07; }
        else return i;
        for (k = 1; k <= need; k++) {
            if (i + k >= n || (p[i + k] & 0xc0) != 0x80) return i;
            cp = (cp << 6) | (p[i + k] & 0x3f);
        }
        if ((need == 2 && cp < 0x800) || (need == 3 && cp < 0x10000) ||
            (cp >= 0xd800 && cp <= 0xdfff) || cp > 0x10ffff)
            return i;
        i += need + 1;
    }
    return n;
}

/* Parse a whole document.  err (size >= 256) receives a message on
   failure.  A UTF-8 BOM is rejected, never stripped: stripping it would
   change the file's sha256, and sha256 is the store key
   (MINI-SPECS.md section 2).  Bytes that are not UTF-8 are rejected too. */
static jval *json_parse(const char *text, size_t len, char *err, size_t errsz)
{
    jparser ps;
    jval   *v;
    size_t  bad;

    err[0] = '\0';

    bad = utf8_bad_at((const unsigned char *)text, len);
    if (bad != len) {
        snprintf(err, errsz, "not valid UTF-8 at byte %lu (werk JSON is UTF-8, "
                 "spec/MINI-SPECS.md section 2)", (unsigned long)bad);
        return NULL;
    }

    if (len >= 3 && (unsigned char)text[0] == 0xef &&
                    (unsigned char)text[1] == 0xbb &&
                    (unsigned char)text[2] == 0xbf) {
        snprintf(err, errsz,
                 "file begins with a UTF-8 byte-order mark; werk JSON is "
                 "BOM-free (spec/MINI-SPECS.md section 2) and stripping it "
                 "would change the file's sha256");
        return NULL;
    }

    ps.p = text; ps.n = len; ps.i = 0; ps.depth = 0; ps.err[0] = '\0';
    v = j_value(&ps);
    if (!v) { snprintf(err, errsz, "%s", ps.err[0] ? ps.err : "parse error"); return NULL; }

    j_ws(&ps);
    if (ps.i != ps.n) {
        snprintf(err, errsz, "trailing bytes after the top-level value at offset %lu",
                 (unsigned long)ps.i);
        json_free(v);
        return NULL;
    }
    return v;
}

/* --- accessors ---------------------------------------------------- */

static jval *jget(const jval *o, const char *key)
{
    size_t i;
    if (!o || o->t != J_OBJ) return NULL;
    for (i = 0; i < o->nmemb; i++)
        if (strcmp(o->key[i], key) == 0) return o->val[i];
    return NULL;
}

static const char *jstr(const jval *v)
{
    return (v && v->t == J_STR) ? v->str : NULL;
}

static const char *jstr_of(const jval *o, const char *key)
{
    return jstr(jget(o, key));
}

static int jstr_eq(const jval *v, const char *s)
{
    const char *a = jstr(v);
    return a && strcmp(a, s) == 0;
}

/* Integer field; returns 0 and leaves *out alone when absent or not an
   exact integer. */
static int jint_of(const jval *o, const char *key, long long *out)
{
    jval *v = jget(o, key);
    if (!v || v->t != J_NUM || !v->is_int) return 0;
    *out = v->inum;
    return 1;
}

/* --- a minimal pretty printer, used only for --envelope ----------- */

/* Print a non-integral number in the shortest decimal form that reparses
   to the same binary64 -- the rule MINI-SPECS.md section 3 gives for
   canonical JSON.  Doing it the lazy way (%.17g always) turns 0.0005 into
   0.00050000000000000001, which is true but unreadable in an audit
   dump.  A trailing ".0" is forced so that a float64 5.0 in a
   MessagePack header is never mistaken for the integer 5. */
static void print_double(double d, FILE *f)
{
    char buf[64];
    int  prec;

    for (prec = 15; prec <= 17; prec++) {
        snprintf(buf, sizeof buf, "%.*g", prec, d);
        if (strtod(buf, NULL) == d) break;
    }
    if (!strpbrk(buf, ".eEn"))   /* 'n' catches inf/nan spellings */
        snprintf(buf + strlen(buf), sizeof buf - strlen(buf), ".0");
    fputs(buf, f);
}

static void json_print(const jval *v, int indent, FILE *f)
{
    int    k;
    size_t i;

    if (!v) { fputs("null", f); return; }
    switch (v->t) {
    case J_NULL: fputs("null", f); break;
    case J_BOOL: fputs(v->b ? "true" : "false", f); break;
    case J_NUM:
        if (v->is_int) fprintf(f, "%lld", v->inum);
        else           print_double(v->num, f);
        break;
    case J_STR:
        fputc('"', f);
        for (i = 0; i < v->slen; i++) {
            unsigned char c = (unsigned char)v->str[i];
            if      (c == '"')  fputs("\\\"", f);
            else if (c == '\\') fputs("\\\\", f);
            else if (c == '\n') fputs("\\n", f);
            else if (c == '\r') fputs("\\r", f);
            else if (c == '\t') fputs("\\t", f);
            else if (c < 0x20)  fprintf(f, "\\u%04x", c);
            else                fputc((int)c, f);
        }
        fputc('"', f);
        break;
    case J_ARR:
        if (v->nitem == 0) { fputs("[]", f); break; }
        fputs("[\n", f);
        for (i = 0; i < v->nitem; i++) {
            for (k = 0; k <= indent; k++) fputs("  ", f);
            json_print(v->item[i], indent + 1, f);
            fputs(i + 1 < v->nitem ? ",\n" : "\n", f);
        }
        for (k = 0; k < indent; k++) fputs("  ", f);
        fputc(']', f);
        break;
    case J_OBJ:
        if (v->nmemb == 0) { fputs("{}", f); break; }
        fputs("{\n", f);
        for (i = 0; i < v->nmemb; i++) {
            for (k = 0; k <= indent; k++) fputs("  ", f);
            fprintf(f, "\"%s\": ", v->key[i]);
            json_print(v->val[i], indent + 1, f);
            fputs(i + 1 < v->nmemb ? ",\n" : "\n", f);
        }
        for (k = 0; k < indent; k++) fputs("  ", f);
        fputc('}', f);
        break;
    }
}

/* ================================================================== */
/* 4. MessagePack  --  ENVELOPE.layout.txt section 4                   */
/*                                                                     */
/* Only the subset that file permits, decoded into the same jval tree  */
/* the JSON parser produces, so the header can be printed and walked   */
/* with the code that already exists.  Note the trap the layout file   */
/* calls out: MessagePack integers and floats are BIG-endian, the      */
/* opposite of everything else in a werk binary.                       */
/* ================================================================== */

typedef struct {
    const unsigned char *p;
    size_t               n, i;
    int                  depth;
    char                 err[192];
} mpr;

static void mp_fail(mpr *r, const char *msg)
{
    if (!r->err[0])
        snprintf(r->err, sizeof r->err, "%s at header offset %lu",
                 msg, (unsigned long)r->i);
}

static int mp_take(mpr *r, size_t k, const unsigned char **out)
{
    if (r->i + k > r->n) { mp_fail(r, "header truncated"); return 0; }
    *out = r->p + r->i;
    r->i += k;
    return 1;
}

static uint64_t mp_be(const unsigned char *p, size_t k)
{
    uint64_t v = 0;
    size_t   i;
    for (i = 0; i < k; i++) v = (v << 8) | (uint64_t)p[i];
    return v;
}

static double mp_f32(const unsigned char *p)
{
    /* IEEE-754 binary32, big-endian, decoded arithmetically so this does
       not depend on the host float layout. */
    uint32_t bits = (uint32_t)mp_be(p, 4);
    int      sign = (bits >> 31) & 1u;
    int      exp  = (int)((bits >> 23) & 0xffu);
    uint32_t man  = bits & 0x7fffffu;
    double   v;

    if (exp == 0)          v = (double)man * 1.1754943508222875e-38 / 8388608.0;
    else if (exp == 0xff)  v = man ? 0.0 : 1e308 * 10.0; /* NaN/Inf: banned in core */
    else {
        double m = 1.0 + (double)man / 8388608.0;
        int    e = exp - 127;
        v = m;
        while (e > 0) { v *= 2.0; e--; }
        while (e < 0) { v /= 2.0; e++; }
    }
    return sign ? -v : v;
}

static double mp_f64(const unsigned char *p)
{
    uint64_t bits = mp_be(p, 8);
    int      sign = (int)((bits >> 63) & 1u);
    int      exp  = (int)((bits >> 52) & 0x7ffu);
    uint64_t man  = bits & 0xfffffffffffffULL;
    double   v;

    if (exp == 0)         v = (double)man * 2.2250738585072014e-308 / 4503599627370496.0;
    else if (exp == 0x7ff) v = man ? 0.0 : 1e308 * 10.0;
    else {
        double m = 1.0 + (double)man / 4503599627370496.0;
        int    e = exp - 1023;
        v = m;
        while (e > 0) { v *= 2.0; e--; }
        while (e < 0) { v /= 2.0; e++; }
    }
    return sign ? -v : v;
}

static jval *mp_value(mpr *r);

static jval *mp_str(mpr *r, size_t len)
{
    const unsigned char *q;
    jval *v;
    if (!mp_take(r, len, &q)) return NULL;
    v = j_new(J_STR);
    v->str = (char *)xmalloc(len + 1);
    memcpy(v->str, q, len);
    v->str[len] = '\0';
    v->slen = len;
    return v;
}

static jval *mp_array(mpr *r, size_t cnt)
{
    jval  *a = j_new(J_ARR);
    size_t i;
    a->item  = (jval **)xmalloc((cnt ? cnt : 1) * sizeof(jval *));
    for (i = 0; i < cnt; i++) {
        jval *e = mp_value(r);
        if (!e) { a->nitem = i; json_free(a); return NULL; }
        a->item[i] = e;
    }
    a->nitem = cnt;
    return a;
}

static jval *mp_map(mpr *r, size_t cnt)
{
    jval  *o = j_new(J_OBJ);
    size_t i;
    o->key = (char **)xmalloc((cnt ? cnt : 1) * sizeof(char *));
    o->val = (jval **)xmalloc((cnt ? cnt : 1) * sizeof(jval *));
    for (i = 0; i < cnt; i++) {
        jval *k = mp_value(r);
        jval *v;
        if (!k) { o->nmemb = i; json_free(o); return NULL; }
        if (k->t != J_STR) {
            mp_fail(r, "header map key is not a string");
            json_free(k); o->nmemb = i; json_free(o); return NULL;
        }
        v = mp_value(r);
        if (!v) { json_free(k); o->nmemb = i; json_free(o); return NULL; }
        o->key[i] = k->str;  /* take ownership of the string */
        k->str = NULL; k->slen = 0; json_free(k);
        o->val[i] = v;
    }
    o->nmemb = cnt;
    return o;
}

static jval *mp_value(mpr *r)
{
    const unsigned char *q;
    unsigned char        b;
    jval                *v;

    if (++r->depth > J_MAX_DEPTH) { mp_fail(r, "header nesting too deep"); r->depth--; return NULL; }
    if (!mp_take(r, 1, &q)) { r->depth--; return NULL; }
    b = q[0];

    /* ENVELOPE.layout.txt section 4.2: these are banned outright and a
       reader MUST reject the header and mark the node dead. */
    if (b == 0xc1 || (b >= 0xc7 && b <= 0xc9) || (b >= 0xd4 && b <= 0xd8)) {
        mp_fail(r, "banned MessagePack format byte (ext types and 0xc1 are "
                   "forbidden by ENVELOPE.layout.txt section 4.2)");
        r->depth--;
        return NULL;
    }

    if (b <= 0x7f) {                       /* positive fixint            */
        v = j_new(J_NUM); v->is_int = 1; v->inum = b; v->num = (double)b;
        r->depth--; return v;
    }
    if (b >= 0xe0) {                       /* negative fixint            */
        int iv = (int)b - 256;
        v = j_new(J_NUM); v->is_int = 1; v->inum = iv; v->num = (double)iv;
        r->depth--; return v;
    }
    if (b >= 0xa0 && b <= 0xbf) { v = mp_str(r, (size_t)(b & 0x1fu)); r->depth--; return v; }
    if (b >= 0x90 && b <= 0x9f) { v = mp_array(r, (size_t)(b & 0x0fu)); r->depth--; return v; }
    if (b >= 0x80 && b <= 0x8f) { v = mp_map(r, (size_t)(b & 0x0fu)); r->depth--; return v; }

    switch (b) {
    case 0xc0: v = j_new(J_NULL);                    r->depth--; return v;
    case 0xc2: v = j_new(J_BOOL); v->b = 0;          r->depth--; return v;
    case 0xc3: v = j_new(J_BOOL); v->b = 1;          r->depth--; return v;

    case 0xcc: case 0xcd: case 0xce: case 0xcf: {
        size_t   k = (size_t)1u << (b - 0xcc);
        uint64_t u;
        if (!mp_take(r, k, &q)) { r->depth--; return NULL; }
        u = mp_be(q, k);
        v = j_new(J_NUM); v->is_int = 1;
        v->inum = (long long)u; v->num = (double)u;
        r->depth--; return v;
    }
    case 0xd0: case 0xd1: case 0xd2: case 0xd3: {
        size_t    k = (size_t)1u << (b - 0xd0);
        uint64_t  u;
        long long s;
        if (!mp_take(r, k, &q)) { r->depth--; return NULL; }
        u = mp_be(q, k);
        /* sign-extend from k bytes */
        if (k < 8 && (u & ((uint64_t)1 << (k * 8 - 1))))
            u |= ~(((uint64_t)1 << (k * 8)) - 1);
        s = (long long)u;
        v = j_new(J_NUM); v->is_int = 1; v->inum = s; v->num = (double)s;
        r->depth--; return v;
    }
    case 0xca:
        if (!mp_take(r, 4, &q)) { r->depth--; return NULL; }
        v = j_new(J_NUM); v->num = mp_f32(q);
        r->depth--; return v;
    case 0xcb:
        if (!mp_take(r, 8, &q)) { r->depth--; return NULL; }
        v = j_new(J_NUM); v->num = mp_f64(q);
        r->depth--; return v;

    case 0xd9: case 0xda: case 0xdb: {
        size_t k = (size_t)1u << (b - 0xd9);
        size_t len;
        if (!mp_take(r, k, &q)) { r->depth--; return NULL; }
        len = (size_t)mp_be(q, k);
        v = mp_str(r, len);
        r->depth--; return v;
    }
    case 0xc4: case 0xc5: case 0xc6: {
        /* bin: legal in the table, but nothing in the werk header schema
           uses it.  Represent it honestly rather than pretending it is a
           string with meaning. */
        size_t k = (size_t)1u << (b - 0xc4);
        size_t len;
        char   tmp[64];
        if (!mp_take(r, k, &q)) { r->depth--; return NULL; }
        len = (size_t)mp_be(q, k);
        if (!mp_take(r, len, &q)) { r->depth--; return NULL; }
        snprintf(tmp, sizeof tmp, "(bin, %lu bytes, not decoded)", (unsigned long)len);
        v = j_new(J_STR);
        v->str = xstrdup(tmp);
        v->slen = strlen(tmp);
        r->depth--; return v;
    }
    case 0xdc: case 0xdd: {
        size_t k = (b == 0xdc) ? 2u : 4u;
        size_t cnt;
        if (!mp_take(r, k, &q)) { r->depth--; return NULL; }
        cnt = (size_t)mp_be(q, k);
        v = mp_array(r, cnt);
        r->depth--; return v;
    }
    case 0xde: case 0xdf: {
        size_t k = (b == 0xde) ? 2u : 4u;
        size_t cnt;
        if (!mp_take(r, k, &q)) { r->depth--; return NULL; }
        cnt = (size_t)mp_be(q, k);
        v = mp_map(r, cnt);
        r->depth--; return v;
    }
    default:
        mp_fail(r, "unknown MessagePack format byte");
        r->depth--;
        return NULL;
    }
}

static jval *msgpack_decode(const unsigned char *p, size_t n, char *err, size_t errsz)
{
    mpr   r;
    jval *v;

    r.p = p; r.n = n; r.i = 0; r.depth = 0; r.err[0] = '\0';
    err[0] = '\0';
    v = mp_value(&r);
    if (!v) { snprintf(err, errsz, "%s", r.err[0] ? r.err : "decode error"); return NULL; }
    if (r.i != r.n) {
        snprintf(err, errsz, "%lu trailing byte(s) after the header map",
                 (unsigned long)(r.n - r.i));
        json_free(v);
        return NULL;
    }
    return v;
}

/* ================================================================== */
/* 5. The container  --  SPEC.md section 1, MINI-SPECS.md section 5    */
/*                                                                     */
/* "Directory and zip layouts are identical.  Both are the format."     */
/* Everything above this layer asks for a package-relative POSIX path   */
/* and gets bytes; it never learns which of the two forms it has.       */
/* ================================================================== */

enum {
    PKF_OK = 0,        /* bytes returned                                */
    PKF_MISSING,       /* no such entry / no such file                  */
    PKF_UNSUPPORTED,   /* a zip method other than 0 and 8, or encrypted */
    PKF_INVALID,       /* a deflate stream that does not decode, or     */
                       /* bytes that disagree with the directory        */
    PKF_IO,            /* short read, seek failure, truncated entry     */
    PKF_BADPATH        /* path escapes the package or is malformed      */
};

typedef struct {
    char    *name;
    unsigned method;
    uint32_t crc32;
    uint32_t csize;
    uint32_t usize;
    uint32_t lho;      /* local header offset                          */
    unsigned flags;
} zentry;

typedef struct {
    int      is_zip;
    char    *root;     /* directory form: the directory path            */
    char    *zpath;    /* zip form: the .werk path                      */
    FILE    *zf;
    zentry  *ent;
    size_t   nent;
} wpkg;

/* SPEC.md section 10 step 9 and MINI-SPECS.md section 5.4: names are
   forward-slashed, relative, and contain no '..' segment, no drive
   letter and no leading slash.  Anything else is refused before it can
   reach the filesystem. */
static int path_is_safe(const char *p)
{
    size_t i, n;
    if (!p || !*p) return 0;
    n = strlen(p);
    if (p[0] == '/' || p[0] == '\\') return 0;
    if (n >= 2 && p[1] == ':') return 0;                 /* C:\... */
    for (i = 0; i < n; i++) {
        unsigned char c = (unsigned char)p[i];
        if (c == '\\') return 0;
        if (c < 0x20)  return 0;
        if (c == '/' && (i == 0 || p[i - 1] == '/')) return 0;  /* "" or "//" */
    }
    /* reject any ".." path segment */
    for (i = 0; i + 1 < n; i++) {
        if (p[i] == '.' && p[i + 1] == '.') {
            int left_ok  = (i == 0) || (p[i - 1] == '/');
            int right_ok = (i + 2 == n) || (p[i + 2] == '/');
            if (left_ok && right_ok) return 0;
        }
    }
    return 1;
}

/* ENVELOPE.layout.txt section 2: is this the start of an envelope?  `W`,
   `K`, then two characters each an ASCII capital letter or digit. */
static int is_envelope_magic(const unsigned char *p)
{
    int i;
    if (p[0] != 'W' || p[1] != 'K') return 0;
    for (i = 2; i < 4; i++)
        if (!((p[i] >= 'A' && p[i] <= 'Z') || (p[i] >= '0' && p[i] <= '9'))) return 0;
    return 1;
}

static uint16_t rd16(const unsigned char *p) { return (uint16_t)(p[0] | ((uint16_t)p[1] << 8)); }
static uint32_t rd32(const unsigned char *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

/* Read a whole host file.  Returns NULL on failure. */
static unsigned char *slurp(const char *path, size_t *out_len)
{
    FILE          *f = fopen(path, "rb");
    long           sz;
    unsigned char *buf;
    size_t         got;

    if (!f) return NULL;
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return NULL; }
    sz = ftell(f);
    if (sz < 0) { fclose(f); return NULL; }
    if (fseek(f, 0, SEEK_SET) != 0) { fclose(f); return NULL; }

    buf = (unsigned char *)xmalloc((size_t)sz + 1);
    got = fread(buf, 1, (size_t)sz, f);
    fclose(f);
    if (got != (size_t)sz) { free(buf); return NULL; }
    buf[sz] = 0;
    *out_len = (size_t)sz;
    return buf;
}

/* The remedy every zip64 refusal prints.  One sentence, in one place:
   "refused by name" is only true if the name and the way out are the
   same wherever the refusal happens. */
#define ZIP64_REMEDY \
    "This reader implements 32-bit zip only and reads nothing from a zip64 " \
    "container, because the offsets it would follow are sentinels. werk does " \
    "not use zip64: a package past the zip32 ceiling (4 GiB, 65534 entries) is " \
    "carried in DIRECTORY form, which is the same format and has no ceiling."

/* ================================================================== */
/* 5a. Inflate  --  raw DEFLATE (RFC 1951), MINI-SPECS.md section 7.1   */
/*                                                                     */
/* Decoding only, for zip method 8.  The bit-at-a-time canonical        */
/* Huffman walk: the slowest correct way to do it and the easiest to    */
/* check against the prose, which is the right trade for a file that is */
/* also a worked example.                                               */
/* ================================================================== */

/* CRC-32, reflected, polynomial 0xEDB88320 -- MINI-SPECS.md section 6. */
static uint32_t crc32_of(const unsigned char *p, size_t n)
{
    uint32_t crc = 0xffffffffu;
    size_t   i;
    int      k;
    for (i = 0; i < n; i++) {
        crc ^= p[i];
        for (k = 0; k < 8; k++)
            crc = (crc & 1u) ? ((crc >> 1) ^ 0xedb88320u) : (crc >> 1);
    }
    return crc ^ 0xffffffffu;
}

typedef struct {
    const unsigned char *src;
    size_t               n, pos;
    uint32_t             buf;
    int                  cnt;
    int                  err;     /* set once the stream runs out        */
} inf_bits;

/* `need` bits (need <= 16), least significant bit first within a byte. */
static uint32_t inf_take(inf_bits *b, int need)
{
    uint32_t v;
    while (b->cnt < need) {
        if (b->pos >= b->n) { b->err = 1; return 0; }
        b->buf |= (uint32_t)b->src[b->pos++] << b->cnt;
        b->cnt += 8;
    }
    v = b->buf & ((1u << need) - 1u);
    b->buf >>= need;
    b->cnt  -= need;
    return v;
}

/* A canonical Huffman code: how many codes there are of each length, and
   the symbols in order of (length, symbol value), which is the order of
   the codes. */
typedef struct {
    unsigned short count[16];
    unsigned short symbol[288];
} inf_huff;

/* Returns the number of unused codes of the longest length (0 = a
   complete code), or -1 when the lengths are over-subscribed. */
static int inf_build(inf_huff *h, const unsigned char *len, int n)
{
    unsigned short offs[16];
    int            i, left = 1;

    for (i = 0; i < 16; i++) h->count[i] = 0;
    for (i = 0; i < n; i++)  h->count[len[i]]++;
    for (i = 1; i < 16; i++) {
        left <<= 1;
        left -= (int)h->count[i];
        if (left < 0) return -1;
    }
    offs[1] = 0;
    for (i = 1; i < 15; i++) offs[i + 1] = (unsigned short)(offs[i] + h->count[i]);
    for (i = 0; i < n; i++)
        if (len[i] != 0) h->symbol[offs[len[i]]++] = (unsigned short)i;
    return left;
}

/* Returns the decoded symbol, or -1 on a bit sequence that is no code. */
static int inf_decode(inf_bits *b, const inf_huff *h)
{
    int code = 0, first = 0, index = 0, len;
    for (len = 1; len < 16; len++) {
        int count;
        code |= (int)inf_take(b, 1);
        if (b->err) return -1;
        count = (int)h->count[len];
        if (code - count < first) return (int)h->symbol[index + (code - first)];
        index += count;
        first += count;
        first <<= 1;
        code  <<= 1;
    }
    return -1;
}

static int inf_codes(inf_bits *b, unsigned char *out, size_t cap, size_t *n,
                     const inf_huff *lit, const inf_huff *dist)
{
    static const unsigned short LBASE[29] = {
        3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59,
        67, 83, 99, 115, 131, 163, 195, 227, 258 };
    static const unsigned char LEXT[29] = {
        0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4,
        5, 5, 5, 5, 0 };
    static const unsigned short DBASE[30] = {
        1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513,
        769, 1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577 };
    static const unsigned char DEXT[30] = {
        0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10,
        11, 11, 12, 12, 13, 13 };

    for (;;) {
        int sym = inf_decode(b, lit);
        if (sym < 0) return 0;
        if (sym < 256) {
            if (*n >= cap) return 0;
            out[(*n)++] = (unsigned char)sym;
        } else if (sym == 256) {
            return 1;
        } else {
            size_t len, distance, k;
            int    d;
            sym -= 257;
            if (sym >= 29) return 0;
            len = (size_t)LBASE[sym] + inf_take(b, LEXT[sym]);
            d   = inf_decode(b, dist);
            if (d < 0 || d >= 30 || b->err) return 0;
            distance = (size_t)DBASE[d] + inf_take(b, DEXT[d]);
            if (b->err || distance > *n || *n + len > cap) return 0;
            /* Byte by byte on purpose: a match may overlap its own output. */
            for (k = 0; k < len; k++) { out[*n] = out[*n - distance]; (*n)++; }
        }
    }
}

/* Inflate one complete raw DEFLATE stream into `out`, never writing more
   than `cap` bytes.  Returns 1 on success and sets *out_n. */
static int inflate_raw(const unsigned char *src, size_t n,
                       unsigned char *out, size_t cap, size_t *out_n)
{
    static const unsigned char ORDER[19] = {
        16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15 };
    inf_bits b;
    size_t   got = 0;
    int      last;

    b.src = src; b.n = n; b.pos = 0; b.buf = 0; b.cnt = 0; b.err = 0;

    do {
        int type;
        last = (int)inf_take(&b, 1);
        type = (int)inf_take(&b, 2);
        if (b.err) return 0;

        if (type == 0) {
            unsigned len, nlen;
            b.buf = 0; b.cnt = 0;                /* to the next byte boundary */
            if (b.pos + 4 > n) return 0;
            len  = (unsigned)src[b.pos]     | ((unsigned)src[b.pos + 1] << 8);
            nlen = (unsigned)src[b.pos + 2] | ((unsigned)src[b.pos + 3] << 8);
            if (len != ((~nlen) & 0xffffu)) return 0;
            b.pos += 4;
            if (b.pos + len > n || got + len > cap) return 0;
            memcpy(out + got, src + b.pos, len);
            got   += len;
            b.pos += len;
        } else if (type == 1) {
            unsigned char l[288], d[30];
            inf_huff      lit, dist;
            int           i;
            for (i = 0;   i < 144; i++) l[i] = 8;
            for (;        i < 256; i++) l[i] = 9;
            for (;        i < 280; i++) l[i] = 7;
            for (;        i < 288; i++) l[i] = 8;
            for (i = 0;   i < 30;  i++) d[i] = 5;
            (void)inf_build(&lit, l, 288);
            (void)inf_build(&dist, d, 30);
            if (!inf_codes(&b, out, cap, &got, &lit, &dist)) return 0;
        } else if (type == 2) {
            unsigned char lengths[286 + 30], cl[19];
            inf_huff      clcode, lit, dist;
            int           nlen, ndist, ncode, i, left;

            nlen  = (int)inf_take(&b, 5) + 257;
            ndist = (int)inf_take(&b, 5) + 1;
            ncode = (int)inf_take(&b, 4) + 4;
            if (b.err || nlen > 286 || ndist > 30) return 0;
            for (i = 0; i < 19; i++) cl[i] = 0;
            for (i = 0; i < ncode; i++) cl[ORDER[i]] = (unsigned char)inf_take(&b, 3);
            if (b.err || inf_build(&clcode, cl, 19) != 0) return 0;

            i = 0;
            while (i < nlen + ndist) {
                int sym = inf_decode(&b, &clcode);
                int value = 0, repeat;
                if (sym < 0) return 0;
                if (sym < 16) { lengths[i++] = (unsigned char)sym; continue; }
                if (sym == 16) {
                    if (i == 0) return 0;
                    value  = lengths[i - 1];
                    repeat = 3 + (int)inf_take(&b, 2);
                } else if (sym == 17) {
                    repeat = 3 + (int)inf_take(&b, 3);
                } else {
                    repeat = 11 + (int)inf_take(&b, 7);
                }
                if (b.err || i + repeat > nlen + ndist) return 0;
                while (repeat-- > 0) lengths[i++] = (unsigned char)value;
            }
            if (lengths[256] == 0) return 0;      /* no end-of-block code */
            left = inf_build(&lit, lengths, nlen);
            if (left < 0 || (left > 0 && nlen != (int)lit.count[0] + (int)lit.count[1]))
                return 0;
            left = inf_build(&dist, lengths + nlen, ndist);
            if (left < 0 || (left > 0 && ndist != (int)dist.count[0] + (int)dist.count[1]))
                return 0;
            if (!inf_codes(&b, out, cap, &got, &lit, &dist)) return 0;
        } else {
            return 0;                             /* block type 3 is reserved */
        }
    } while (!last);

    *out_n = got;
    return 1;
}

/* Open the zip form: find the EOCD by scanning backwards, then read the
   central directory.  MINI-SPECS.md section 5.1 and 5.2. */
static int zip_open(wpkg *pk, const char *path, char *err, size_t errsz)
{
    FILE          *f;
    long           fsz;
    long           tail_at;
    size_t         tail_n, i;
    unsigned char *tail = NULL;
    long           eocd = -1;
    uint32_t       cd_size, cd_off;
    uint16_t       n_rec;
    unsigned char *cd = NULL;
    size_t         off;
    size_t         cap = 0;

    f = fopen(path, "rb");
    if (!f) { snprintf(err, errsz, "not-found: cannot open '%s' for reading", path); return 0; }

    /* ZIP64 FIRST, from the tail, and WITHOUT needing the file's size.
       A zip64 container is by definition the kind that may be larger than
       a `long` can count (ftell below fails past LONG_MAX, which on some
       hosts is 2 GiB), so the refusal that names it must not depend on
       ftell.  A seek RELATIVE TO THE END needs only a small offset: the
       EOCD record and the zip64 locator are in the last 22 + 65535 + 20
       bytes.  If the file is shorter than that the seek fails and the
       whole file is read from the start instead. */
    {
        const long     ZTAIL = 22L + 65535L + 20L;
        unsigned char *t  = (unsigned char *)xmalloc((size_t)ZTAIL);
        size_t         tn, q;
        if (fseek(f, -ZTAIL, SEEK_END) != 0) {
            clearerr(f);
            if (fseek(f, 0L, SEEK_SET) != 0) { free(t); goto probe_done; }
        }
        tn = fread(t, 1, (size_t)ZTAIL, f);
        clearerr(f);
        for (q = tn; q >= 22; q--) {
            size_t at = q - 22;
            if (t[at] == 0x50 && t[at + 1] == 0x4b && t[at + 2] == 0x05 && t[at + 3] == 0x06) {
                int sentinel = (rd16(t + at + 8) == 0xffffu || rd16(t + at + 10) == 0xffffu ||
                                rd32(t + at + 12) == 0xffffffffu ||
                                rd32(t + at + 16) == 0xffffffffu);
                int locator  = (at >= 20 && rd32(t + at - 20) == 0x07064b50u);
                if (sentinel || locator) {
                    snprintf(err, errsz,
                             "zip64-unsupported: zip64 container (EOCD sentinel: %s; "
                             "zip64 locator before the EOCD: %s). %s",
                             sentinel ? "true" : "false", locator ? "true" : "false",
                             ZIP64_REMEDY);
                    free(t);
                    fclose(f);
                    return 0;
                }
                break;
            }
        }
        free(t);
    }
probe_done:

    if (fseek(f, 0, SEEK_END) != 0 || (fsz = ftell(f)) < 0) {
        snprintf(err, errsz, "bad-container: cannot determine the size of '%s'", path);
        fclose(f); return 0;
    }
    if (fsz < 22) {
        snprintf(err, errsz, "bad-container: '%s' is %ld bytes, too small to be a zip",
                 path, fsz);
        fclose(f); return 0;
    }

    /* The EOCD is at most 65535+22 bytes from the end: the trailing
       comment is the only thing that may follow it. */
    tail_n  = (size_t)((fsz < (long)(65535 + 22)) ? fsz : (long)(65535 + 22));
    tail_at = fsz - (long)tail_n;
    tail    = (unsigned char *)xmalloc(tail_n);
    if (fseek(f, tail_at, SEEK_SET) != 0 || fread(tail, 1, tail_n, f) != tail_n) {
        snprintf(err, errsz, "bad-container: short read while scanning for the EOCD record");
        goto fail;
    }

    for (i = tail_n; i >= 22; i--) {
        size_t at = i - 22;
        if (tail[at] == 0x50 && tail[at + 1] == 0x4b &&
            tail[at + 2] == 0x05 && tail[at + 3] == 0x06) {
            uint16_t clen = rd16(tail + at + 20);
            /* MINI-SPECS.md section 5.4, reader rules: the EOCD is the
               highest record whose comment length accounts for exactly the
               rest of the file. */
            if (at + 22 + (size_t)clen == tail_n) { eocd = (long)at; break; }
        }
    }
    if (eocd < 0) {
        /* Zip64 packages carry a different end record; say so precisely
           rather than "not a zip". */
        snprintf(err, errsz,
                 "bad-container: no end-of-central-directory record found: not a zip");
        goto fail;
    }

    n_rec   = rd16(tail + eocd + 10);
    cd_size = rd32(tail + eocd + 12);
    cd_off  = rd32(tail + eocd + 16);

    /* MINI-SPECS.md section 5.5, BOTH signals, either one is enough: a
       sentinel in the EOCD, or the zip64 locator (PK 06 07) sitting
       immediately before it.  Refused whole and by name: the offsets a
       zip32 reader would follow are sentinels. */
    {
        int sentinel = (n_rec == 0xffffu || rd16(tail + eocd + 8) == 0xffffu ||
                        cd_size == 0xffffffffu || cd_off == 0xffffffffu);
        int locator  = (eocd >= 20 && rd32(tail + eocd - 20) == 0x07064b50u);
        if (sentinel || locator) {
            snprintf(err, errsz,
                     "zip64-unsupported: zip64 container (EOCD sentinel: %s; "
                     "zip64 locator before the EOCD: %s). %s",
                     sentinel ? "true" : "false", locator ? "true" : "false",
                     ZIP64_REMEDY);
            goto fail;
        }
    }
    /* MINI-SPECS.md section 5.4, reader rules: exactly `total records`
       (EOCD offset 10) records are read from the central directory offset;
       the directory's byte size (offset 12) is not used to walk it, so it
       is not trusted either.  Everything from the directory offset to the
       end of the file is read and every record is bounds-checked in it. */
    (void)cd_size;
    if ((long)cd_off > fsz) {
        snprintf(err, errsz, "bad-container: central directory offset %lu lies past "
                 "the end of a %ld byte file", (unsigned long)cd_off, fsz);
        goto fail;
    }
    {
        size_t cd_avail = (size_t)(fsz - (long)cd_off);
        uint16_t rec;
        cd = (unsigned char *)xmalloc(cd_avail ? cd_avail : 1);
        if (fseek(f, (long)cd_off, SEEK_SET) != 0 ||
            fread(cd, 1, cd_avail, f) != cd_avail) {
            snprintf(err, errsz, "bad-container: short read of the central directory");
            goto fail;
        }
        cd_size = (uint32_t)cd_avail;
        off = 0;
        for (rec = 0; rec < n_rec; rec++) {
        uint16_t nlen, mlen, klen;
        zentry   e;
        size_t   q;

        if (off + 46 > (size_t)cd_size) {
            snprintf(err, errsz, "bad-container: truncated central directory "
                     "(record %u of %u)", (unsigned)rec + 1u, (unsigned)n_rec);
            goto fail;
        }
        if (rd32(cd + off) != 0x02014b50u) {
            snprintf(err, errsz,
                     "bad-container: bad central directory signature at "
                     "central-directory offset %lu", (unsigned long)off);
            goto fail;
        }
        e.flags  = rd16(cd + off + 8);
        e.method = rd16(cd + off + 10);
        e.crc32  = rd32(cd + off + 16);
        e.csize  = rd32(cd + off + 20);
        e.usize  = rd32(cd + off + 24);
        nlen     = rd16(cd + off + 28);
        mlen     = rd16(cd + off + 30);
        klen     = rd16(cd + off + 32);
        e.lho    = rd32(cd + off + 42);

        /* Only the name is read; the extra field and the comment are
           skipped, not bounds-checked (MINI-SPECS.md section 5.4). */
        if (off + 46 + (size_t)nlen > (size_t)cd_size) {
            snprintf(err, errsz, "bad-container: central directory name at %lu "
                     "runs past the end of the file", (unsigned long)off);
            goto fail;
        }
        e.name = (char *)xmalloc((size_t)nlen + 1);
        memcpy(e.name, cd + off + 46, nlen);
        e.name[nlen] = '\0';

        if (e.csize == 0xffffffffu || e.usize == 0xffffffffu || e.lho == 0xffffffffu) {
            /* MINI-SPECS.md section 5.5 step 5: the per-entry sentinel. */
            snprintf(err, errsz,
                     "zip64-unsupported: entry '%.200s' carries a 0xFFFFFFFF size or "
                     "offset sentinel (a zip64 entry). %s", e.name, ZIP64_REMEDY);
            free(e.name);
            goto fail;
        }
        if (e.flags & 0x0008u) {
            snprintf(err, errsz,
                     "bad-container: entry '%.200s' sets general purpose flag bit 3 "
                     "(data descriptor), which a werk writer MUST NOT set "
                     "(MINI-SPECS.md section 5.4)", e.name);
            free(e.name);
            goto fail;
        }
        for (q = 0; q < pk->nent; q++) {
            if (strcmp(pk->ent[q].name, e.name) == 0) {
                /* Which bytes ARE that file cannot be decided, and readers
                   that pick different records disagree about one package. */
                snprintf(err, errsz,
                         "bad-container: the zip holds two entries named '%.200s'; "
                         "which bytes are that file cannot be decided, so the "
                         "container is refused", e.name);
                free(e.name);
                goto fail;
            }
        }

        if (pk->nent == cap) {
            cap = cap ? cap * 2 : 64;
            pk->ent = (zentry *)xrealloc(pk->ent, cap * sizeof(zentry));
        }
        pk->ent[pk->nent++] = e;

        off += 46u + (size_t)nlen + mlen + klen;
        }
    }

    free(tail);
    free(cd);
    pk->is_zip = 1;
    pk->zpath  = xstrdup(path);
    pk->zf     = f;
    return 1;

fail:
    free(tail);
    free(cd);
    fclose(f);
    return 0;
}

static const zentry *zip_find(const wpkg *pk, const char *name)
{
    size_t i;
    for (i = 0; i < pk->nent; i++)
        if (strcmp(pk->ent[i].name, name) == 0) return &pk->ent[i];
    return NULL;
}

/* Read one package file.  On success returns a malloc'd buffer and sets
   *out_len; on failure returns NULL and sets *status to a PKF_* code. */
static unsigned char *pkg_read(wpkg *pk, const char *path, size_t *out_len, int *status)
{
    *status = PKF_OK;

    if (!path_is_safe(path)) { *status = PKF_BADPATH; return NULL; }

    if (!pk->is_zip) {
        char          *full;
        unsigned char *buf;
        size_t         n;

        n = strlen(pk->root) + 1 + strlen(path) + 1;
        full = (char *)xmalloc(n);
        snprintf(full, n, "%s/%s", pk->root, path);
        /* fopen accepts forward slashes on Windows as well as POSIX, so
           the package-relative POSIX path is used verbatim (SPEC.md
           section 1: both layouts are the format). */
        buf = slurp(full, out_len);
        free(full);
        if (!buf) { *status = PKF_MISSING; return NULL; }
        return buf;
    } else {
        const zentry  *e = zip_find(pk, path);
        unsigned char  lh[30];
        long           data_off;
        unsigned char *buf;

        if (!e) { *status = PKF_MISSING; return NULL; }

        if ((e->method != 0 && e->method != 8) || (e->flags & 0x0001u)) {
            /* MINI-SPECS.md section 5.3: report unsupported, never return
               wrong bytes. */
            *status = PKF_UNSUPPORTED;
            return NULL;
        }

        /* MINI-SPECS.md section 5.3: the local header's name and extra
           lengths can differ from the central directory's, so they are
           always re-read here.  Data begins at lho + 30 + n + m. */
        if (fseek(pk->zf, (long)e->lho, SEEK_SET) != 0 ||
            fread(lh, 1, 30, pk->zf) != 30) { *status = PKF_IO; return NULL; }
        if (rd32(lh) != 0x04034b50u) { *status = PKF_IO; return NULL; }

        data_off = (long)e->lho + 30 + (long)rd16(lh + 26) + (long)rd16(lh + 28);

        buf = (unsigned char *)xmalloc((size_t)e->csize + 1);
        if (fseek(pk->zf, data_off, SEEK_SET) != 0 ||
            fread(buf, 1, e->csize, pk->zf) != e->csize) {
            free(buf); *status = PKF_IO; return NULL;
        }
        buf[e->csize] = 0;
        if (e->method == 8) {
            /* A raw DEFLATE stream (MINI-SPECS.md section 7.1).  The
               directory's uncompressed size bounds the output, and size
               and CRC-32 are checked before a byte is handed over: a
               stream that decodes to the wrong thing is damage to this
               entry, never a wrong payload. */
            unsigned char *out = (unsigned char *)xmalloc((size_t)e->usize + 1);
            size_t         got = 0;
            int            ok  = inflate_raw(buf, e->csize, out, e->usize, &got);
            free(buf);
            if (!ok || got != (size_t)e->usize || crc32_of(out, got) != e->crc32) {
                free(out);
                *status = PKF_INVALID;
                return NULL;
            }
            out[got] = 0;
            *out_len = got;
            return out;
        }
        *out_len = e->csize;
        return buf;
    }
}

static const char *pkf_name(int st)
{
    switch (st) {
    case PKF_OK:          return "ok";
    case PKF_MISSING:     return "missing";
    case PKF_UNSUPPORTED: return "zip-entry-unsupported";
    case PKF_INVALID:     return "zip-entry-invalid";
    case PKF_IO:          return "io-error";
    case PKF_BADPATH:     return "unsafe-path";
    default:              return "unknown";
    }
}

/* Decide directory vs zip and open.  A directory is recognised by the
   presence of a readable <path>/MANIFEST.json; anything else is tried as
   a zip.  That ordering means a directory whose name ends in .werk works
   too, which the spec's "both are the format" demands. */
static int pkg_open(wpkg *pk, const char *path, char *err, size_t errsz)
{
    char  *probe;
    size_t n;
    FILE  *f;

    memset(pk, 0, sizeof *pk);

    n = strlen(path) + 1 + 13 + 1;
    probe = (char *)xmalloc(n);
    snprintf(probe, n, "%s/MANIFEST.json", path);
    f = fopen(probe, "rb");
    free(probe);
    if (f) {
        fclose(f);
        pk->is_zip = 0;
        pk->root   = xstrdup(path);
        return 1;
    }
    return zip_open(pk, path, err, errsz);
}

static void pkg_close(wpkg *pk)
{
    size_t i;
    if (pk->zf) fclose(pk->zf);
    for (i = 0; i < pk->nent; i++) free(pk->ent[i].name);
    free(pk->ent);
    free(pk->root);
    free(pk->zpath);
    memset(pk, 0, sizeof *pk);
}

/* ================================================================== */
/* 6. The manifest walk  --  SPEC.md sections 2, 5 and 10              */
/* ================================================================== */

enum {
    WF_OK = 0,
    WF_MISSING,
    WF_SIZE,
    WF_HASH,
    WF_UNSUPPORTED,
    WF_INVALID,        /* zip entry damaged at the container level      */
    WF_IO,
    WF_BADPATH,
    WF_MALFORMED       /* the files[] record itself is not well formed  */
};

static const char *wf_name(int st)
{
    switch (st) {
    case WF_OK:          return "PASS";
    case WF_MISSING:     return "MISSING";
    case WF_SIZE:        return "SIZE-MISMATCH";
    case WF_HASH:        return "SHA256-MISMATCH";
    /* These two are spelled as the report codes of SPEC.md section 10, so
     * that all four readers name the two entry-level refusals alike (the
     * container gate compares them). The older words above are kept. */
    case WF_UNSUPPORTED: return "zip-entry-unsupported";
    case WF_INVALID:     return "zip-entry-invalid";
    case WF_IO:          return "IO-ERROR";
    case WF_BADPATH:     return "UNSAFE-PATH";
    case WF_MALFORMED:   return "MALFORMED-RECORD";
    default:             return "UNKNOWN";
    }
}

typedef struct {
    const char *path;        /* borrowed from the parsed manifest       */
    const char *sha_want;
    const char *role;
    long long   size_want;
    int         st;
    long long   size_got;
    char        sha_got[65];
    int         foreign;     /* the node DECLARES this file to be in a
                                defined foreign format (SPEC.md 3.18):
                                not an envelope, whatever its first
                                bytes are                               */
} wfile;

typedef struct {
    long long   v;
    const char *note;
    wfile      *f;
    size_t      nf;
    int         checked;     /* files[] has been verified               */
    int         valid;       /* every file passed                       */
} wver;

enum {
    ND_ALIVE = 0,
    ND_MISSING,
    ND_CORRUPT,
    ND_UNSUPPORTED,
    ND_NOVERSION,
    ND_MALFORMED,
    ND_REQUIRES_DEAD
};

typedef struct {
    const char *id;
    const char *type;
    long long   active;
    wver       *ver;
    size_t      nver;
    int         resolved;    /* index into ver[], or -1                 */
    int         dead;        /* ND_*                                    */
    int         fallback;    /* resolved to something other than active */
    int         unknown_type;
    const char *env_bad;     /* path of the file whose envelope frame failed */
    const jval *jnode;
} wnode;

typedef struct {
    jval    *root;
    wnode   *node;
    size_t   nnode;
    strlist  report;
    int      conventions_ok;
    int      n_dead;
    int      n_skipped;
    int      n_fallback;
    int      sig_present;
    int      sig_invalid;    /* present-and-invalid: an error (SPEC 10.1) */
    int      n_rejected;     /* fallbacks away from a FAILING active version */
    int      n_envelopes;    /* envelope frames validated during the walk */
} wmanifest;

/* --- SPEC.md section 10 step 3: conventions ----------------------- */

typedef struct {
    const char *key;
    int         kind;        /* 0 string, 1 number, 2 sh_l1_order       */
    const char *sval;
    double      dval;
} convexp;

/* Every value pinned to a const by the profile's manifest schema.  A reader
   that cannot support one of these must refuse, not guess.

   The tables are PER PROFILE: a convention list belongs to the profile, not
   to the reader.  Profile image/1 has no handedness, no up axis and no
   quaternions, so checking profile 1's twenty-one against it would report
   fourteen missing conventions about a well-formed package.  Found the first
   time a second profile existed; spec finding S-25. */
static const convexp CONVENTIONS[] = {
    { "endianness",          0, "le",         0 },
    { "units_per_meter",     1, NULL,       1.0 },
    { "length_unit",         0, "metre",      0 },
    { "angle_unit",          0, "radian",     0 },
    { "time_unit",           0, "second",     0 },
    { "mass_unit",           0, "kilogram",   0 },
    { "up_axis",             0, "y",          0 },
    { "forward_axis",        0, "-z",         0 },
    { "right_axis",          0, "+x",         0 },
    { "handedness",          0, "right",      0 },
    { "winding",             0, "ccw",        0 },
    { "quat_order",          0, "wxyz",       0 },
    { "oct_encoding_pole",   0, "y",          0 },
    { "sh_l1_order",         2, NULL,         0 },
    { "color_space_default", 0, "srgb",       0 },
    { "uv_origin",           0, "top-left",   0 },
    { "alignment_bytes",     1, NULL,      16.0 },
    { "text_encoding",       0, "utf-8",      0 },
    { "id_case",             0, "kebab-case", 0 },
    { "hash_algorithm",      0, "sha256",     0 },
    { "signature_algorithm", 0, "ed25519",    0 }
};
#define N_CONVENTIONS ((int)(sizeof CONVENTIONS / sizeof CONVENTIONS[0]))

/* Profile image/1 -- spec/PROFILE-IMAGE.md section 6.  Nine, not twenty-one. */
static const convexp CONVENTIONS_IMAGE[] = {
    { "endianness",          0, "le",         0 },
    { "color_space_default", 0, "srgb",       0 },
    { "pixel_origin",        0, "top-left",   0 },
    { "alpha_mode",          0, "straight",   0 },
    { "alignment_bytes",     1, NULL,      16.0 },
    { "text_encoding",       0, "utf-8",      0 },
    { "id_case",             0, "kebab-case", 0 },
    { "hash_algorithm",      0, "sha256",     0 },
    { "signature_algorithm", 0, "ed25519",    0 }
};
#define N_CONVENTIONS_IMAGE     ((int)(sizeof CONVENTIONS_IMAGE / sizeof CONVENTIONS_IMAGE[0]))

/* The six conventions EVERY reader depends on to read any werk at all --
   the container, the manifest and the envelope frame -- whatever the
   profile.  A reader that does not have a package's profile built in
   still checks these (SPEC.md section 10.3); the profile's own
   conventions govern payload meaning it does not claim. */
static const convexp CONVENTIONS_BASE[] = {
    { "endianness",          0, "le",         0 },
    { "alignment_bytes",     1, NULL,      16.0 },
    { "text_encoding",       0, "utf-8",      0 },
    { "id_case",             0, "kebab-case", 0 },
    { "hash_algorithm",      0, "sha256",     0 },
    { "signature_algorithm", 0, "ed25519",    0 }
};
#define N_CONVENTIONS_BASE      ((int)(sizeof CONVENTIONS_BASE / sizeof CONVENTIONS_BASE[0]))

static int check_conventions(const jval *conv, const char *profile,
                             const char *schema_path, strlist *rep)
{
    static const char *SH[4] = { "dc", "y", "z", "x" };
    const convexp *table;
    int    n_table, want_sh;
    int    ok = 1, i;
    int    foreign_profile = 0;
    size_t k;

    if (!conv || conv->t != J_OBJ) {
        sl_addf(rep, "CONVENTIONS  missing or not an object -- refusing to "
                     "interpret any payload (SPEC.md section 10 step 3)");
        return 0;
    }

    if (profile && strcmp(profile, "3d-entity/1") == 0) {
        table = CONVENTIONS; n_table = N_CONVENTIONS; want_sh = 1;
    } else if (profile && strcmp(profile, "image/1") == 0) {
        table = CONVENTIONS_IMAGE; n_table = N_CONVENTIONS_IMAGE; want_sh = 0;
    } else {
        /* Not a complaint about the package: an admission about this reader
           (S-25).  ONE unsupported-profile line; listing, hashing and
           extraction all still happen, only payload meaning is off the
           table (law 3, smallest refusal scope) -- and the six base
           conventions this reader itself depends on are checked below. */
        int own = 0;
        for (k = 0; k < conv->nmemb; k++) {
            int base = 0;
            for (i = 0; i < N_CONVENTIONS_BASE; i++)
                if (strcmp(conv->key[k], CONVENTIONS_BASE[i].key) == 0) { base = 1; break; }
            if (!base) own++;
        }
        sl_addf(rep, "unsupported-profile: profile '%s' is not built into this "
                     "reader (it has '3d-entity/1' and 'image/1'). The manifest "
                     "names %s%s%s as the schema that validates it; this bootstrap "
                     "loader carries no JSON Schema validator and did NOT validate "
                     "the manifest against it. The six base conventions were "
                     "checked against this reader; the profile's own %d govern "
                     "payload meaning and were NOT interpreted. Every file is "
                     "still listed, hash-verified and extractable",
                profile ? profile : "(absent)",
                schema_path ? "`" : "", schema_path ? schema_path : "NO manifest_schema",
                schema_path ? "`" : "", own);
        table = CONVENTIONS_BASE; n_table = N_CONVENTIONS_BASE; want_sh = 0;
        foreign_profile = 1;
    }

    for (i = 0; i < n_table; i++) {
        const convexp *e = &table[i];
        jval          *v = jget(conv, e->key);

        if (!v) {
            sl_addf(rep, "CONVENTIONS  '%s' is absent; it is mandatory", e->key);
            ok = 0;
            continue;
        }
        if (e->kind == 0) {
            if (!jstr_eq(v, e->sval)) {
                sl_addf(rep, "CONVENTIONS  '%s' = %s%s%s, this reader supports "
                             "only \"%s\" -- refusing rather than guessing",
                        e->key,
                        v->t == J_STR ? "\"" : "", v->t == J_STR ? v->str : "(non-string)",
                        v->t == J_STR ? "\"" : "", e->sval);
                ok = 0;
            }
        } else if (e->kind == 1) {
            if (v->t != J_NUM || v->num != e->dval) {
                sl_addf(rep, "CONVENTIONS  '%s' is not %g -- refusing rather "
                             "than guessing", e->key, e->dval);
                ok = 0;
            }
        } else if (want_sh) {
            int bad = 0;
            if (v->t != J_ARR || v->nitem != 4) bad = 1;
            else for (k = 0; k < 4; k++) if (!jstr_eq(v->item[k], SH[k])) bad = 1;
            if (bad) {
                sl_addf(rep, "CONVENTIONS  'sh_l1_order' is not "
                             "[\"dc\",\"y\",\"z\",\"x\"] -- refusing rather "
                             "than guessing");
                ok = 0;
            }
        }
    }

    /* Stage 12's two OPTIONAL conventions of profile 1: absent is fine,
       present is checked.  This file used to refuse any package that
       declared them ("declared but unknown"), which no reference fixture
       does and every package of one third-party writer does. */
    if (want_sh) {
        jval *v = jget(conv, "sh_coeff_order");
        if (v && !jstr_eq(v, "coefficient-major")) {
            sl_addf(rep, "CONVENTIONS  'sh_coeff_order' is not "
                         "\"coefficient-major\" -- refusing rather than guessing");
            ok = 0;
        }
        v = jget(conv, "sh_degree");
        if (v && (v->t != J_NUM || v->num < 0 || v->num > 3 ||
                  v->num != (double)(int)v->num)) {
            sl_addf(rep, "CONVENTIONS  'sh_degree' is not an integer 0..3 -- "
                         "refusing rather than guessing");
            ok = 0;
        }
    }

    /* manifest.schema.json sets additionalProperties:false on conventions,
       so a key this reader has never heard of is a convention it cannot
       claim to honour.  Only for a profile this reader has built in: for
       any other, the keys beyond the base six are the PROFILE's and are
       not this reader's to refuse. */
    for (k = 0; !foreign_profile && k < conv->nmemb; k++) {
        int known = 0;
        for (i = 0; i < n_table; i++)
            if (strcmp(conv->key[k], table[i].key) == 0) { known = 1; break; }
        if (want_sh && (strcmp(conv->key[k], "sh_coeff_order") == 0 ||
                        strcmp(conv->key[k], "sh_degree") == 0))
            known = 1;
        if (!known) {
            sl_addf(rep, "CONVENTIONS  '%s' is declared but unknown to this "
                         "reader -- refusing rather than ignoring it",
                    conv->key[k]);
            ok = 0;
        }
    }

    if (ok)
        sl_addf(rep, "CONVENTIONS  all %d %svalues checked and supported",
                n_table, foreign_profile ? "base " : "");
    return ok;
}

/* --- which node types are "not a surprise" ------------------------- */

/* A bootstrap loader interprets no payload, so there is nothing for a
   table of types to gate: every core.* type is its profile's
   constitution, whichever profile that is, and is never skipped; an x.*
   type is the open frontier and is skipped and said so (SPEC.md section
   10 step 8, law 12).  All three bootstrap loaders apply this one rule.
   This file used to carry a table of the core types it had been told
   about; it had drifted five types behind the manifest schema
   (core.tool, core.tool.config, core.geom.points, core.geom.gsplat and
   core.retarget.bind were all reported as unknown), which is the same
   failure as the magic table and has the same cure: no table (ruling 2
   of 2026-10-13). */
static int type_is_known(const char *t)
{
    return t && strncmp(t, "core.", 5) == 0;
}

/* --- file verification -------------------------------------------- */

static void verify_file(wpkg *pk, wfile *wf)
{
    unsigned char *buf;
    size_t         len = 0;
    int            st;

    wf->sha_got[0] = '\0';
    wf->size_got   = -1;

    if (!wf->path || !wf->sha_want || wf->size_want < 0) {
        wf->st = WF_MALFORMED;
        return;
    }
    if (!path_is_safe(wf->path)) { wf->st = WF_BADPATH; return; }

    buf = pkg_read(pk, wf->path, &len, &st);
    if (!buf) {
        switch (st) {
        case PKF_MISSING:     wf->st = WF_MISSING;     break;
        case PKF_UNSUPPORTED: wf->st = WF_UNSUPPORTED; break;
        case PKF_INVALID:     wf->st = WF_INVALID;     break;
        case PKF_BADPATH:     wf->st = WF_BADPATH;     break;
        default:              wf->st = WF_IO;          break;
        }
        return;
    }

    wf->size_got = (long long)len;
    sha256_hex(buf, len, wf->sha_got);
    free(buf);

    /* SPEC.md section 10 step 6: check size, then check sha256. */
    if ((long long)len != wf->size_want) { wf->st = WF_SIZE; return; }
    if (strcmp(wf->sha_got, wf->sha_want) != 0) { wf->st = WF_HASH; return; }
    wf->st = WF_OK;
}

static void verify_version(wpkg *pk, wver *ve)
{
    size_t i;
    if (ve->checked) return;
    ve->valid = 1;
    for (i = 0; i < ve->nf; i++) {
        verify_file(pk, &ve->f[i]);
        if (ve->f[i].st != WF_OK) ve->valid = 0;
    }
    ve->checked = 1;
}

/* --- building the node table -------------------------------------- */

static void build_version(const jval *jv, const jval *meta, wver *ve)
{
    const jval *files;
    const jval *file_formats = jget(meta, "file_formats");
    const char *payload_decl = NULL;
    size_t      i;

    memset(ve, 0, sizeof *ve);
    ve->v = -1;
    jint_of(jv, "v", &ve->v);
    ve->note = jstr_of(jv, "note");

    files = jget(jv, "files");
    if (!files || files->t != J_ARR) return;

    ve->nf = files->nitem;
    ve->f  = (wfile *)xmalloc((ve->nf ? ve->nf : 1) * sizeof(wfile));
    for (i = 0; i < ve->nf; i++) {
        const jval *jf = files->item[i];
        wfile      *wf = &ve->f[i];
        memset(wf, 0, sizeof *wf);
        wf->size_want = -1;
        wf->st        = WF_MALFORMED;
        if (jf && jf->t == J_OBJ) {
            wf->path     = jstr_of(jf, "path");
            wf->sha_want = jstr_of(jf, "sha256");
            wf->role     = jstr_of(jf, "role");
            jint_of(jf, "size", &wf->size_want);
        }
    }

    /* SPEC.md section 3.18: which of these files the node DECLARES to be
       in a defined foreign format -- meta.payload_format for the payload
       file (resolved by section 2.1: payload_file, else the single file,
       else the one file with role "payload"), meta.file_formats by role.
       A declaration beats a sniff: such a file is not an envelope. */
    if (jstr(jget(meta, "payload_format"))) {
        payload_decl = jstr_of(jv, "payload_file");
        if (!payload_decl && ve->nf == 1) payload_decl = ve->f[0].path;
        if (!payload_decl) {
            int hits = 0;
            for (i = 0; i < ve->nf; i++)
                if (ve->f[i].role && strcmp(ve->f[i].role, "payload") == 0) {
                    payload_decl = ve->f[i].path;
                    hits++;
                }
            if (hits != 1) payload_decl = NULL;
        }
    }
    for (i = 0; i < ve->nf; i++) {
        wfile *wf = &ve->f[i];
        if (!wf->path) continue;
        if (payload_decl && strcmp(wf->path, payload_decl) == 0) wf->foreign = 1;
        if (wf->role && file_formats && file_formats->t == J_OBJ &&
            jget(file_formats, wf->role))
            wf->foreign = 1;
    }
}

/* Emit one precise line per unusable file of `ve`, tagged with `tag` so
   the same detail serves both the "this node died" and the "this node
   fell back" story.  Returns the worst node-level classification seen. */
static int report_version_failures(const wnode *nd, const wver *ve,
                                   strlist *rep, const char *tag)
{
    int    worst = ND_NOVERSION;
    size_t k;

    for (k = 0; k < ve->nf; k++) {
        const wfile *wf = &ve->f[k];
        const char  *p  = wf->path ? wf->path : "(no path)";
        if (wf->st == WF_OK) continue;
        switch (wf->st) {
        case WF_MISSING:
            worst = ND_MISSING;
            sl_addf(rep, "%s  node=%s v%lld file=%s reason=missing",
                    tag, nd->id, ve->v, p);
            break;
        case WF_UNSUPPORTED:
            worst = ND_UNSUPPORTED;
            sl_addf(rep, "%s  node=%s v%lld file=%s reason=zip-entry-unsupported "
                         "(the zip method is neither 0/store nor 8/deflate, or "
                         "the entry is encrypted; this loader will not return "
                         "wrong bytes, MINI-SPECS.md section 5.3)",
                    tag, nd->id, ve->v, p);
            break;
        case WF_INVALID:
            worst = ND_CORRUPT;
            sl_addf(rep, "%s  node=%s v%lld file=%s reason=zip-entry-invalid "
                         "(its deflate stream does not decode, or the inflated "
                         "bytes disagree with the directory's size or CRC-32)",
                    tag, nd->id, ve->v, p);
            break;
        case WF_SIZE:
            worst = ND_CORRUPT;
            sl_addf(rep, "%s  node=%s v%lld file=%s reason=size-mismatch "
                         "declared=%lld actual=%lld",
                    tag, nd->id, ve->v, p, wf->size_want, wf->size_got);
            break;
        case WF_HASH:
            worst = ND_CORRUPT;
            sl_addf(rep, "%s  node=%s v%lld file=%s reason=sha256-mismatch "
                         "declared=%s actual=%s",
                    tag, nd->id, ve->v, p, wf->sha_want, wf->sha_got);
            break;
        case WF_BADPATH:
            worst = ND_MALFORMED;
            sl_addf(rep, "%s  node=%s v%lld file=%s reason=unsafe-path "
                         "(escapes the package or is not a relative POSIX path)",
                    tag, nd->id, ve->v, p);
            break;
        case WF_MALFORMED:
            worst = ND_MALFORMED;
            sl_addf(rep, "%s  node=%s v%lld reason=malformed-file-record "
                         "(path, sha256 or size absent)", tag, nd->id, ve->v);
            break;
        default:
            worst = ND_CORRUPT;
            sl_addf(rep, "%s  node=%s v%lld file=%s reason=io-error",
                    tag, nd->id, ve->v, p);
            break;
        }
    }
    return worst;
}

/* SPEC.md section 5: take `active`; if that version is unusable, fall
   back to the newest VALID version with a LOWER v, and report it.  The
   filesystem is never globbed for versions -- versions[] is the only
   authority. */
static void resolve_node(wpkg *pk, wnode *nd, strlist *rep)
{
    size_t i;
    long   best   = -1;
    int    act_ix = -1;

    nd->resolved = -1;

    if (nd->nver == 0) {
        nd->dead = ND_MALFORMED;
        sl_addf(rep, "DEAD      node=%s type=%s reason=malformed-node "
                     "detail=versions[] is absent or empty",
                nd->id ? nd->id : "(no node_id)", nd->type ? nd->type : "(no type)");
        return;
    }

    /* 1. the author's recommendation */
    for (i = 0; i < nd->nver; i++) {
        if (nd->ver[i].v == nd->active) {
            act_ix = (int)i;
            verify_version(pk, &nd->ver[i]);
            if (nd->ver[i].valid) { nd->resolved = (int)i; return; }
            break;
        }
    }

    /* 2. the newest valid version with a lower v */
    for (i = 0; i < nd->nver; i++) {
        wver *ve = &nd->ver[i];
        if (ve->v < 0 || ve->v >= nd->active) continue;
        verify_version(pk, ve);
        if (!ve->valid) continue;
        if (best < 0 || ve->v > nd->ver[best].v) best = (long)i;
    }

    if (best >= 0) {
        nd->resolved = (int)best;
        nd->fallback = 1;
        /* Say WHY the author's version was rejected before saying what was
           used instead: a fallback without a cause is indistinguishable
           from a reader that simply ignored `active`. */
        if (act_ix >= 0) {
            /* The node lives; the failing file of the active version is
               still an error (SPEC.md section 10.1, exit status 1). */
            nd->fallback = 2;
            (void)report_version_failures(nd, &nd->ver[act_ix], rep, "REJECTED");
        }
        else
            sl_addf(rep, "REJECTED  node=%s active=v%lld is not present in "
                         "versions[] at all", nd->id, nd->active);
        sl_addf(rep, "FALLBACK  node=%s active=v%lld unusable, resolved to v%lld "
                     "(newest valid earlier version; SPEC.md section 5)",
                nd->id, nd->active, nd->ver[best].v);
        return;
    }

    /* 3. nothing usable -- classify by the worst thing seen on the version
          the author recommended, so the report says WHY. */
    if (act_ix >= 0) {
        nd->dead = report_version_failures(nd, &nd->ver[act_ix], rep, "DEAD    ");
    } else {
        nd->dead = ND_NOVERSION;
    }
    if (nd->dead == ND_NOVERSION)
        sl_addf(rep, "DEAD      node=%s reason=no-valid-version active=v%lld "
                     "and no earlier version verifies", nd->id, nd->active);
}

static wnode *find_node(wmanifest *m, const char *id)
{
    size_t i;
    if (!id) return NULL;
    for (i = 0; i < m->nnode; i++)
        if (m->node[i].id && strcmp(m->node[i].id, id) == 0) return &m->node[i];
    return NULL;
}

/* SPEC.md section 5: "A requires edge into a dead node kills the source
   node too; an enhances edge into a dead node costs exactly one
   feature."  A `requires` edge to a node absent from nodes[] kills the
   same way (requires-missing-node); an `enhances` edge to one is
   edge-dangling.
   Two passes, deliberately.  The first runs the `requires` kill to a
   fixpoint so a chain of requires propagates.  The second reports the
   `enhances` degradations exactly once, which it could not do inside the
   fixpoint loop without repeating itself on every sweep. */
static void propagate_requires(wmanifest *m)
{
    int    changed = 1;
    size_t i, k;

    while (changed) {
        changed = 0;
        for (i = 0; i < m->nnode; i++) {
            wnode      *nd = &m->node[i];
            const jval *edges;

            if (nd->dead) continue;
            edges = jget(nd->jnode, "edges");
            if (!edges || edges->t != J_ARR) continue;

            for (k = 0; k < edges->nitem; k++) {
                const jval *e    = edges->item[k];
                const char *to   = jstr_of(e, "to");
                const char *kind = jstr_of(e, "kind");
                const wnode *tgt;

                if (!to || !kind || strcmp(kind, "requires") != 0) continue;
                tgt = find_node(m, to);

                if (!tgt) {
                    sl_addf(&m->report,
                            "DEAD      node=%s reason=requires-missing-node "
                            "target=%s is not in nodes[]", nd->id, to);
                    nd->dead = ND_REQUIRES_DEAD;
                    changed = 1;
                    break;
                }
                if (tgt->dead) {
                    sl_addf(&m->report,
                            "DEAD      node=%s reason=requires-dead-node "
                            "target=%s (SPEC.md section 5)", nd->id, to);
                    nd->dead = ND_REQUIRES_DEAD;
                    changed = 1;
                    break;
                }
            }
        }
    }

    for (i = 0; i < m->nnode; i++) {
        const wnode *nd = &m->node[i];
        const jval  *edges = jget(nd->jnode, "edges");
        if (nd->dead) continue;
        if (!edges || edges->t != J_ARR) continue;
        for (k = 0; k < edges->nitem; k++) {
            const jval  *e    = edges->item[k];
            const char  *to   = jstr_of(e, "to");
            const char  *kind = jstr_of(e, "kind");
            const wnode *tgt;
            if (!to || !kind || strcmp(kind, "enhances") != 0) continue;
            tgt = find_node(m, to);
            if (!tgt)
                sl_addf(&m->report,
                        "DEGRADED  node=%s reason=edge-dangling target=%s is not "
                        "in nodes[]; the 'enhances' edge loses one feature",
                        nd->id, to);
            else if (tgt->dead)
                sl_addf(&m->report,
                        "DEGRADED  node=%s reason=enhances-dead-node target=%s; "
                        "the 'enhances' edge loses one feature", nd->id, to);
        }
    }
}

static const char *node_status(const wnode *nd)
{
    switch (nd->dead) {
    case ND_MISSING:       return "dead-missing";
    case ND_CORRUPT:       return "dead-corrupt";
    case ND_UNSUPPORTED:   return "dead-unsupported";
    case ND_NOVERSION:     return "dead-no-version";
    case ND_MALFORMED:     return "dead-malformed";
    case ND_REQUIRES_DEAD: return "dead-requires-dead";
    default: break;
    }
    if (nd->unknown_type) return "skipped-unknown-type";
    if (nd->fallback)     return "ok-fallback";
    return "ok";
}

static void manifest_free(wmanifest *m)
{
    size_t i, k;
    for (i = 0; i < m->nnode; i++) {
        for (k = 0; k < m->node[i].nver; k++) free(m->node[i].ver[k].f);
        free(m->node[i].ver);
    }
    free(m->node);
    sl_free(&m->report);
    json_free(m->root);
    memset(m, 0, sizeof *m);
}

/* Load and walk the manifest.  Returns 0 when the container or the
   manifest itself could not be read (the only fatal condition); dead
   nodes are a successful load with bad news in the report. */
static int envelope_report(const unsigned char *buf, size_t len,
                           const char *label, FILE *out);

static int manifest_load(wpkg *pk, wmanifest *m, char *err, size_t errsz)
{
    unsigned char *raw;
    size_t         rawlen = 0;
    int            st;
    char           jerr[256];
    const jval    *nodes;
    size_t         i;
    char           mhash[65];

    memset(m, 0, sizeof *m);
    sl_init(&m->report);

    raw = pkg_read(pk, "MANIFEST.json", &rawlen, &st);
    if (!raw) {
        snprintf(err, errsz, "%s: MANIFEST.json could not be read (%s)",
                 st == PKF_MISSING ? "manifest-absent" : "manifest-unparseable",
                 pkf_name(st));
        return 0;
    }
    m->root = json_parse((const char *)raw, rawlen, jerr, sizeof jerr);
    sha256_hex(raw, rawlen, mhash);
    if (m->root)
        sl_addf(&m->report, "MANIFEST  %lu bytes, sha256 %s",
                (unsigned long)rawlen, mhash);
    free(raw);
    if (!m->root) {
        snprintf(err, errsz, "manifest-unparseable: MANIFEST.json is not valid werk JSON: %s", jerr);
        return 0;
    }
    if (m->root->t != J_OBJ) {
        snprintf(err, errsz, "manifest-structurally-invalid: MANIFEST.json top-level value is not an object");
        return 0;
    }

    /* werk version and profile: reported, never guessed at. */
    {
        const jval *w = jget(m->root, "werk");
        long long   major = -1, minor = -1;
        const char *prof  = jstr_of(m->root, "profile");
        jint_of(w, "major", &major);
        jint_of(w, "minor", &minor);
        sl_addf(&m->report, "FORMAT    werk %lld.%lld profile %s",
                major, minor, prof ? prof : "(absent)");
        if (major != 1)
            sl_addf(&m->report, "FORMAT    warning: this reader implements werk "
                                "major version 1; the package declares %lld", major);
    }

    /* SPEC.md section 10 step 3. */
    m->conventions_ok = check_conventions(jget(m->root, "conventions"),
                                          jstr_of(m->root, "profile"),
                                          jstr_of(m->root, "manifest_schema"),
                                          &m->report);

    /* Container declaration, informative. */
    {
        const jval *c  = jget(m->root, "container");
        const char *cf = jstr_of(c, "form");
        const char *cz = jstr_of(c, "zip_compression");
        sl_addf(&m->report, "CONTAINER opened as %s; manifest declares form=%s "
                            "zip_compression=%s",
                pk->is_zip ? "zip" : "directory",
                cf ? cf : "(absent)", cz ? cz : "(absent)");
    }

    /* SPEC.md section 10 step 4 and section 6: three states, and this
       reader is honest that it can only distinguish two of them. */
    {
        size_t         slen = 0;
        int            sst;
        unsigned char *sig = pkg_read(pk, "SIGNATURE.json", &slen, &sst);
        if (sig) {
            /* What can be checked without Ed25519 is checked: a JSON object
               whose manifest_sha256 is this manifest's.  Damage to a present
               signature is present-and-invalid, never absent and never
               unverified (SPEC.md section 6). */
            char        sh[65], serr[256];
            jval       *sj = json_parse((const char *)sig, slen, serr, sizeof serr);
            const char *declared = (sj && sj->t == J_OBJ)
                                   ? jstr_of(sj, "manifest_sha256") : NULL;
            sha256_hex(sig, slen, sh);
            free(sig);
            m->sig_present = 1;
            if (!sj || sj->t != J_OBJ) {
                m->sig_invalid = 1;
                sl_addf(&m->report,
                        "signature: present-and-invalid -- SIGNATURE.json is not a "
                        "JSON object (%s)", sj ? "another JSON value" : serr);
            } else if (!declared || strcmp(declared, mhash) != 0) {
                m->sig_invalid = 1;
                sl_addf(&m->report,
                        "signature: present-and-invalid -- manifest_sha256 is %s but "
                        "MANIFEST.json hashes to %s: the manifest changed under an "
                        "existing signature", declared ? declared : "(absent)", mhash);
            } else {
                sl_addf(&m->report,
                        "signature: unverified -- SIGNATURE.json is present "
                        "(%lu bytes, sha256 %s) and its manifest_sha256 matches, but "
                        "this loader carries no ed25519 and has NOT checked the "
                        "mathematics. `unverified` is the fourth state word: it is "
                        "not `signed-and-valid` and it is not `absent` (SPEC.md "
                        "section 6 and section 10 step 4).",
                        (unsigned long)slen, sh);
            }
            if (sj) json_free(sj);
        } else if (sst != PKF_MISSING) {
            m->sig_present = 1;
            m->sig_invalid = 1;
            sl_addf(&m->report,
                    "signature: present-and-invalid -- SIGNATURE.json is present but "
                    "cannot be read (%s)", pkf_name(sst));
        } else {
            sl_addf(&m->report,
                    "signature: absent -- this package is anonymous, and "
                    "visibly so. That is a legal state, not an error "
                    "(SPEC.md section 6).");
        }
    }

    nodes = jget(m->root, "nodes");
    if (!nodes || nodes->t != J_ARR) {
        snprintf(err, errsz, "manifest-structurally-invalid: MANIFEST.json has no nodes[] array");
        return 0;
    }

    m->nnode = nodes->nitem;
    m->node  = (wnode *)xmalloc((m->nnode ? m->nnode : 1) * sizeof(wnode));

    for (i = 0; i < m->nnode; i++) {
        const jval *jn = nodes->item[i];
        wnode      *nd = &m->node[i];
        const jval *vers;
        size_t      k;

        memset(nd, 0, sizeof *nd);
        nd->resolved = -1;
        nd->active   = -1;
        nd->jnode    = jn;

        if (!jn || jn->t != J_OBJ) {
            nd->dead = ND_MALFORMED;
            nd->id   = "(malformed)";
            nd->type = "(malformed)";
            sl_addf(&m->report, "DEAD      nodes[%lu] is not an object",
                    (unsigned long)i);
            continue;
        }
        nd->id   = jstr_of(jn, "node_id");
        nd->type = jstr_of(jn, "type");
        jint_of(jn, "active", &nd->active);
        if (!nd->id)   nd->id   = "(no node_id)";
        if (!nd->type) nd->type = "(no type)";

        vers = jget(jn, "versions");
        if (vers && vers->t == J_ARR && vers->nitem > 0) {
            nd->nver = vers->nitem;
            nd->ver  = (wver *)xmalloc(nd->nver * sizeof(wver));
            for (k = 0; k < nd->nver; k++)
                build_version(vers->item[k], jget(jn, "meta"), &nd->ver[k]);
        }

        resolve_node(pk, nd, &m->report);

        /* read-envelope, exercised on every file of the resolved version
           that starts like an envelope and is not DECLARED to be something
           else.  A broken frame kills the node, like any other damage; a
           sound one is counted, so "no envelope complaints" and "no
           envelopes looked at" stop printing the same nothing. */
        if (!nd->dead && nd->resolved >= 0) {
            const wver *rv = &nd->ver[nd->resolved];
            for (k = 0; k < rv->nf && !nd->dead; k++) {
                const wfile   *wf = &rv->f[k];
                unsigned char *ebuf;
                size_t         elen = 0;
                int            est;
                if (wf->foreign || !wf->path) continue;
                ebuf = pkg_read(pk, wf->path, &elen, &est);
                if (!ebuf) continue;
                if (elen >= 4 && is_envelope_magic(ebuf)) {
                    if (envelope_report(ebuf, elen, wf->path, NULL) != 0) {
                        nd->dead     = ND_CORRUPT;
                        nd->resolved = -1;
                        nd->env_bad  = wf->path;
                        sl_addf(&m->report,
                                "DEAD      node=%s file=%s reason=envelope-invalid "
                                "(run --envelope on it for the failed assertion)",
                                nd->id, wf->path);
                    } else {
                        m->n_envelopes++;
                    }
                }
                free(ebuf);
            }
        }

        /* SPEC.md section 10 step 8: an unknown type is skipped and said
           so, and degrades through the same path as a broken one. */
        if (!type_is_known(nd->type)) {
            nd->unknown_type = 1;
            if (!nd->dead)
                sl_addf(&m->report,
                        "SKIP      node=%s type=%s reason=unknown-type; files "
                        "verified, payload not interpreted (SPEC.md section 10 "
                        "step 8)", nd->id, nd->type);
            else
                sl_addf(&m->report,
                        "SKIP      node=%s type=%s reason=unknown-type (node is "
                        "also dead, see above)", nd->id, nd->type);
        }
    }

    propagate_requires(m);

    for (i = 0; i < m->nnode; i++) {
        if (m->node[i].dead)         m->n_dead++;
        else if (m->node[i].unknown_type) m->n_skipped++;
        if (m->node[i].fallback)     m->n_fallback++;
        if (m->node[i].fallback == 2 && !m->node[i].dead) m->n_rejected++;
    }

    sl_addf(&m->report, "ENVELOPES %d frame(s) validated", m->n_envelopes);
    sl_addf(&m->report, "SUMMARY   %lu node(s): %d dead, %d skipped "
                        "(unknown type), %d resolved by fallback",
            (unsigned long)m->nnode, m->n_dead, m->n_skipped, m->n_fallback);
    return 1;
}

/* ================================================================== */
/* 7. The binary envelope  --  ENVELOPE.layout.txt                     */
/*                                                                     */
/* This is the read-envelope capability, and the reason this loader is  */
/* allowed to declare it: everything below is implemented and every     */
/* assertion of section 7's normative pseudocode is checked.            */
/* ================================================================== */

typedef struct { const char *magic; const char *kind; } magickind;

/* The seven RESERVED magics of ENVELOPE.layout.txt section 2 and the kind
   each binds -- a consistency check, not a recogniser.  An envelope is
   recognised by its FRAME (is_envelope_magic, above), never by a table of
   the magics this file happens to know, so a profile-defined or newer
   envelope is validated structurally instead of being passed over in
   silence (ruling 4 of 2026-10-13).  WKX0..WKX9 bind no kind and are
   shared by every profile and extension; the header's `kind` says what
   the payload is.  tests/run_gate_magic.py keeps this table equal to the
   layout file's and to the other three readers'. */
static const magickind ENV_MAGIC[] = {
    { "WKFF", "core.field.flow" },
    { "WKRP", "core.pose.rest"  },
    { "WKAC", "core.anim.clip"  },
    { "WKSK", "core.skeleton"   },
    { "WKEM", "core.embedding"  },
    { "WKPC", "core.geom.points" },
    { "WKGS", "core.geom.gsplat" }
};

/* printf to `out`, or nowhere when out is NULL: the walk validates every
   envelope frame quietly and --envelope prints the same checks. */
static void env_printf(FILE *out, const char *fmt, ...)
{
    va_list ap;
    if (!out) return;
    va_start(ap, fmt);
    vfprintf(out, fmt, ap);
    va_end(ap);
}

/* Returns 0 on success, nonzero when the envelope is malformed.  A
   malformed envelope is a dead node, never a fatal error.  With out ==
   NULL nothing is printed and only the verdict is returned. */
static int envelope_report(const unsigned char *buf, size_t len,
                           const char *label, FILE *out)
{
    char        magic[5];
    uint32_t    version, header_len;
    size_t      p_computed;
    jval       *hdr = NULL;
    char        err[256];
    const jval *secs;
    long long   po = -1, psz = -1;
    const char *kind, *endian;
    const char *expect_kind = NULL;
    size_t      i;
    int         bad = 0;

    env_printf(out, "envelope: %s\n", label);
    env_printf(out, "  file size        : %lu bytes\n", (unsigned long)len);

    if (len < 12) {
        env_printf(out, "  MALFORMED: file is shorter than the 12-byte fixed prefix\n");
        return 1;
    }

    memcpy(magic, buf, 4);
    magic[4] = '\0';
    for (i = 0; i < 4; i++)
        if (buf[i] < 0x20 || buf[i] > 0x7e) magic[i] = '?';

    version    = rd32(buf + 4);
    header_len = rd32(buf + 8);

    env_printf(out, "  magic            : \"%s\"  %02x %02x %02x %02x\n",
            magic, buf[0], buf[1], buf[2], buf[3]);
    env_printf(out, "  version (u32 LE) : %lu\n", (unsigned long)version);
    env_printf(out, "  header_len       : %lu\n", (unsigned long)header_len);

    for (i = 0; i < sizeof ENV_MAGIC / sizeof ENV_MAGIC[0]; i++)
        if (strcmp(magic, ENV_MAGIC[i].magic) == 0) expect_kind = ENV_MAGIC[i].kind;
    if (!is_envelope_magic(buf)) {
        env_printf(out, "  NOT AN ENVELOPE MAGIC (`WK` and two of A-Z or 0-9) -- "
                     "node marked unreadable, load continues "
                     "(ENVELOPE.layout.txt section 2)\n");
        return 1;
    }
    env_printf(out, "  expected kind    : %s\n",
               expect_kind ? expect_kind
                           : "(no reserved kind: the header's `kind` and the "
                             "package's `layouts` map say what this is)");

    if ((size_t)12 + header_len > len) {
        env_printf(out, "  MALFORMED: 12 + header_len (%lu) exceeds the file size\n",
                (unsigned long)(12u + header_len));
        return 1;
    }

    hdr = msgpack_decode(buf + 12, header_len, err, sizeof err);
    if (!hdr) {
        env_printf(out, "  MALFORMED: MessagePack header: %s\n", err);
        return 1;
    }
    if (hdr->t != J_OBJ) {
        env_printf(out, "  MALFORMED: the header is not a MessagePack map\n");
        json_free(hdr);
        return 1;
    }

    /* payload_origin: computed AND declared, and they must agree.  Two
       independent statements of the same fact is how a truncated or
       hand-edited file is caught (ENVELOPE.layout.txt section 1). */
    p_computed = 16u * (((size_t)12 + header_len + 15u) / 16u);
    jint_of(hdr, "payload_origin", &po);
    jint_of(hdr, "payload_size",   &psz);
    kind   = jstr_of(hdr, "kind");
    endian = jstr_of(hdr, "endianness");

    env_printf(out, "  header keys      : %lu\n", (unsigned long)hdr->nmemb);
    env_printf(out, "  kind             : %s\n", kind ? kind : "(absent)");
    env_printf(out, "  endianness       : %s\n", endian ? endian : "(absent)");
    env_printf(out, "  payload_origin   : declared %lld, computed %lu%s\n",
            po, (unsigned long)p_computed,
            (po == (long long)p_computed) ? "  (agree)" : "  <-- DISAGREE");
    env_printf(out, "  payload_size     : %lld\n", psz);

    if (!endian || strcmp(endian, "le") != 0) {
        env_printf(out, "  MALFORMED: header 'endianness' must be exactly \"le\"\n");
        bad = 1;
    }
    if (po != (long long)p_computed) {
        env_printf(out, "  MALFORMED: declared payload_origin does not match the "
                     "computed 16 * ceil((12 + header_len) / 16)\n");
        bad = 1;
    }
    if (psz < 0 || po < 0 || (long long)len != po + psz) {
        env_printf(out, "  MALFORMED: payload_origin + payload_size (%lld) != file "
                     "size (%lu)\n", po + psz, (unsigned long)len);
        bad = 1;
    }
    if (kind && expect_kind && strcmp(kind, expect_kind) != 0) {
        env_printf(out, "  MALFORMED: header 'kind' is '%s' but magic \"%s\" means "
                     "'%s'\n", kind, magic, expect_kind);
        bad = 1;
    }

    secs = jget(hdr, "sections");
    if (!secs || secs->t != J_ARR) {
        env_printf(out, "  MALFORMED: header has no 'sections' array\n");
        json_free(hdr);
        return 1;
    }

    env_printf(out, "\n  %-20s %-8s %10s %10s %8s  %s\n",
            "section", "dtype", "offset", "size", "stride", "shape");
    for (i = 0; i < secs->nitem; i++) {
        const jval *s = secs->item[i];
        const char *nm = jstr_of(s, "name");
        const char *dt = jstr_of(s, "dtype");
        long long   so = -1, ss = -1, st = -1;
        char        shape[128];
        size_t      w = 0;
        const jval *sh;

        jint_of(s, "offset", &so);
        jint_of(s, "size",   &ss);
        jint_of(s, "stride", &st);

        shape[0] = '\0';
        sh = jget(s, "shape");
        if (sh && sh->t == J_ARR) {
            size_t k;
            w += (size_t)snprintf(shape + w, sizeof shape - w, "[");
            for (k = 0; k < sh->nitem && w + 24 < sizeof shape; k++)
                w += (size_t)snprintf(shape + w, sizeof shape - w, "%s%lld",
                                      k ? "," : "",
                                      sh->item[k]->is_int ? sh->item[k]->inum : 0);
            snprintf(shape + w, sizeof shape - w, "]");
        }

        env_printf(out, "  %-20s %-8s %10lld %10lld %8lld  %s\n",
                nm ? nm : "(no name)", dt ? dt : "(no dtype)", so, ss, st, shape);

        if (so < 0 || ss < 0) {
            env_printf(out, "     MALFORMED: section offset/size absent\n");
            bad = 1;
            continue;
        }
        if (so % 16 != 0) {
            env_printf(out, "     MALFORMED: offset is not a multiple of 16 "
                         "(ENVELOPE.layout.txt section 5)\n");
            bad = 1;
        }
        if (so + ss > (long long)len) {
            env_printf(out, "     MALFORMED: section runs past the end of the file\n");
            bad = 1;
        }
        if (so < po) {
            env_printf(out, "     MALFORMED: section starts before payload_origin\n");
            bad = 1;
        }
    }

    /* Section 5: the last section, rounded up to 16, must land exactly on
       payload_origin + payload_size.  Trailing padding is legal, trailing
       data is not. */
    if (secs->nitem > 0 && !bad) {
        const jval *s = secs->item[secs->nitem - 1];
        long long   so = -1, ss = -1, end;
        jint_of(s, "offset", &so);
        jint_of(s, "size",   &ss);
        if (so >= 0 && ss >= 0) {
            end = ((so + ss) + 15) / 16 * 16;
            if (end != po + psz) {
                env_printf(out, "\n  MALFORMED: last section ends at %lld (rounded up "
                             "to 16) but payload_origin + payload_size is %lld -- "
                             "trailing data is not legal\n", end, po + psz);
                bad = 1;
            }
        }
    }

    env_printf(out, "\n  header, decoded:\n  ");
    if (out) {
        json_print(hdr, 1, out);
        fputc('\n', out);
    }
    env_printf(out, "\n  %s\n", bad
            ? "ENVELOPE MALFORMED -- a real load would mark this node dead and continue"
            : "envelope OK: every assertion of ENVELOPE.layout.txt section 7 holds");

    json_free(hdr);
    return bad;
}

/* ================================================================== */
/* 8. Command line                                                     */
/* ================================================================== */

static void usage(FILE *f)
{
    fprintf(f,
"werk_read -- bootstrap reader for the werk container (profile 3d-entity/1)\n"
"capabilities: read-manifest, verify-hashes, read-envelope, materialize\n"
"\n"
"usage:\n"
"  werk_read <package.werk|dir> --list\n"
"      one line per node: node_id, type, active, resolved version, status\n"
"  werk_read <package.werk|dir> --verify\n"
"      verify size and sha256 of every file of every resolved version\n"
"  werk_read <package.werk|dir> --report\n"
"      the full load report: dead nodes, fallbacks, skips, unsupported entries\n"
"  werk_read <package.werk|dir> --extract <node_id> --out <dir>\n"
"      write that node's resolved-version files under <dir>\n"
"  werk_read <package.werk|dir> --cat <path>\n"
"      write one package file's raw bytes to stdout (binary safe)\n"
"  werk_read <package.werk|dir> --envelope <path>\n"
"      parse a custom binary per spec/layouts/ENVELOPE.layout.txt\n"
"  werk_read --selftest\n"
"      run the SHA-256 test vectors of spec/MINI-SPECS.md section 11\n"
"\n"
"  --strict   exit 1 when the load found an error: a dead node, a hash\n"
"             mismatch (also one a version fallback recovered from), an\n"
"             invalid signature\n"
"\n"
"exit (SPEC.md section 10.1): 0 when the container and manifest were read\n"
"      (dead nodes and all); 1 when they were read and --strict tripped or\n"
"      conventions are unsupported; 2 when NOTHING was loaded (not a zip,\n"
"      zip64, no or unparseable MANIFEST.json, or a bad command line).\n"
"\n"
"This reader is read-only. It never writes into the package and never\n"
"executes anything it finds there (SPEC.md section 7.1).\n");
}

/* --- --list ------------------------------------------------------- */

static void cmd_list(const wmanifest *m)
{
    size_t i;
    printf("%-28s %-22s %6s %8s  %s\n",
           "node_id", "type", "active", "resolved", "status");
    printf("%-28s %-22s %6s %8s  %s\n",
           "----------------------------", "----------------------",
           "------", "--------", "------");
    for (i = 0; i < m->nnode; i++) {
        const wnode *nd = &m->node[i];
        char         act[32], res[32];
        if (nd->active >= 0) snprintf(act, sizeof act, "v%lld", nd->active);
        else                 snprintf(act, sizeof act, "-");
        if (nd->resolved >= 0) snprintf(res, sizeof res, "v%lld", nd->ver[nd->resolved].v);
        else                   snprintf(res, sizeof res, "-");
        printf("%-28s %-22s %6s %8s  %s\n", nd->id, nd->type, act, res,
               node_status(nd));
    }
    printf("\n%lu node(s): %d dead, %d skipped (unknown type), %d fallback\n",
           (unsigned long)m->nnode, m->n_dead, m->n_skipped, m->n_fallback);
}

/* --- --verify ----------------------------------------------------- */

static void cmd_verify(const wmanifest *m)
{
    size_t i, k;
    int    pass = 0, fail = 0;

    for (i = 0; i < m->nnode; i++) {
        const wnode *nd = &m->node[i];
        const wver  *ve;
        int          vi = nd->resolved;

        if (vi < 0) {
            /* Nothing resolved; report the author's recommended version's
               files so the failure is visible file by file. */
            for (k = 0; k < nd->nver; k++) {
                if (nd->ver[k].v != nd->active) continue;
                ve = &nd->ver[k];
                {
                    size_t q;
                    for (q = 0; q < ve->nf; q++) {
                        const wfile *wf = &ve->f[q];
                        /* A file whose bytes verified, in a node that is
                           dead because an envelope's FRAME is broken, used
                           to print "FAIL ... PASS" here and no reason. */
                        if (wf->st == WF_OK && nd->env_bad) {
                            printf("%s  %-52s node=%s v%lld  %s\n",
                                   wf->path == nd->env_bad ? "FAIL" : "DEAD",
                                   wf->path ? wf->path : "(no path)", nd->id, ve->v,
                                   wf->path == nd->env_bad
                                       ? "envelope-invalid (bytes hash as declared; "
                                         "run --envelope on it for the failed assertion)"
                                       : "bytes hash as declared; the node is dead "
                                         "by envelope-invalid in another file");
                            fail += wf->path == nd->env_bad;
                            continue;
                        }
                        printf("FAIL  %-52s node=%s v%lld  %s",
                               wf->path ? wf->path : "(no path)", nd->id, ve->v,
                               wf_name(wf->st));
                        if (wf->st == WF_HASH)
                            printf(" want=%s got=%s", wf->sha_want, wf->sha_got);
                        else if (wf->st == WF_SIZE)
                            printf(" want=%lld got=%lld", wf->size_want, wf->size_got);
                        printf("\n");
                        fail++;
                    }
                }
            }
            if (nd->nver == 0)
                printf("FAIL  %-52s node=%s  MALFORMED-NODE\n", "-", nd->id);
            continue;
        }

        ve = &nd->ver[vi];
        for (k = 0; k < ve->nf; k++) {
            const wfile *wf = &ve->f[k];
            if (wf->st == WF_OK) {
                printf("PASS  %-52s node=%s v%lld  %lld bytes  %s\n",
                       wf->path, nd->id, ve->v, wf->size_want, wf->sha_got);
                pass++;
            } else {
                printf("FAIL  %-52s node=%s v%lld  %s\n",
                       wf->path ? wf->path : "(no path)", nd->id, ve->v,
                       wf_name(wf->st));
                fail++;
            }
        }
    }

    printf("\nverify: %d file(s) PASS, %d FAIL, across %lu node(s) "
           "(%d dead, %d skipped, %d fallback)\n",
           pass, fail, (unsigned long)m->nnode,
           m->n_dead, m->n_skipped, m->n_fallback);
}

/* --- --report ----------------------------------------------------- */

static void cmd_report(const wmanifest *m)
{
    size_t i;
    printf("werk load report\n");
    printf("================\n");
    for (i = 0; i < m->report.n; i++)
        printf("%s\n", m->report.v[i]);
}

/* --- --extract ---------------------------------------------------- */

/* Create every missing component of a directory path.  Existing
   directories are not an error; this is the only place the program
   touches the filesystem outside the package, and it only ever creates
   directories under the --out root the user named. */
static int mkdirs(const char *dir)
{
    char  *tmp = xstrdup(dir);
    size_t i, n = strlen(tmp);

    for (i = 1; i <= n; i++) {
        if (tmp[i] == '/' || tmp[i] == '\\' || tmp[i] == '\0') {
            char save = tmp[i];
            tmp[i] = '\0';
            /* Skip a bare drive prefix such as "F:" */
            if (!(i == 2 && tmp[1] == ':'))
                WR_MKDIR(tmp);       /* an existing directory is fine */
            tmp[i] = save;
            if (save == '\0') break;
        }
    }
    free(tmp);
    return 0;
}

static int cmd_extract(wpkg *pk, const wmanifest *m, const char *node_id,
                       const char *outdir)
{
    const wnode *nd = NULL;
    const wver  *ve;
    size_t       i;
    int          wrote = 0, skipped = 0;

    for (i = 0; i < m->nnode; i++)
        if (m->node[i].id && strcmp(m->node[i].id, node_id) == 0)
            nd = &m->node[i];

    if (!nd) {
        fprintf(stderr, "werk_read: no node with node_id '%s'\n", node_id);
        return 1;
    }
    if (nd->resolved < 0) {
        fprintf(stderr, "werk_read: node '%s' has no valid version (%s); "
                        "nothing extracted\n", node_id, node_status(nd));
        return 1;
    }

    ve = &nd->ver[nd->resolved];
    printf("extracting node=%s type=%s resolved=v%lld -> %s\n",
           nd->id, nd->type, ve->v, outdir);
    if (nd->fallback)
        printf("  note: this is a FALLBACK; the author's active version is v%lld\n",
               nd->active);

    for (i = 0; i < ve->nf; i++) {
        const wfile   *wf = &ve->f[i];
        unsigned char *buf;
        size_t         len = 0;
        int            st;
        char          *full;
        size_t         n;
        char          *slash;
        FILE          *f;

        if (wf->st != WF_OK) {
            /* Never hand out bytes that failed verification. */
            printf("  SKIP  %-48s %s (not written)\n",
                   wf->path ? wf->path : "(no path)", wf_name(wf->st));
            skipped++;
            continue;
        }

        buf = pkg_read(pk, wf->path, &len, &st);
        if (!buf) {
            printf("  SKIP  %-48s %s (not written)\n", wf->path, pkf_name(st));
            skipped++;
            continue;
        }

        n = strlen(outdir) + 1 + strlen(wf->path) + 1;
        full = (char *)xmalloc(n);
        snprintf(full, n, "%s/%s", outdir, wf->path);

        slash = strrchr(full, '/');
        if (slash) { *slash = '\0'; mkdirs(full); *slash = '/'; }
        else       { mkdirs(outdir); }

        f = fopen(full, "wb");
        if (!f) {
            printf("  SKIP  %-48s cannot open '%s' for writing\n", wf->path, full);
            skipped++;
        } else {
            size_t put = fwrite(buf, 1, len, f);
            fclose(f);
            if (put != len) {
                printf("  SKIP  %-48s short write\n", wf->path);
                skipped++;
            } else {
                printf("  WROTE %-48s %lu bytes%s%s\n", wf->path,
                       (unsigned long)len,
                       wf->role ? "  role=" : "", wf->role ? wf->role : "");
                wrote++;
            }
        }
        free(full);
        free(buf);
    }

    printf("extracted %d file(s), skipped %d\n", wrote, skipped);
    return 0;
}

/* --- --cat -------------------------------------------------------- */

/* SPEC.md section 10 step 9: never follow a path that is not in some
   files[].  MANIFEST.json and SIGNATURE.json are the two files that by
   construction appear in no node (SPEC.md section 2, decision D-MAN-1),
   so they are named explicitly rather than left unreachable. */
static int path_is_declared(const wmanifest *m, const char *path)
{
    size_t i, k, q;

    if (strcmp(path, "MANIFEST.json") == 0)  return 1;
    if (strcmp(path, "SIGNATURE.json") == 0) return 1;

    for (i = 0; i < m->nnode; i++)
        for (k = 0; k < m->node[i].nver; k++)
            for (q = 0; q < m->node[i].ver[k].nf; q++) {
                const char *p = m->node[i].ver[k].f[q].path;
                if (p && strcmp(p, path) == 0) return 1;
            }
    return 0;
}

static int cmd_cat(wpkg *pk, const wmanifest *m, const char *path)
{
    unsigned char *buf;
    size_t         len = 0;
    int            st;

    if (!path_is_safe(path)) {
        fprintf(stderr, "werk_read: '%s' is not a safe package-relative path\n", path);
        return 1;
    }
    if (!path_is_declared(m, path)) {
        fprintf(stderr,
                "werk_read: refusing to read '%s': it is not listed in any node "
                "version's files[]. Nothing floats (SPEC.md section 2, section 10 "
                "step 9).\n", path);
        return 1;
    }

    buf = pkg_read(pk, path, &len, &st);
    if (!buf) {
        fprintf(stderr, "werk_read: cannot read '%s': %s\n", path, pkf_name(st));
        return 1;
    }

    WR_STDOUT_BINARY();
    if (len && fwrite(buf, 1, len, stdout) != len) {
        fprintf(stderr, "werk_read: short write to stdout\n");
        free(buf);
        return 1;
    }
    fflush(stdout);
    free(buf);
    return 0;
}

/* --- --envelope --------------------------------------------------- */

static int cmd_envelope(wpkg *pk, const wmanifest *m, const char *path)
{
    unsigned char *buf;
    size_t         len = 0;
    int            st, rc;

    if (!path_is_safe(path)) {
        fprintf(stderr, "werk_read: '%s' is not a safe package-relative path\n", path);
        return 1;
    }
    if (!path_is_declared(m, path)) {
        fprintf(stderr,
                "werk_read: refusing to read '%s': it is not listed in any node "
                "version's files[] (SPEC.md section 10 step 9).\n", path);
        return 1;
    }
    buf = pkg_read(pk, path, &len, &st);
    if (!buf) {
        fprintf(stderr, "werk_read: cannot read '%s': %s\n", path, pkf_name(st));
        return 1;
    }
    rc = envelope_report(buf, len, path, stdout);
    free(buf);
    /* A malformed envelope is a dead node, not a failed load (law 3): the
       failure is reported in full on stdout and the process still exits 0,
       exactly as a corrupt payload node does.  `rc` is deliberately
       discarded here for that reason. */
    (void)rc;
    return 0;
}

/* --- main --------------------------------------------------------- */

int main(int argc, char **argv)
{
    const char *pkgpath = NULL;
    const char *node_id = NULL;
    const char *outdir  = NULL;
    const char *catpath = NULL;
    const char *envpath = NULL;
    int         do_list = 0, do_verify = 0, do_report = 0;
    int         do_extract = 0, strict = 0;
    int         i, rc = 0;
    wpkg        pk;
    wmanifest   m;
    char        err[512];

    if (argc < 2) { usage(stdout); return 2; }

    for (i = 1; i < argc; i++) {
        const char *a = argv[i];
        if (strcmp(a, "--selftest") == 0)  return sha256_selftest();
        else if (strcmp(a, "--help") == 0 || strcmp(a, "-h") == 0) { usage(stdout); return 0; }
        else if (strcmp(a, "--list") == 0)   do_list = 1;
        else if (strcmp(a, "--verify") == 0) do_verify = 1;
        else if (strcmp(a, "--report") == 0) do_report = 1;
        else if (strcmp(a, "--strict") == 0) strict = 1;
        else if (strcmp(a, "--extract") == 0) {
            if (++i >= argc) { fprintf(stderr, "werk_read: --extract needs a node_id\n"); return 2; }
            do_extract = 1; node_id = argv[i];
        } else if (strcmp(a, "--out") == 0) {
            if (++i >= argc) { fprintf(stderr, "werk_read: --out needs a directory\n"); return 2; }
            outdir = argv[i];
        } else if (strcmp(a, "--cat") == 0) {
            if (++i >= argc) { fprintf(stderr, "werk_read: --cat needs a path\n"); return 2; }
            catpath = argv[i];
        } else if (strcmp(a, "--envelope") == 0) {
            if (++i >= argc) { fprintf(stderr, "werk_read: --envelope needs a path\n"); return 2; }
            envpath = argv[i];
        } else if (a[0] == '-') {
            fprintf(stderr, "werk_read: unknown option '%s'\n", a);
            usage(stderr);
            return 2;
        } else if (!pkgpath) {
            pkgpath = a;
        } else {
            fprintf(stderr, "werk_read: unexpected argument '%s'\n", a);
            return 2;
        }
    }

    if (!pkgpath) { usage(stderr); return 2; }
    if (!do_list && !do_verify && !do_report && !do_extract && !catpath && !envpath) {
        fprintf(stderr, "werk_read: nothing to do; pick a mode\n");
        usage(stderr);
        return 2;
    }
    if (do_extract && !outdir) {
        fprintf(stderr, "werk_read: --extract also needs --out <dir>\n");
        return 2;
    }

    /* SPEC.md section 10 step 1. */
    err[0] = '\0';
    if (!pkg_open(&pk, pkgpath, err, sizeof err)) {
        /* SPEC.md section 10.1: a container-scoped refusal.  The message
           begins with its stable code, and the exit status is 2. */
        fprintf(stderr, "[error] %s\n", err);
        fprintf(stderr, "container-scoped refusal: nothing was loaded; exit status 2\n");
        return 2;
    }

    /* Steps 2-8. */
    if (!manifest_load(&pk, &m, err, sizeof err)) {
        fprintf(stderr, "[error] %s\n", err);
        fprintf(stderr, "container-scoped refusal: nothing was loaded; exit status 2\n");
        manifest_free(&m);
        pkg_close(&pk);
        return 2;
    }

    if (!m.conventions_ok) {
        /* Refuse, do not guess (SPEC.md section 10 step 3).  The report is
           still printed, because a refusal that does not say why is
           useless. */
        size_t k;
        fprintf(stderr, "[error] unsupported-convention: REFUSING this package: "
                        "its conventions include values this reader does not "
                        "support.\n");
        for (k = 0; k < m.report.n; k++)
            if (strncmp(m.report.v[k], "CONVENTIONS", 11) == 0)
                fprintf(stderr, "  %s\n", m.report.v[k]);
        manifest_free(&m);
        pkg_close(&pk);
        return 1;
    }

    if (do_report) cmd_report(&m);
    if (do_list) {
        if (do_report) printf("\n");
        cmd_list(&m);
    }
    if (do_verify) {
        if (do_report || do_list) printf("\n");
        cmd_verify(&m);
    }
    if (do_extract) rc |= cmd_extract(&pk, &m, node_id, outdir);
    if (envpath)    rc |= cmd_envelope(&pk, &m, envpath);
    if (catpath)    rc |= cmd_cat(&pk, &m, catpath);

    if (strict && (m.n_dead > 0 || m.n_rejected > 0 || m.sig_invalid)) {
        fprintf(stderr, "werk_read: --strict: %d node(s) dead, %d resolved past a "
                        "failing active version, signature %s\n", m.n_dead,
                m.n_rejected, m.sig_invalid ? "present-and-invalid" : "not invalid");
        rc = 1;
    }

    manifest_free(&m);
    pkg_close(&pk);
    return rc;
}
