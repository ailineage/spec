# ADR-0006: Optional registry and escrow model

- Status: Accepted
- Date: 2026-10-19
- Deciders: Ol1n
- Affects: SPEC.md §2.1, §6.3, §7, §12, §13; REQ-0006–0008, REQ-0303, REQ-0307, REQ-0802–0806

## Context

Embedded metadata does not survive most social platforms, messengers and re-encoders. Verifying a stripped artifact requires looking it up somewhere. Escrowed prompts need a custodian. Revocations need a publication point. At the same time, a mandatory central service would be a single point of failure, a surveillance risk and a reason for companies to refuse adoption.

## Decision

1. **The manifest is self-contained.** Verification of an artifact with its manifest needs only the artifact, the manifest, trust anchors and a clock. No Registry call is required.
2. **The Registry is optional and federated.** Anyone can run one. A Registry stores manifests by `artifact.id` byte-exact, serves lineage chains, supports perceptual lookup for stripped media, and publishes signed revocation lists.
3. **Escrow holds ciphertext only.** The custodian cannot read prompts on its own. Each escrow record is bound to `prompt.hash` and `artifact.id`.
4. **Disclosure is a process, not an API call.** A request states a legal basis; the decision and its outcome are written to an append-only audit log; the plaintext is checked by recomputing the commitment.
5. Registry endpoints are informative in this repository. The normative OpenAPI lives in the `registry` repository.

## Consequences

- Verifiers work offline and in the browser with no backend.
- Stripped artifacts without a Registry are simply `UNPROVENANCED` — an honest result.
- Federation means no global uniqueness of manifests: two Registries may hold different manifests for the same bytes (for example, the same image generated independently). Verifiers report each.
- The key-holding model for escrow (who holds the decryption key, threshold schemes) is left to Registry implementations in 0.1, constrained by REQ-0303. A reference design will be part of the `registry` repository.
- Running an escrow creates legal duties (GDPR retention and erasure, responding to orders). These are flagged for legal review in the roadmap.

## Alternatives

- **Mandatory central registry.** Rejected: single point of failure and control, a privacy target, and a governance problem for a neutral standard.
- **No registry at all.** Rejected: leaves the most common real-world case (metadata stripped) without any recovery path.
- **Blockchain anchoring.** Rejected for 0.x: RFC 3161 timestamps provide time evidence with established legal standing (and eIDAS qualified timestamps as a possible profile) without the cost and permanence problems of public ledgers.
- **Plaintext prompts at the registry with access control.** Rejected: one breach exposes everything; ciphertext-only bounds the damage.
