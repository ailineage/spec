# Glossary

Informative definitions for terms used in [SPEC.md](SPEC.md).

- **Accountability layer** — information that lets a third party establish who stood behind an artifact and how it was produced, as opposed to whether it is true or AI-made.
- **Actor / principal** — the party accountable for the generation request (`actor.principal`). Not necessarily the signer.
- **Annotation member** — a top-level manifest member whose name starts with `_`; for test fixtures only, ignored by Verifiers and excluded from signing ([REQ-0005]).
- **Artifact** — a byte sequence produced or modified with AI involvement: image, text, code, audio, video, document.
- **Artifact identifier** — `urn:sha256:` over the artifact's hashable bytes (`artifact.id`).
- **Canonicalization** — a deterministic transformation that maps equivalent inputs to identical bytes before hashing (JCS for JSON, `utf8-nfc-trim-v1` for prompts).
- **Chain mode** — verification that also resolves and verifies parent manifests.
- **Commitment** — a hash of canonicalized data published instead of the data, binding the committer to it without revealing it.
- **Context reference** — the identifier of material placed in the model's context window (`prompt.context_refs`).
- **Custodian** — the party holding escrowed prompt ciphertext, usually a Registry.
- **DID** — Decentralized Identifier (W3C DID Core), e.g. `did:key:…`, `did:web:example.com`.
- **Disclosure** — release of an escrowed prompt to a requester, under the declared `disclosure_policy`, recorded in an audit log.
- **Escrow** — encrypted storage of the prompt plaintext by a custodian, referenced by `escrow_ref`.
- **Hashable bytes** — the artifact bytes with any embedded AILineage manifest removed, per container (SPEC.md §5).
- **JCS** — JSON Canonicalization Scheme, RFC 8785.
- **Leaf** — a parent with no manifest; reported `UNPROVENANCED` in a chain report without breaking the child.
- **Lineage chain** — the DAG obtained by following `parents[]` across manifests.
- **Manifest** — the signed JSON object defined by SPEC.md §4 (`application/vnd.ailineage+json`).
- **Perceptual hash** — a fingerprint that stays similar under re-encoding (`artifact.perceptual`), used to find candidates for stripped artifacts.
- **Producer** — software that creates and signs manifests.
- **Pseudonymous** — a principal that cannot be linked to a person without information held outside the manifest.
- **Registry** — an optional service storing manifests, escrow ciphertext, revocations and disclosure audit logs.
- **RFC 3161 token** — a TimeStampToken from a Time-Stamping Authority attesting that data (here: the signature) existed at `genTime`.
- **Sidecar** — a file `<artifact>.lineage.json` next to the artifact, carrying its manifest.
- **Signing input** — the bytes that are signed: UTF-8 JCS of the manifest without `signature` and annotation members.
- **TSA** — Time-Stamping Authority.
- **Verifier** — software that evaluates an artifact and its manifest and outputs `PROVENANCED`, `UNPROVENANCED` or `PROVENANCE_BROKEN(reason)`.
