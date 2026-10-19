# ADR-0007: Digest format: SHA-256 with an algorithm prefix

- Status: Accepted
- Date: 2026-10-19
- Deciders: Ol1n
- Affects: SPEC.md §5.5, §15; REQ-0230–0233; `schema/defs/hash.json`, `schema/defs/urn-artifact.json`. Resolves OPEN_QUESTIONS.md question 1.

## Context

Digests appear in nearly every manifest field: `artifact.id`, `parents[].id`, `context_refs`, `prompt.hash`, `workflow_hash`, `params_hash`, `version_hash`. If SHA-256 ever has to be replaced, each digest must say which algorithm produced it. Changing the digest format after manifests exist would invalidate all of them, so the format must be fixed before the reference implementation (phase 2).

The two candidates were the algorithm-prefixed hex form already used in the 0.1 draft (`sha256:<hex>`, `urn:sha256:<hex>`) and multihash (varint algorithm code + length + digest, usually multibase-encoded, as in IPFS CIDs).

## Decision

1. Keep the algorithm-prefixed lowercase hex form: `<alg>:<hex>` for digests and `urn:<alg>:<hex>` for artifact identifiers.
2. Define a **digest algorithm registry** in the specification. In 0.1 it contains only `sha256`. Producers MUST use it.
3. Verifiers MUST reject digests with an unknown algorithm or a wrong length as `SCHEMA_INVALID`, never skip them.
4. New algorithms (for example `sha384`, `sha512`, `blake3`) are added by an ADR as a minor version change: a registry entry plus one `anyOf` branch in each digest schema.
5. Multihash is not used.

## Consequences

- No existing fixture, signature or example changes; phase 2 is unblocked.
- Digests remain comparable by eye with `shasum -a 256` output and map one-to-one to in-toto (`{"sha256": "<hex>"}`) and OCI (`sha256:<hex>`) digests.
- Old Verifiers fail closed on manifests that use a newer algorithm (`SCHEMA_INVALID`), which is the safe failure.
- The project maintains a small registry itself instead of reusing the multicodec table.
- `urn:sha256:` is not a registered URN namespace; this is already noted in SPEC.md §15.

## Alternatives

- **Multihash.** Self-describing and compact, with an existing code table. Rejected: opaque to humans and standard tools, needs conversion for in-toto and OCI interop, and its main ecosystem (IPFS) is not a target. Would also have required regenerating every fixture.
- **SHA-256 only, no extension point.** Simplest. Rejected: a later algorithm change would be a format break instead of an additive change.
- **Separate `alg` member next to each digest.** Rejected: doubles the number of fields and lets the algorithm and value drift apart; the prefix keeps them in one string.
