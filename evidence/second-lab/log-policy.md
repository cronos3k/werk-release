# Trial log policy

The redacted trial logs stay local. They are not in this repository.
Yuvraj Puyam (the second-lab replicator) decides whether to share them.

The local package is `<scratch>/sanitised-logs/`.
It contains 26 sessions from batch 1, batch 2, and the negative control.
It includes the retained seal checks and interrupted session.
The August raw session was not located. This package does not cover that session.

The redaction removes these account details:

- Account email addresses.
- Organization identifiers found in the account attachment.
- Account-synced skill names and their injected listing.
- The local Windows user name, replaced with `<user>`.
- Injected account session context.

The procedure preserves record order, tool-call structures, tool results, and session identifiers.
Account strings inside tool results receive the same redaction.
Each account attachment keeps its record boundary and attachment type.
The procedure replaces its account content with a visible redaction marker.

The manifest records original and redacted SHA-256 hashes, record counts, and tool-call counts.
SHA-256 is a cryptographic hash used to identify exact file bytes.
All 26 source hashes and modification times remained unchanged.
All tool-call counts and session boundaries matched after redaction.
Tool order, tool identifiers, result identifiers, record types and parent links also matched.
Automated scans found no matching email, user name, collected organization identifier, or prefixed synced skill reference.
The procedure removes complete skill-list attachments and explicit skill fields.
Common words that also name skills remain in unrelated program output.

These checks cover known account fields and patterns. They do not establish anonymity for every free-text detail.
Yuvraj must review the package before any outward sharing.

A reviewer can request original sessions from Yuvraj.
The request should identify the redacted session filename and the records needed.
Yuvraj decides whether access is appropriate and how to protect account details.
Do not place original or redacted transcripts in a Git commit.
