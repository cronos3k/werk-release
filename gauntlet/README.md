# gauntlet/ — the agent-implementability experiment

The manifesto's law 10 says agent-implementability is **tested, not
asserted**. This folder holds the tests and their numbers.

* [`RESULTS.md`](RESULTS.md) — the measurements: success rate, wall time,
  which embedded resource each agent used, coverage, and every stumble.
  **Run 1** (four agents, four languages) tested a fixture with no custom
  binary and said so in its own conclusions. **Run 2** exists to close that
  gap: a fixture carrying a `WKEM` envelope, and two extra tasks — parse the
  binary payload, and state the recipe and the disclosure in plain language
  from the file alone.
* Each stumble is filed as a spec bug in `../HANDOVER.md`. A stumble is worth
  more than a clean run, which is why the reports are written to surface them
  rather than to look competent.

The experiment is deliberately unkind to the format: an agent is given a file
path and nothing else — no repository, no specification directory, no web —
and must produce a working reader in a named language. If the file cannot
teach it, the file is wrong.
