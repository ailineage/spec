# ADR-0005: Signature suites: ES256 and EdDSA

- Status: Accepted
- Date: 2026-10-19
- Deciders: Ol1n
- Affects: SPEC.md §8.2–8.3; REQ-0120–0122, REQ-0502–0504

## Context

Producers range from a laptop hook to a hosted gateway with an HSM. Verifiers include browsers (WebCrypto), Go and Python SDKs and WASM builds. Each additional algorithm multiplies test vectors and the attack surface (algorithm confusion, weak parameters). C2PA mandates support for ECDSA and EdDSA among others; cloud KMS and HSMs universally support P-256; Ed25519 is the default for developer keys (SSH, Sigstore, did:key).

## Decision

- 0.1 supports exactly two algorithms:
  - `EdDSA` — Ed25519, pure, RFC 8032.
  - `ES256` — ECDSA P-256 with SHA-256, signature as 64-byte `r || s` (RFC 7518 §3.4), not DER.
- **No RSA.** No other curves.
- Keys are identified by `kid`: a DID URL (`did:key` MUST, `did:web` SHOULD be supported by Verifiers) or an X.509 chain in `signature.chain`.
- **Keyless Sigstore signing** (Fulcio short-lived certificate bound to an OIDC identity, Rekor transparency log entry) is a planned *future profile*, defined together with the in-toto mapping. It is not part of 0.1.

## Consequences

- Every Verifier implements two signature checks; both are in WebCrypto, Go's standard library and Python's `cryptography`.
- ES256 covers HSM, cloud KMS and enterprise PKI; EdDSA covers developer and service keys with deterministic signatures.
- Organizations with RSA-only PKI must issue an EC key for AILineage signing.
- Raw `r || s` encoding avoids DER malleability and matches JOSE; implementers must convert from DER when their library emits DER (the fixture generator shows how).

## Alternatives

- **Include RS256 / PS256.** Rejected: large keys and signatures, PKCS#1 v1.5 legacy pitfalls, no benefit for new deployments.
- **Ed25519 only.** Rejected: many HSMs and KMS offerings in regulated sectors still lack Ed25519.
- **Post-quantum (ML-DSA) now.** Deferred: library support in browsers is not yet universal. A hybrid or ML-DSA suite will be added by ADR when it is. Timestamps help: a signature timestamped before a cryptographic break remains attributable to its time.
- **Sigstore keyless as the default.** Deferred: it ties verification to OIDC identity and online transparency logs, which suits CI but not offline media verification.
