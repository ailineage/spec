# Changelog

All notable changes to the specification are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Each entry lists affected REQ-IDs and the ADR, so SDKs can track compatibility.

## [Unreleased]

### Added

- ADR-0007: digest format `<alg>:<hex>` with a digest algorithm registry (only `sha256` in 0.1); REQ-0230 to REQ-0233; digest schemas restructured as one `anyOf` branch per algorithm. No fixture changes.
- ADR-0008: mandatory salted prompt commitment. New canonicalization methods `utf8-nfc-trim-salted-v1` and `multimodal-salted-v1`, required for `storage` = `escrow` or `none`; REQ-0052, REQ-0308 to REQ-0311; CANONICALIZATION.md §5 with salted test vectors; THREAT_MODEL T13.

### Changed

- Valid fixtures 01–09, 11 and 12 re-signed with salted commitments and new RFC 3161 tokens. TEST ONLY salts and openings published in `fixtures/data/`; `make validate` verifies every opening.
- Invalid fixtures `escrow-unsalted`, `none-unsalted` and `public-salted` added.
- REQ-0041, REQ-0049, REQ-0303, REQ-0307 and REQ-0804 updated for salted commitments; CANONICALIZATION.md sections renumbered.

## [0.1.0-draft] — 2026-10-19

### Added

- SPEC.md 0.1 with 17 sections and requirement IDs REQ-0001 to REQ-0902.
- JSON Schema `schema/lineage-0.1.json` (draft 2020-12) with conditional rules for prompt storage and parents.
- CANONICALIZATION.md: JCS signing input, `utf8-nfc-trim-v1`, `multimodal-v1`, `params_hash`, generated test vectors.
- THREAT_MODEL.md (12 threats), COMPLIANCE_MAP.md, RELATED_WORK.md, GLOSSARY.md.
- ADR-0001 to ADR-0006.
- 14 valid fixtures with real hashes, Ed25519 and ES256 test signatures and freetsa.org RFC 3161 tokens; 16 invalid fixtures.
- Examples: PNG iTXt embedding, sidecar with header comment, Git notes.
- Governance, contribution, conduct and security policies; CI workflow.
