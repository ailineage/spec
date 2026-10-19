# ADR-0004: JCS canonicalization for 0.x

- Status: Accepted
- Date: 2026-10-19
- Deciders: Ol1n
- Affects: SPEC.md §8.1; CANONICALIZATION.md; REQ-0004, REQ-0500, REQ-0501

## Context

The manifest is signed. It is stored pretty-printed in sidecars, compact in PNG chunks, inside C2PA assertions and in Git notes. Signature verification must not depend on whitespace or member order. The options are: sign the exact bytes and forbid reformatting; canonicalize JSON; or use a binary format with deterministic encoding, such as CBOR, which C2PA uses.

## Decision

For all 0.x versions:

1. The manifest is JSON (I-JSON subset, integers only).
2. The signing input is RFC 8785 JCS of the manifest without `signature` and without annotation members.
3. Prompt text uses its own text canonicalization (`utf8-nfc-trim-v1`), because JCS only canonicalizes JSON structure, not Unicode normalization or line endings inside strings.
4. A CBOR profile (deterministic CBOR per RFC 8949 §4.2) is planned for the C2PA embedding. It will be defined by a later ADR as a *second serialization of the same data model*, with a deterministic mapping, so that one logical manifest has exactly one JSON and one CBOR signing input.

## Consequences

- Any JSON library can produce and read manifests; only the signer and verifier need a JCS implementation, available for Go, Python, JavaScript, Java, Rust and .NET.
- Floats are excluded from the manifest, which removes the riskiest part of JCS (number serialization). Floats can still occur in `params_hash` inputs; test vectors cover them.
- The C2PA profile carries JSON inside a CBOR container in 0.x. That works but is not idiomatic C2PA; the CBOR profile fixes it later.
- Duplicate member names must be rejected explicitly, because many JSON parsers silently keep the last value.

## Alternatives

- **No canonicalization; sign exact bytes (JWS-style detached payload).** Rejected: any reformatting breaks the signature; embedding into different containers would require carrying the exact original bytes alongside.
- **JWS / JOSE compact serialization.** Rejected for 0.x: the manifest becomes an opaque base64 blob, unreadable in sidecars and Git notes, and needs a second "unprotected" copy for humans. Algorithm identifiers (`ES256`, `EdDSA`) are still borrowed from JOSE.
- **CBOR (COSE) from the start, as in C2PA.** Rejected for 0.x: tooling for inspection and hand-writing of fixtures is weaker, and the primary adopters of 0.x (gateways, editors, CI) are JSON-native. Kept as the planned second profile.
- **Custom canonical JSON.** Rejected: JCS is published, reviewed and implemented.
