# Open Questions for 0.1 → 0.2

Decisions the 0.1 draft deliberately leaves open. Each answer should become an ADR (or an amendment to an existing one). Ordered roughly by impact.

1. ~~**Multihash vs SHA-256 only.**~~ **Resolved** by [ADR-0007](adr/0007-digest-format-sha256-extensible.md): SHA-256 with the algorithm prefix, extensible through a digest algorithm registry; no multihash.

2. ~~**Salted prompt commitment.**~~ **Resolved** by [ADR-0008](adr/0008-mandatory-salted-prompt-commitment.md): mandatory per-commitment 32-byte salt for `storage` = `escrow` or `none`; public prompts stay unsalted.

3. **CBOR profile for C2PA.** C2PA assertions are CBOR. Do we define a deterministic-CBOR serialization (RFC 8949 §4.2) of the same data model with its own signing input, or keep JSON inside the C2PA assertion permanently ([ADR-0004](adr/0004-canonicalization-jcs.md))? If CBOR: in 0.2, or together with the phase-5 C2PA work?

4. **Media type and name registrations.** Register `application/vnd.ailineage+json` in the IANA vendor tree now, or wait for an IETF Internet-Draft? Same for the XMP namespace `http://ailineage.org/ns/0.1/`, the PNG keyword `ailineage` and the MP4 box `ailn`. All depend on the `ailineage.org` domain being secured first.

5. **JPEG, WebP and MP4 embedding.** 0.1 puts the manifest in a *second*, dedicated APP1 XMP packet so that removal is a pure byte operation ([REQ-0215]–[REQ-0217]); many XMP readers only read the first packet. Alternatives: a dedicated APP11/JUMBF box (as C2PA does) or a custom APP segment. WebP allows only one XMP chunk, and MP4 removal needs a canonical box-size rewrite rule. Which mechanisms become normative in the `embed/` document?

6. **Escrow key management and GDPR retention.** REQ-0303 forbids the custodian decrypting alone but does not prescribe how keys are held (principal-held key, threshold scheme, HSM with dual control). Separately: how does a data-subject erasure request interact with the evidentiary purpose of escrow ([REQ-0806])? Needs the legal review planned in the roadmap.

7. **TSA trust and legal weight.** Which TSAs should a public Verifier trust by default? Should there be an eIDAS qualified-timestamp profile (e.g. PostSignum, I.CA) for legal weight in the EU, and a self-hosted TSA for CI so tests do not depend on freetsa.org?

8. **Hosted-model identity.** For API models, `version_hash` uses the ad-hoc form `build:<id>` ([REQ-0032]). Should providers co-sign or attest model identity (a provider signature over `model.id` + build), and should there be a registry of canonical `model.id` slugs (provider's API name vs Hugging Face repo name)?

9. **Unknown signing key: broken or unprovenanced?** 0.1 reports a cryptographically valid signature by a key outside the trust policy as `PROVENANCE_BROKEN(KEY_UNTRUSTED)`, as the plan specified. This is strict: an honest manifest from an unknown organisation looks "broken" to a user. Keep it, or report `PROVENANCED` with a warning and leave trust display to the UI?

10. **Fixture 03 naming and `kind` for code edits.** The plan names fixture 03 `03-code-created-…` but gives it a `previous_version` parent, which [REQ-0074] forbids for `kind = created`; the fixture therefore uses `kind = edited`. Rename the file to `03-code-edited-claude-code-sidecar.json`, or should `created` allow `previous_version` for "new content replacing a file"?

## Notes from drafting 0.1

- `AILINEAGE_PLAN.md` was not available when this draft was written. The informative Registry endpoints in SPEC.md §12 are derived from `ROADMAP.md` (manifests, chain, escrow, disclose) and must be reconciled with the phase-3 plan.
- `security@ailineage.org` (SECURITY.md) and `hello@ailineage.org` (CODE_OF_CONDUCT.md) are planned mailboxes that do not exist yet.
- The C2PA mapping in SPEC.md §11.1 (action names, ingredient relationships, IPTC terms for `assisted`) must be validated against the current C2PA 2.x specification in phase 5.
- The Code of Practice commitment numbering in COMPLIANCE_MAP.md follows public summaries of the 10 June 2026 final text and needs checking against the text itself.
