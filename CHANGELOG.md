# Changelog

All notable changes to the specification are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Each entry lists affected REQ-IDs and the ADR, so SDKs can track compatibility.

## [Unreleased]

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
