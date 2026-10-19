# ADR-0002: Three-state verification

- Status: Accepted
- Date: 2026-10-19
- Deciders: Ol1n
- Affects: SPEC.md §8.4, §9; REQ-0124, REQ-0505–0508, REQ-0600–0611

## Context

Verification results are shown to people who are not specialists: journalists, judges, moderators, readers. A binary "verified / not verified" conflates "nobody signed this" with "somebody tampered with this". A label like "human-made" for unsigned content would be false: most content has no manifest regardless of origin, and metadata stripping by platforms is the norm.

A separate question is what to do when no Time-Stamping Authority (TSA) was available at signing time. One option is a fourth state, `PROVENANCED_UNTIMESTAMPED`.

## Decision

A Verifier outputs exactly one of three states:

- `PROVENANCED` — a manifest for these exact bytes, well-formed, signed by a trusted and unrevoked key, timestamped.
- `UNPROVENANCED` — no manifest found. Explicitly *not* "human" and not "suspicious".
- `PROVENANCE_BROKEN(reason)` — a manifest was found but a check failed. `reason` is one of `SCHEMA_INVALID`, `HASH_MISMATCH`, `KEY_UNTRUSTED`, `SIG_INVALID`, `TS_INVALID`, `KEY_REVOKED`, `PARENT_UNRESOLVABLE`, chosen by the first failing step of a fixed algorithm.

On timestamps:

1. `signature.ts` is **required** by the schema. A manifest without `ts` is `PROVENANCE_BROKEN(SCHEMA_INVALID)`.
2. A Producer that cannot reach a TSA MUST retry or defer publication; it MUST NOT emit an untimestamped manifest.
3. There is **no fourth state**. The degraded case that does occur in practice — a valid token from a TSA the Verifier does not trust — is reported as `PROVENANCED` with the warning `W_TSA_UNTRUSTED`. A Verifier MAY run a strict policy that turns this warning into `TS_INVALID`, and must say so.
4. Warnings (`W_*`) never change the state.

## Consequences

- Users see three outcomes that map to three different actions: trust within policy, no information, investigate.
- Producers need network access to a TSA when signing. Offline generation must queue manifests and sign later; `created_at` then precedes `genTime`, and a delay over 24 hours produces `W_TS_DELAYED`.
- A deterministic step order makes results reproducible across implementations and testable with fixtures.
- Trust in TSAs is local policy. Fixtures use freetsa.org, which test Verifiers must explicitly trust.

## Alternatives

- **Two states (valid / invalid).** Rejected: an unsigned file would look like a forged one, punishing the overwhelming majority of legitimate content.
- **A "human" or "authentic" state.** Rejected: absence of a manifest is not evidence of human origin; claiming otherwise is the error AI detectors make.
- **Fourth state `PROVENANCED_UNTIMESTAMPED`.** Rejected: it would invite Producers to skip the TSA, and the main protection against backdating (THREAT_MODEL T2) would become optional. Every additional top-level state also multiplies UI and policy complexity.
- **Optional `ts`.** Rejected for the same reason as the fourth state.
