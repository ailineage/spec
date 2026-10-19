# AILineage

![status: 0.1 draft](https://img.shields.io/badge/spec-0.1%20draft-orange) [![validate](https://github.com/ailineage/spec/actions/workflows/validate.yml/badge.svg)](https://github.com/ailineage/spec/actions/workflows/validate.yml)

**Legally recognizable lineage for AI artifacts: who asked, which model, from what — without disclosing the prompt.**

A signed, RFC 3161-timestamped JSON manifest binds an artifact's hash to an accountable principal, a model, a *commitment* to the prompt and the artifact's parents. Verification yields one of three states:

| State | Meaning |
| --- | --- |
| `PROVENANCED` | A valid manifest for these exact bytes, signed by a trusted key and timestamped. |
| `UNPROVENANCED` | No manifest found. Says nothing about whether AI was involved. |
| `PROVENANCE_BROKEN(reason)` | A manifest exists but a check failed (`SIG_INVALID`, `HASH_MISMATCH`, …). |

Minimal manifest ([fixture 11](fixtures/valid/11-minimal.json)):

<!-- BEGIN GENERATED: minimal-manifest (fixtures/regen.py) -->

```json
{
  "spec": "ailineage/0.1",
  "artifact": {"id": "urn:sha256:5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03", "media_type": "text/plain", "created_at": "2026-10-19T07:55:00Z"},
  "generation": {"kind": "created", "model": {"id": "anthropic/claude-haiku-5-5", "provider": "anthropic.com"}},
  "prompt": {"hash": "sha256:88057a8763d37fbd4318d10d4d8cfc79e1759dcdf8308723b5b8a3ac6b4fcdf4", "canonicalization": "utf8-nfc-trim-salted-v1", "storage": "none", "disclosure_policy": "none", "contains_pii": false},
  "parents": [],
  "actor": {"principal": "did:web:ol1n.com", "role": "operator", "pseudonymous": false},
  "flags": [],
  "signature": {"alg": "EdDSA", "kid": "did:key:z6MkunqAcgKusG7fp3hXi2TXxdTZm7eomDR6ASgvWhLHeu6n#z6MkunqAcgKusG7fp3hXi2TXxdTZm7eomDR6ASgvWhLHeu6n", "ts": "MIISGAYJKoZI…Rk2g==", "sig": "BE1tKJTurKZ_…k_U-AA"}
}
```

`ts` and `sig` are shortened here; the complete, verifiable file is [`fixtures/valid/11-minimal.json`](fixtures/valid/11-minimal.json).

<!-- END GENERATED: minimal-manifest -->

**Read:** [SPEC.md](SPEC.md) · [CANONICALIZATION.md](CANONICALIZATION.md) · [THREAT_MODEL.md](THREAT_MODEL.md) · [COMPLIANCE_MAP.md](COMPLIANCE_MAP.md) · [ADRs](adr/README.md) · [JSON Schema](schema/README.md) · [fixtures](fixtures/README.md) · [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md)

**Relationship to C2PA, in-toto and the AI Act.** AILineage is not a competing container format. Its manifest travels *inside* C2PA (assertion `org.ailineage.lineage`) and in-toto (predicate `https://ailineage.org/predicate/v0.1`), and uses its own sidecar or embedding only where neither applies. It adds what those formats leave out: a prompt commitment with escrow and audited disclosure, an accountable principal, and cross-modal lineage. Under EU AI Act Article 50 it supplies machine-readable provenance evidence; whether a deployment complies remains the deployer's call ([COMPLIANCE_MAP.md](COMPLIANCE_MAP.md)).

**Sister repositories** (planned): `ailineage/go-ailineage` (reference implementation, `ail` CLI) · `ailineage/py-ailineage` · `ailineage/registry` · `ailineage/verify`.

Specification text: [CC-BY-4.0](LICENSE). Code in sister repositories: Apache-2.0. Run `make validate lint test-vectors` before sending a PR ([CONTRIBUTING.md](CONTRIBUTING.md)).
