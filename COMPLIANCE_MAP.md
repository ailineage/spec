# AILineage Compliance Map 0.1

This document is informative and is **not legal advice**. It maps manifest fields to regulatory and standards regimes. Legal review is pending (roadmap §6).

Two kinds of statements are kept apart throughout:

- **Spec satisfies** — the specification itself provides the technical property a provision asks for, when a Producer implements it.
- **Spec provides evidence** — the manifest records information useful to show compliance; whether a deployment complies remains the provider's or deployer's responsibility.

## Mapping

| Field | Regime | Article / section | How the field helps | What it does not cover | Kind |
| --- | --- | --- | --- | --- | --- |
| whole manifest (signed, embedded or sidecar) | EU AI Act | Art. 50(2): providers of systems generating synthetic audio, image, video or text mark outputs in a machine-readable format, detectable as artificially generated | Machine-readable, signed metadata layer bound to the artifact hash; interoperable via C2PA | Robustness against removal: metadata alone is not robust. The Code of Practice expects multiple layers (e.g. metadata plus watermark). AILineage provides the metadata and lineage layer only. | Spec satisfies the metadata layer; provides evidence for the rest |
| `generation.kind`, `generation.model` | EU AI Act | Art. 50(2) | States that and how AI generated or manipulated the content, and which model | Watermarking, fingerprinting, detection tools | Spec provides evidence |
| `flags: deepfake-candidate` | EU AI Act | Art. 50(4) first subparagraph: deployers disclose deep fakes | Machine-readable signal that a deployer label is warranted | The visible label itself and its placement; exceptions for artistic or satirical works | Spec provides evidence; labelling is the deployer's duty |
| `flags: public-interest-text` | EU AI Act | Art. 50(4) second subparagraph: AI-generated text published to inform the public on matters of public interest | Signal for labelling; `kind = assisted` plus `actor` record human editorial involvement relevant to the editorial-responsibility exception | Whether human review and editorial responsibility actually took place | Spec provides evidence |
| `actor.role`, `actor.on_behalf_of` | EU AI Act | Art. 50(1)–(4): distinct duties for providers and deployers | Records which party acted in which role for each artifact | Determining the legal role of a party | Spec provides evidence |
| `signature.ts`, `artifact.created_at` | EU AI Act | Art. 50(5): information provided at the latest at first interaction or exposure | Trusted time of marking, useful to show marking happened at generation | Timing of the human-facing disclosure | Spec provides evidence |
| whole manifest | EU Code of Practice on marking and labelling of AI-generated content (final, 10 June 2026) | Section for providers, Commitments 1–2: multi-layered machine-readable marking of outputs, and making marks detectable and verifiable | Metadata layer (embedded, C2PA assertion), plus open verification algorithm and fixtures for detection/verification tooling | Watermark layer; provider-side detection API | Spec satisfies one marking layer; provides evidence |
| `flags`, `jurisdiction.regimes` | EU Code of Practice | Section for deployers: labelling of deep fakes and public-interest text, common EU icon | Machine-readable trigger for deployer labelling workflows | The label, the icon and its display | Spec provides evidence |
| `parents[]`, `generation.kind = edited` | C2PA 2.x | `c2pa.actions`, ingredients | Direct mapping to actions and ingredient relationships (SPEC.md §11.1) | C2PA claim signing and trust list | Spec satisfies via the interop profile (phase 5) |
| `generation.kind` | C2PA 2.x / IPTC | `digitalSourceType` | Maps to `trainedAlgorithmicMedia`, `compositeWithTrainedAlgorithmicMedia`, `algorithmicallyEnhanced` | Exact IPTC term choice for edge cases | Spec provides evidence |
| embedded manifest | China: Measures for Labeling AI-Generated Synthetic Content (effective 1 Sep 2025), GB 45438-2025 | Implicit labels: metadata in files identifying synthetic content, the service provider and a content id | Embedded metadata with provider (`model.provider`), principal and content id (`artifact.id`) | Explicit (visible) labels; the exact metadata fields and format required by GB 45438-2025 | Spec provides evidence; a GB 45438 field mapping is needed |
| whole manifest, `signature`, `parents[]` | NIST AI 100-4 (Reducing Risks Posed by Synthetic Content) | Provenance data tracking: metadata recording and digital signatures | Signed provenance metadata with lineage, a technique described by the report | Watermarking, detection, auditing of model capabilities | Spec satisfies the provenance-metadata technique |
| `generation.kind = assisted`, `parents[]` chain, `actor` | U.S. Copyright Office guidance on AI (2023 registration guidance; 2025 Part 2: Copyrightability) | Human authorship requirement; disclosure of AI-generated material in registration | Time-stamped record of which versions were human-authored and where AI assisted; `previous_version` chains show the sequence of human and AI contributions | Whether the human contribution suffices for protection; `assisted` is a self-declaration | Spec provides evidence |

## Notes

- Article 50 applies from 2 August 2026. The Code of Practice is voluntary; adherence can be used to demonstrate compliance once assessed as adequate.
- AILineage deliberately does not define a watermark. Combining it with a watermark (for example a provider's own scheme) gives the multi-layer marking the Code of Practice describes; Verifiers MAY read watermark signals as information only.
- `jurisdiction.regimes` identifiers: `eu-ai-act-art50`, `eu-cop-marking-2026`, `cn-ai-labeling-2025` ([REQ-0100]).

## References

See [SPEC.md §17.2](SPEC.md#172-informative): [AI-ACT], [EU-COP], [CN-LABEL], [NIST-AI-100-4], [USCO], [C2PA], [IPTC-DST].
