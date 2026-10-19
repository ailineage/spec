# Governance

This document describes how the AILineage specification is maintained and how decisions are made.

## Roles

- **Contributor** — anyone who opens an issue, reviews or sends a pull request.
- **Spec Editor** — a Contributor appointed by the Maintainers to keep SPEC.md coherent: wording, REQ-ID allocation, cross-references, release notes. Editors merge editorial changes.
- **Maintainer** — responsible for the direction of the specification, merging normative changes, releases and these rules.

Current Maintainers:

| Name | Organization | Since |
| --- | --- | --- |
| Ol1n | independent | 2026-10 |

### Becoming a Maintainer

A Contributor becomes eligible after **three merged normative pull requests** (each with an ADR or a substantive ADR revision). An existing Maintainer nominates the Contributor in a public issue; the nomination passes under the lazy-consensus rule below with no Maintainer veto.

A Maintainer who is inactive for 12 months moves to *emeritus* status and can return by request.

## Decision making

- **Lazy consensus.** A pull request may be merged when it has been open for at least **7 days** with at least one Maintainer approval and no unresolved objection. Editorial changes need no waiting period.
- **Normative changes require an ADR.** Any change that adds, removes or alters a MUST/SHOULD/MAY, a schema rule, an enum value or a REQ-ID needs an ADR in `adr/` in the same pull request ([adr/README.md](adr/README.md)).
- **Veto.** Any Maintainer may veto a normative change with a written rationale in the pull request. A veto can be lifted by the vetoing Maintainer or overridden by a two-thirds majority of Maintainers when there are at least three.
- Decisions and their reasons are public: in pull requests, issues and ADRs.

## Versioning and deprecation

- The spec version is `ailineage/<major>.<minor>` (SPEC.md §16).
- **Minor** versions are additive: new optional members, enum values, informative sections. Existing valid manifests stay valid.
- **Major** versions may break compatibility. Each major release requires an ADR and migration notes, and the previous major version remains supported — schema published, fixtures maintained, Verifiers expected to accept it — for at least **6 months** of overlap after the new major is released.
- During `0.x`, minor versions may break compatibility; each break is recorded in an ADR and in CHANGELOG.md.
- Deprecated features are marked in SPEC.md with the version that deprecated them and the earliest version that may remove them.

## Licensing and contributions

- The specification text, schemas, fixtures and examples in this repository are licensed under **CC-BY-4.0** ([LICENSE](LICENSE)).
- Code in sister repositories (`go-ailineage`, `py-ailineage`, `registry`, `verify`) is licensed under **Apache-2.0**. The only code in this repository, the fixture generator `fixtures/regen.py`, is likewise Apache-2.0, declared by its SPDX header.
- Contributions require a **Developer Certificate of Origin** sign-off (`Signed-off-by:` line, `git commit -s`). There is no CLA.

## Neutral home

The project intends to move to a **neutral foundation** — the Linux Foundation, for example through OpenSSF or LF AI & Data — once **at least two organizations are represented among the Maintainers**. Until then, the current Maintainer commits to:

- keeping all decisions public and recorded as described above;
- not registering trademarks or domain names for the project in a way that prevents transfer to a foundation;
- transferring the GitHub organization, domain names and any trademarks to the foundation upon acceptance.

## Code of conduct

All participation is governed by the [Code of Conduct](CODE_OF_CONDUCT.md).
