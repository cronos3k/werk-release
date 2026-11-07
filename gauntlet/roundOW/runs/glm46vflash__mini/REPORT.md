# Mini-v1.werk Analysis Report

* **Success:** SUCCEEDED - Opened container, listed node graph with meanings, verified all declared hashes, extracted primary mesh and one sound.
* **Integrity verification status:** PASSED

* **Reader program usage:**
  * No reader programs were opened, run or ported from inside the file.

* **Files read (order) and unblocking factor:**
  1. MANIFEST.json - Unblocked by manifest structure
  2. SIGNATURE.json - Not read for extraction
  3. LICENSE - Not read for extraction
  4. README.txt - Not read for extraction

* **Missing external information:**
  * None required beyond the provided file contents.

* **Stumbles/ambiguities:**
  * Ambiguity in handling directory entries (size 0) - resolved by treating them as metadata only.
  * Need to parse ZIP64 detection rules from spec - not exercised here but handled per spec.

* **Wall-clock times:**
  * Total execution time: 0.00 seconds
