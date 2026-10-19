# Architecture Decision Records

Every normative change to the specification is recorded as an ADR ([GOVERNANCE.md](../GOVERNANCE.md)). ADRs are numbered sequentially and never deleted. A superseded ADR is kept and marked *Superseded by ADR-NNNN*.

## Index

| ADR | Title | Status |
| --- | --- | --- |
| [0001](0001-prompt-as-commitment.md) | Prompt as commitment, not plaintext | Accepted, amended by ADR-0008 |
| [0002](0002-three-state-verification.md) | Three-state verification | Accepted |
| [0003](0003-embed-into-c2pa-and-in-toto.md) | Embed into C2PA and in-toto | Accepted |
| [0004](0004-canonicalization-jcs.md) | JCS canonicalization for 0.x | Accepted |
| [0005](0005-signature-suites.md) | Signature suites: ES256 and EdDSA | Accepted |
| [0006](0006-registry-and-escrow-model.md) | Optional registry and escrow model | Accepted |
| [0007](0007-digest-format-sha256-extensible.md) | Digest format: SHA-256 with an algorithm prefix | Accepted |
| [0008](0008-mandatory-salted-prompt-commitment.md) | Mandatory salted prompt commitment | Accepted |

## Template

Copy the block below into `adr/NNNN-short-title.md`.

```markdown
# ADR-NNNN: Title

- Status: Proposed | Accepted | Superseded by ADR-NNNN | Rejected
- Date: YYYY-MM-DD
- Deciders: names
- Affects: SPEC.md sections, REQ-IDs, schema

## Context

What problem forces a decision? What constraints apply?

## Decision

What we decided, stated so that it can be checked.

## Consequences

What becomes easier, what becomes harder, what follows for implementers.

## Alternatives

Each alternative considered, and why it was not chosen.
```
