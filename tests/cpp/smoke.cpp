// smoke.cpp — proof that C++ opens the same .werk through the same DLL.
//
// This is the third face of the Stage 2 gate: Rust (the crate), Python
// (bindings/python/werk.py, ctypes) and C++ (this file) all go through ONE
// shared library. It links against core/include/werk.h and werk.dll.
//
// Build (Windows, MSVC):
//   cl /nologo /EHsc /std:c++17 /I..\..\core\include smoke.cpp ^
//      ..\..\core\target\release\werk.dll.lib /Fe:smoke.exe
// Build (Windows/Linux, GCC or Clang):
//   g++ -std=c++17 -I../../core/include smoke.cpp -L../../core/target/release \
//       -lwerk -o smoke
//
// Run:  smoke <package.werk|dir>
// Exit: 0 when every assertion holds, 1 otherwise. Assertions are printed, so
//       a failure names itself.

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "werk.h"

static int g_failures = 0;

static void check(bool ok, const char *what) {
    std::printf("  [%s] %s\n", ok ? "PASS" : "FAIL", what);
    if (!ok) ++g_failures;
}

static void check_eq(const char *got, const char *want, const char *what) {
    bool ok = got && want && std::strcmp(got, want) == 0;
    std::printf("  [%s] %s%s\n", ok ? "PASS" : "FAIL", what,
                ok ? "" : (std::string(" (got \"") + (got ? got : "(null)") +
                           "\", wanted \"" + want + "\")").c_str());
    if (!ok) ++g_failures;
}

int main(int argc, char **argv) {
    const char *path = (argc > 1) ? argv[1] : "../fixtures/crate.werk";

    std::printf("werk-core %s, profile %s\n", werk_version(), werk_profile());
    std::printf("opening %s\n", path);

    werk_package *pkg = nullptr;
    int32_t rc = werk_open(path, WERK_OPEN_DEFAULT, &pkg);
    if (rc != WERK_OK) {
        std::printf("  [FAIL] werk_open returned %d: %s\n", rc, werk_last_error());
        return 1;
    }
    check(pkg != nullptr, "werk_open produced a handle");

    // --- identity ---------------------------------------------------------
    std::printf("entity     : %s (%s)\n", werk_entity_name(pkg), werk_entity_uuid(pkg));
    std::printf("manifest   : sha256 %s\n", werk_manifest_sha256(pkg));
    check_eq(werk_package_profile(pkg), "3d-entity/1", "profile is 3d-entity/1");
    check(std::strlen(werk_manifest_sha256(pkg)) == 64, "manifest sha256 is 64 hex chars");

    size_t mlen = 0;
    const uint8_t *mbytes = werk_manifest_bytes(pkg, &mlen);
    check(mbytes != nullptr && mlen > 0, "manifest bytes are reachable");
    check(mbytes[0] == '{', "manifest bytes start with '{'");

    // --- the three signature states ---------------------------------------
    int32_t sig = werk_signature_state(pkg);
    const char *sig_name = sig == WERK_SIG_ABSENT   ? "absent"
                         : sig == WERK_SIG_VALID    ? "signed-and-valid"
                                                    : "present-and-invalid";
    std::printf("signature  : %s (%s)\n", sig_name, werk_signature_detail(pkg));
    check(sig == WERK_SIG_ABSENT || sig == WERK_SIG_VALID || sig == WERK_SIG_INVALID,
          "signature state is one of exactly three values");

    // --- the graph --------------------------------------------------------
    int32_t nodes = werk_node_count(pkg);
    std::printf("nodes      : %d\n", nodes);
    check(nodes > 0, "the package has at least one node");

    int alive = 0, skipped = 0, dead = 0;
    long long total_declared = 0;
    for (int32_t n = 0; n < nodes; ++n) {
        int32_t st = werk_node_status(pkg, n);
        if (st == WERK_NODE_ALIVE) ++alive;
        else if (st == WERK_NODE_SKIPPED) ++skipped;
        else ++dead;

        int32_t vcount = werk_version_count(pkg, n);
        for (int32_t v = 0; v < vcount; ++v) {
            int32_t fcount = werk_file_count(pkg, n, v);
            for (int32_t f = 0; f < fcount; ++f) {
                total_declared += (long long)werk_file_size(pkg, n, v, f);
                // Every version must carry a work note (law 6).
                check(std::strlen(werk_version_note(pkg, n, v)) >= 8,
                      "every version carries a work note of >= 8 characters");
                if (g_failures) break;
            }
            if (g_failures) break;
        }
        if (g_failures) break;
    }
    std::printf("           : %d alive, %d skipped, %d dead, %lld declared bytes\n",
                alive, skipped, dead, total_declared);

    // --- an unknown node type must be SKIPPED, not fatal ------------------
    int32_t xi = werk_node_index(pkg, "x-probe");
    if (xi >= 0) {
        check(werk_node_status(pkg, xi) == WERK_NODE_SKIPPED,
              "an x.* node is skipped, not dead and not fatal");
        check(werk_node_resolved(pkg, xi) > 0,
              "a skipped node still resolves a version (its bytes are verified)");
    }

    // --- blobs -------------------------------------------------------------
    int32_t bi = werk_node_index(pkg, "rest-poses");
    if (bi >= 0) {
        const char *p = werk_file_path(pkg, bi, 0, 0);
        const uint8_t *data = nullptr;
        size_t len = 0;
        check(werk_blob(pkg, p, &data, &len) == WERK_OK, "werk_blob returns the payload");
        check(len == (size_t)werk_file_size(pkg, bi, 0, 0),
              "blob length equals the declared size");
        check(len >= 4 && std::memcmp(data, "WKRP", 4) == 0,
              "the rest-pose payload really is a WKRP envelope");
    }

    // --- the report is the API, not an afterthought ------------------------
    int32_t rcount = werk_report_count(pkg);
    std::printf("report     : %d entries, %d error(s)\n", rcount, werk_report_errors(pkg));
    for (int32_t i = 0; i < rcount && i < 40; ++i) {
        std::printf("  [%s] %s %s%s: %s\n",
                    werk_report_severity(pkg, i), werk_report_code(pkg, i),
                    werk_report_node(pkg, i), werk_report_path(pkg, i),
                    werk_report_message(pkg, i));
    }

    // --- a missing file is an error return, not a crash --------------------
    const uint8_t *nodata = nullptr;
    size_t nolen = 0;
    check(werk_blob(pkg, "no/such/file.bin", &nodata, &nolen) == WERK_ERR_NO_ITEM,
          "asking for a file that is not there returns WERK_ERR_NO_ITEM");
    check(std::strlen(werk_last_error()) > 0, "werk_last_error explains the failure");

    werk_close(pkg);

    std::printf("\n%s: %d failure(s)\n", g_failures ? "FAILED" : "OK", g_failures);
    return g_failures ? 1 : 0;
}
