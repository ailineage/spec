# ADR-0003: Embed into C2PA and in-toto

- Status: Accepted
- Date: 2026-10-19
- Deciders: Ol1n
- Affects: SPEC.md §1.1 G4, §10, §11, §15

## Context

Content provenance already has a container standard for media (C2PA, with Content Credentials adoption by camera makers, platforms and generative AI vendors) and software supply chains have a standard attestation framework (in-toto with DSSE, used by SLSA and Sigstore). A new, competing container would fragment tooling and lose on adoption. Neither existing format, however, defines a prompt commitment with escrow and disclosure, an accountable principal for the request, or lineage that crosses from chat to image to video to code.

## Decision

AILineage defines a **payload**, not a container ecosystem.

- In C2PA, the manifest is carried as the assertion `org.ailineage.lineage`, alongside standard `c2pa.actions` with IPTC `digitalSourceType`.
- In in-toto, the manifest without `signature` is the predicate of type `https://ailineage.org/predicate/v0.1`, signed by a DSSE envelope.
- AILineage's own embedding (PNG iTXt, JPEG XMP, sidecar `.lineage.json`, Git notes) is a fallback for formats and workflows those standards do not serve: plain text, source code, chat answers, intermediate pipeline artifacts.
- The AILineage manifest keeps its own signature even when wrapped, so it can be extracted and verified on its own.

## Consequences

- Implementers can add AILineage to an existing C2PA or in-toto pipeline without changing it.
- Mapping tables (SPEC.md §11) must be maintained as C2PA and in-toto evolve.
- Some duplication: a C2PA asset may carry both a C2PA claim signature and the AILineage signature. This is intentional; they cover different statements.
- C2PA uses CBOR; AILineage 0.x is JSON. The C2PA profile carries JSON for now ([ADR-0004](0004-canonicalization-jcs.md)).

## Alternatives

- **Own container everywhere.** Rejected: duplicates C2PA, competes for the same metadata slots, and positions the project against the standards it needs.
- **Only C2PA.** Rejected: C2PA does not cover source code, plain text and Git workflows well, and its trust model centres on claim generators, not on the requesting principal.
- **Only in-toto.** Rejected: in-toto has no embedding into media files and no notion of perceptual identity for stripped media.
- **Propose fields directly into C2PA instead of a separate spec.** Not excluded for the future (roadmap phase 5), but a stand-alone spec with fixtures is needed first to have something concrete to propose.
