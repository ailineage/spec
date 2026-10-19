# AILineage Specification 0.1

| | |
| --- | --- |
| Status | **Draft 0.1** — not yet stable; breaking changes possible until 1.0 |
| Spec identifier | `ailineage/0.1` |
| Schema | [`schema/lineage-0.1.json`](schema/lineage-0.1.json) (JSON Schema 2020-12) |
| Editors | Ol1n (maintainer) |
| License | [CC-BY-4.0](LICENSE) |
| Discussion | GitHub issues and pull requests on this repository |

Each normative requirement carries a stable identifier of the form `[REQ-xxxx]`. Identifiers are never reused or renumbered; a removed requirement is marked *Removed in x.y*. SDK test suites SHOULD cite these identifiers.

## Table of contents

1. [Scope and goals](#1-scope-and-goals)
2. [Conformance](#2-conformance)
3. [Terminology](#3-terminology)
4. [Data model](#4-data-model)
5. [Identifiers](#5-identifiers)
6. [Prompt commitment](#6-prompt-commitment)
7. [Lineage chain](#7-lineage-chain)
8. [Signature and timestamp](#8-signature-and-timestamp)
9. [Verification algorithm](#9-verification-algorithm)
10. [Embedding (informative)](#10-embedding-informative)
11. [Interop profiles (informative)](#11-interop-profiles-informative)
12. [Registry API (informative)](#12-registry-api-informative)
13. [Privacy considerations](#13-privacy-considerations)
14. [Security considerations](#14-security-considerations)
15. [IANA and registries considerations](#15-iana-and-registries-considerations)
16. [Versioning](#16-versioning)
17. [References](#17-references)

---

## 1. Scope and goals

AILineage defines a small, signed, timestamped **manifest** that binds an AI-produced or AI-assisted artifact to:

- **who asked** — an accountable principal (possibly pseudonymous),
- **which model** — a model identifier, provider and optionally a weights or build digest,
- **from what** — a cryptographic *commitment* to the prompt, its context and the parent artifacts,

without disclosing the prompt itself. The prompt plaintext stays with its owner or in an encrypted escrow and is released only under a declared disclosure policy.

AILineage is an **accountability layer**. It answers "who stood behind this artifact and how was it made" in a way that can be checked later by a third party and presented as evidence.

### 1.1 Goals

- G1. A manifest is self-contained and verifiable offline given the artifact, trust anchors and a clock.
- G2. Prompts are committed, not published, by default.
- G3. Lineage across tools and modalities (text → image → video, version chains, agent runs) is expressible as a DAG.
- G4. The format embeds into existing provenance ecosystems — C2PA, in-toto — rather than competing with them ([ADR-0003](adr/0003-embed-into-c2pa-and-in-toto.md)).
- G5. Verification yields one of three states with a machine-readable reason ([ADR-0002](adr/0002-three-state-verification.md)).

### 1.2 Non-goals

- **AI detection.** AILineage does not decide whether content "is AI". An artifact without a manifest is `UNPROVENANCED`, not "human".
- **Truthfulness.** A valid manifest says who made a claim and how; it says nothing about whether the content is true.
- **Watermarking.** AILineage does not define or generate watermarks. Watermark signals MAY be read by tools as auxiliary information.
- **Content moderation.** Flags are Producer declarations; they are not policy ([REQ-0093]).
- **Proof of prompt content.** A commitment proves that *some* prompt with the committed hash existed at signing time. It does not prove which prompt until disclosure ([THREAT_MODEL.md](THREAT_MODEL.md) T5).

## 2. Conformance

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in BCP 14 [RFC 2119] [RFC 8174] when, and only when, they appear in all capitals, as shown here.

Sections marked *(informative)* contain no requirements. Examples are informative.

### 2.1 Roles

- **Producer** — software that creates and signs a manifest for an artifact (a generation gateway, a ComfyUI node, an editor hook).
- **Verifier** — software that evaluates an artifact and its manifest and outputs a verification state (§9).
- **Registry** — an OPTIONAL service that stores manifests by `artifact.id`, holds prompt escrow ciphertext, serves lineage chains and records disclosures ([ADR-0006](adr/0006-registry-and-escrow-model.md)).

One implementation MAY play several roles. It MUST then meet the requirements of each role it plays.

### 2.2 General requirements

- **[REQ-0001]** A Producer MUST emit manifests that validate against `schema/lineage-0.1.json` and that satisfy every requirement in this document marked for the Producer role.
- **[REQ-0002]** A Verifier MUST implement the algorithm of §9 and MUST output exactly one of `PROVENANCED`, `UNPROVENANCED`, `PROVENANCE_BROKEN`.
- **[REQ-0003]** Members not defined by this specification MUST NOT appear anywhere in a manifest except inside `extensions` (§4.10) and as annotation members ([REQ-0005]). The schema expresses this with `additionalProperties: false`.
- **[REQ-0004]** A manifest MUST be a single JSON object [RFC 8259] encoded in UTF-8 that conforms to I-JSON [RFC 7493]: no duplicate member names, no lone surrogates, and integers only within ±(2^53−1). The manifest contains no non-integer numbers. A Verifier MUST treat duplicate member names as `SCHEMA_INVALID`.
- **[REQ-0005]** Top-level members whose names match `^_[a-z0-9_]+$` are *annotation members*. They exist for test fixtures (e.g. `"_note"`). Producers MUST NOT emit annotation members in production manifests. Verifiers MUST ignore their content. Annotation members are excluded from the signing input ([REQ-0501]). A Verifier SHOULD emit warning `W_ANNOTATION_PRESENT` when it finds one.
- **[REQ-0006]** A Registry MUST store and serve each manifest exactly as submitted, byte for byte. It MUST NOT add, remove or reorder members.
- **[REQ-0007]** A Registry SHOULD run the §9 algorithm on submission and MUST NOT accept a manifest whose result is `PROVENANCE_BROKEN` with reason `SCHEMA_INVALID`, `SIG_INVALID` or `TS_INVALID`.
- **[REQ-0008]** A Registry that publishes key revocations MUST publish them as a signed, append-only list keyed by `kid` with a revocation time (§8.5).

### 2.3 Conformance table

P = Producer, V = Verifier, R = Registry. "●" means the requirement binds that role.

| REQ | Topic | P | V | R |
| --- | --- | :-: | :-: | :-: |
| 0001 | Schema-valid output | ● | | |
| 0002 | Three-state output | | ● | |
| 0003 | No undefined members | ● | ● | |
| 0004 | I-JSON, no duplicates | ● | ● | ● |
| 0005 | Annotation members | ● | ● | |
| 0006 | Byte-exact storage | | | ● |
| 0007 | Reject broken submissions | | | ● |
| 0008 | Signed revocation list | | | ● |
| 0010–0127 | Data model fields (§4) | ● | ● | |
| 0200–0203 | Artifact identifier | ● | ● | |
| 0210–0222 | Per-format hashing (PNG, JPEG, sidecar, header) | ● | ● | |
| 0230–0233 | Digest format and algorithm registry | ● | ● | ● |
| 0300–0301, 0304 | Prompt commitment | ● | | |
| 0302 | Public prompt re-hash | | ● | |
| 0303, 0307 | Escrow and disclosure | ● | | ● |
| 0306 | `contains_pii` is a declaration | | ● | ● |
| 0400–0406 | Lineage chain | ● | ● | ● |
| 0500–0509 | Signature and timestamp | ● | ● | |
| 0600–0611 | Verification algorithm | | ● | ● |
| 0800–0806 | Privacy | ● | ● | ● |
| 0900–0902 | Versioning | ● | ● | ● |

## 3. Terminology

Full definitions are in [GLOSSARY.md](GLOSSARY.md). The key terms are:

- **Artifact** — a byte sequence produced or modified with AI involvement: an image, text, code file, audio, video, document.
- **Manifest** — the JSON object defined in §4 describing one artifact. Media type `application/vnd.ailineage+json` (§15).
- **Lineage chain** — the directed acyclic graph formed by following `parents[]` from a manifest to the manifests of its parents, recursively.
- **Commitment** — a hash of canonicalized data (here: the prompt) published in place of the data. It binds the Producer to the data without revealing it.
- **Escrow** — encrypted storage of the prompt plaintext, held by a Registry or another custodian, released only per `disclosure_policy`.
- **Disclosure** — the act of releasing an escrowed prompt plaintext to a requester. Anyone can check the plaintext against the commitment.

## 4. Data model

A manifest is a JSON object with the members below. The column *Req.* uses: **MUST** (required), **MAY** (optional), **MUST-IF** (required under a condition). The JSON Schema is normative for structure. The text is normative for semantics. Where they disagree, file a bug; the stricter reading applies until fixed.

Overview:

```text
spec            "ailineage/0.1"
artifact        { id, media_type, created_at, size_bytes?, perceptual? }
generation      { kind, model { id, provider, version_hash?, card_ref? }, runtime? }
prompt          { hash, canonicalization, storage, escrow_ref?, text?, disclosure_policy,
                  contains_pii, system_prompt_hash?, context_refs?, turn_index? }
parents         [ { id, relation, lineage_ref? } ]
actor           { principal, role, pseudonymous, on_behalf_of? }
flags           [ ... ]
jurisdiction?   { produced_in?, regimes? }
extensions?     { "<reverse-dns>": any }
signature       { alg, kid, ts, sig, chain? }
```

### 4.1 `spec`

| Field | Type | Req. | Semantics | Example | REQ |
| --- | --- | --- | --- | --- | --- |
| `spec` | string | MUST | Specification identifier and version. Constant `ailineage/0.1` for this version. | `"ailineage/0.1"` | [REQ-0010] |

- **[REQ-0010]** `spec` MUST be the string `ailineage/0.1`. Versioning rules are in §16.

### 4.2 `artifact`

| Field | Type | Req. | Semantics | Example | REQ |
| --- | --- | --- | --- | --- | --- |
| `artifact` | object | MUST | The artifact described. | | |
| `artifact.id` | string | MUST | `urn:sha256:<64 lowercase hex>` over the artifact's hashable bytes (§5). | `"urn:sha256:3f2a…"` | [REQ-0020] |
| `artifact.media_type` | string | MUST | Media type [RFC 6838], lowercase, optionally with parameters. | `"image/png"`, `"text/x-go; charset=utf-8"` | [REQ-0021] |
| `artifact.created_at` | string | MUST | RFC 3339 time with explicit offset at which the artifact bytes were finalized. | `"2026-10-19T07:00:00Z"` | [REQ-0022] |
| `artifact.size_bytes` | integer | MAY | Length of the hashable bytes (§5). | `10362` | [REQ-0023] |
| `artifact.perceptual` | object | MAY | `{ "alg", "value" }`: perceptual fingerprint for metadata-strip lookups. | `{"alg":"dhash","value":"f0e4c2…"}` | [REQ-0024] |
| `artifact.perceptual.alg` | string | MUST-IF `perceptual` | Perceptual hash algorithm, lowercase. | `"dhash"` | [REQ-0024] |
| `artifact.perceptual.value` | string | MUST-IF `perceptual` | Fingerprint as lowercase hex. | `"f0e4c2a1b3d59687"` | [REQ-0024] |

- **[REQ-0020]** `artifact.id` MUST be computed as specified in §5.
- **[REQ-0021]** `artifact.media_type` MUST be a registered or vendor-tree media type that describes the artifact bytes. Type and subtype MUST be lowercase.
- **[REQ-0022]** `artifact.created_at` MUST include a UTC offset (`Z` or `±hh:mm`). The Producer MUST NOT set it later than the time at which it requests the timestamp (§8.4).
- **[REQ-0023]** If present, `artifact.size_bytes` MUST equal the length in bytes of the hashable bytes defined in §5. A Verifier that finds a mismatch MUST report `HASH_MISMATCH`.
- **[REQ-0024]** `perceptual.alg` names a perceptual hash. Values defined for 0.1: `dhash` (64-bit difference hash, images), `phash` (64-bit DCT hash, images), `chromaprint` (audio fingerprint). Other values MAY be used and MUST be lowercase. `perceptual.value` is lowercase hex. A perceptual match MUST NOT by itself lead to `PROVENANCED` (§9, [REQ-0610]).

### 4.3 `generation`

| Field | Type | Req. | Semantics | Example | REQ |
| --- | --- | --- | --- | --- | --- |
| `generation` | object | MUST | How the artifact was produced. | | [REQ-0030] |
| `generation.model` | object | MUST | The model that produced or assisted. | | [REQ-0031] |
| `generation.kind` | enum | MUST | `created` \| `edited` \| `derived` \| `assisted`. | `"created"` | [REQ-0030] |
| `generation.model.id` | string | MUST | `<provider>/<model>`. | `"anthropic/claude-fable-5-1"`, `"black-forest-labs/flux-schnell"` | [REQ-0031] |
| `generation.model.version_hash` | string | MAY | `sha256:<hex>` over weights, or `build:<id>` reported by an API. SHOULD if self-hosted. | `"build:claude-fable-5-1"` | [REQ-0032] |
| `generation.model.provider` | string | MUST | Domain name or DID of the model provider. | `"anthropic.com"`, `"bfl.ai"` | [REQ-0033] |
| `generation.model.card_ref` | string | MAY | `https` URL of the model card. | `"https://huggingface.co/black-forest-labs/FLUX.1-schnell"` | [REQ-0034] |
| `generation.runtime` | object | MAY | Execution environment. | | [REQ-0035] |
| `generation.runtime.tool` | string | MAY | `<name> <version>` of the generating tool. | `"ComfyUI 0.4.1"`, `"Claude Code 2.x"` | [REQ-0036] |
| `generation.runtime.workflow_hash` | string | MAY | `sha256:<hex>` of the workflow or pipeline definition. | | [REQ-0037] |
| `generation.runtime.seed` | integer | MAY | Random seed, ≥ 0. | `424242` | [REQ-0038] |
| `generation.runtime.params_hash` | string | MAY | `sha256:<hex>` of `JCS(params)` minus volatile keys. | | [REQ-0038] |
| `generation.runtime.volatile` | array of string | MAY | Top-level params keys excluded from `params_hash`. Requires `params_hash`. | `["client_id","queued_at"]` | [REQ-0039] |

- **[REQ-0030]** `generation.kind` MUST be one of:
  - `created` — the model produced a new artifact. Parents, if any, are inputs, references or templates, never a previous version ([REQ-0074]).
  - `edited` — the model modified an existing artifact. At least one parent MUST be present ([REQ-0073]), typically with relation `input` or `previous_version`.
  - `derived` — the model produced a new artifact, possibly of another media type, from one or more parents (image → video, text → speech). At least one parent MUST be present ([REQ-0073]).
  - `assisted` — a human authored the artifact and a model assisted (suggestions, rewording, completion). This is a Producer declaration about the human share; it is not verifiable by this specification.
- **[REQ-0031]** `model.id` MUST match `<provider>/<model>`, where `<provider>` is the lowercase organization slug as used by the provider or its primary distribution hub, and `<model>` is the model name as published. Producers SHOULD use the identifier the provider uses in its API or model hub.
- **[REQ-0032]** `version_hash` MUST be either `sha256:<64 hex>` or `build:<id>` where `<id>` matches `[A-Za-z0-9._:-]{1,128}`. For a single weights file the digest is over the file bytes. For multiple files the digest is over `JCS([...])` of the array of `"sha256:<hex>"` digests of each file, ordered by file name in byte order. A Producer that runs the model itself (self-hosted) SHOULD provide a `sha256:` value. A Producer calling a hosted API SHOULD provide the build or version id reported by the API, prefixed `build:`.
- **[REQ-0033]** `model.provider` MUST be a DNS domain name controlled by the model provider or a DID of the provider.
- **[REQ-0034]** `card_ref`, if present, MUST be an `https` URL.
- **[REQ-0035]** `runtime` MAY be omitted entirely. All its members are optional.
- **[REQ-0036]** `runtime.tool` SHOULD be `<name> <version>`.
- **[REQ-0037]** `runtime.workflow_hash` MUST be `sha256:` over `JCS(workflow)` if the workflow is JSON, otherwise over its raw bytes. Before hashing, the Producer SHOULD replace prompt-bearing values in the workflow with the literal string `<prompt>`, so that the workflow hash does not commit to the prompt a second time without canonicalization.
- **[REQ-0038]** `runtime.seed` MUST be a non-negative integer. `runtime.params_hash` MUST be `sha256:` over the JCS serialization [RFC 8785] of the generation parameter object with the top-level members listed in `volatile` removed (CANONICALIZATION.md §5).
- **[REQ-0039]** `runtime.volatile` lists top-level parameter names that vary between otherwise identical runs (request ids, queue timestamps). If `volatile` is present, `params_hash` MUST be present.

### 4.4 `prompt`

| Field | Type | Req. | Semantics | Example | REQ |
| --- | --- | --- | --- | --- | --- |
| `prompt.hash` | string | MUST | `sha256:<hex>` over the canonicalized prompt. | | [REQ-0040] |
| `prompt.canonicalization` | enum | MUST | `utf8-nfc-trim-v1` \| `multimodal-v1`. | `"utf8-nfc-trim-v1"` | [REQ-0041] |
| `prompt.storage` | enum | MUST | `none` \| `escrow` \| `public`. | `"escrow"` | [REQ-0042] |
| `prompt.escrow_ref` | string | MUST-IF `storage=escrow` | `https` URL or `urn:ailineage:escrow:<host>:<id>`. | `"urn:ailineage:escrow:registry.ailineage.org:01J9…"` | [REQ-0043], [REQ-0044] |
| `prompt.text` | string | MUST-IF `storage=public`; MUST NOT otherwise | Prompt plaintext. | | [REQ-0045] |
| `prompt.disclosure_policy` | enum | MUST | `on-legal-request` \| `owner` \| `public` \| `none`. | `"on-legal-request"` | [REQ-0047] |
| `prompt.contains_pii` | boolean | MUST | Producer declaration whether the prompt contains personal data. | `false` | [REQ-0048] |
| `prompt.system_prompt_hash` | string | MAY | `sha256:<hex>` over the canonicalized system prompt. | | [REQ-0049] |
| `prompt.context_refs` | array of string | MAY | `urn:sha256:` ids of material placed in the model context. | | [REQ-0050] |
| `prompt.turn_index` | integer | MAY | Zero-based position of the prompt in a conversation. | `2` | [REQ-0051] |

- **[REQ-0040]** `prompt.hash` MUST be `sha256:` followed by the 64 lowercase hex digits of SHA-256 over the canonical prompt bytes defined by `prompt.canonicalization` (§6).
- **[REQ-0041]** `prompt.canonicalization` MUST be `utf8-nfc-trim-v1` for text-only prompts and `multimodal-v1` for prompts with non-text attachments. Both are defined in [CANONICALIZATION.md](CANONICALIZATION.md).
- **[REQ-0042]** `prompt.storage` declares where the plaintext lives:
  - `none` — not stored by any party under this specification. The Producer or principal may still hold a copy outside the system.
  - `escrow` — stored as ciphertext by a custodian identified by `escrow_ref`.
  - `public` — included in the manifest as `prompt.text`.
- **[REQ-0043]** If `storage` is `escrow`, `escrow_ref` MUST be present and `text` MUST NOT be present.
- **[REQ-0044]** `escrow_ref` MUST be an `https` URL or a URN `urn:ailineage:escrow:<host>:<id>`, where `<host>` is the custodian's DNS name and `<id>` matches `[A-Za-z0-9_-]{8,128}`. The URN form resolves to `https://<host>/v0/escrow/<id>`.
- **[REQ-0045]** If `storage` is `public`, `text` MUST be present and MUST be the prompt text whose canonical form hashes to `prompt.hash`. `text` MUST NOT be present for any other `storage` value.
- **[REQ-0046]** If `storage` is `none`, neither `escrow_ref` nor `text` may be present.
- **[REQ-0047]** `disclosure_policy` declares who may obtain the plaintext:
  - `on-legal-request` — only upon a request with a documented legal basis (court order, regulator request), via the custodian's disclosure process.
  - `owner` — only the principal (or `on_behalf_of` party) may request it.
  - `public` — anyone. MUST be used when `storage` is `public`.
  - `none` — the plaintext will not be disclosed by any party under this specification.
- **[REQ-0048]** `contains_pii` is a Producer declaration. It is not a guarantee. See [REQ-0306].
- **[REQ-0049]** `system_prompt_hash`, if present, MUST be computed with the same canonicalization method as `prompt.hash`, applied to the system prompt text.
- **[REQ-0050]** Each `context_refs` entry MUST be `urn:sha256:` over the bytes of one item placed in the model context: a file's raw bytes, a retrieved chunk as UTF-8 bytes, or a previous conversation turn in its `utf8-nfc-trim-v1` canonical form. Entries MUST be unique. Order SHOULD follow the order in which items entered the context.
- **[REQ-0051]** `turn_index` MUST be a non-negative integer counting user turns from 0.

### 4.5 `parents`

| Field | Type | Req. | Semantics | Example | REQ |
| --- | --- | --- | --- | --- | --- |
| `parents` | array | MUST | Direct ancestors. MAY be empty. | `[]` | [REQ-0070] |
| `parents[].id` | string | MUST | `urn:sha256:` of the parent artifact. | | [REQ-0071] |
| `parents[].relation` | enum | MUST | `input` \| `reference` \| `previous_version` \| `template`. | `"input"` | [REQ-0071] |
| `parents[].lineage_ref` | string | MAY | Where the parent's manifest can be fetched: `https` URL or `urn:ailineage:registry:<host>:<hex>`. | | [REQ-0076] |

- **[REQ-0070]** `parents` MUST be present. An empty array means no recorded ancestors. Array order carries no meaning.
- **[REQ-0071]** `relation` semantics:
  - `input` — the parent's content was consumed and transformed into this artifact (source image for inpainting, image for image-to-video).
  - `reference` — the parent influenced content or style without being transformed (style reference, retrieved document cited in an answer).
  - `previous_version` — the parent is an earlier version of the same logical artifact (file history).
  - `template` — the parent provided structure (document template, workflow template).
- **[REQ-0072]** No `parents[].id` may equal `artifact.id`. JSON Schema cannot express this rule. A Verifier MUST check it and report `SCHEMA_INVALID` on violation.
- **[REQ-0073]** If `generation.kind` is `edited` or `derived`, `parents` MUST contain at least one entry.
- **[REQ-0074]** If `generation.kind` is `created`, no parent may have relation `previous_version`.
- **[REQ-0075]** The pair (`id`, `relation`) MUST be unique within `parents`. A Verifier MUST report `SCHEMA_INVALID` on violation.
- **[REQ-0076]** `lineage_ref` MUST be an `https` URL returning the parent manifest, or `urn:ailineage:registry:<host>:<64 hex>`, which resolves to `https://<host>/v0/manifests/urn:sha256:<64 hex>`.
- **[REQ-0077]** At most one parent may have relation `previous_version`. A Verifier MUST report `SCHEMA_INVALID` on violation.

### 4.6 `actor`

| Field | Type | Req. | Semantics | Example | REQ |
| --- | --- | --- | --- | --- | --- |
| `actor.principal` | string | MUST | DID or `https` URL of the accountable party. | `"did:web:ol1n.com"` | [REQ-0080] |
| `actor.role` | enum | MUST | `operator` \| `deployer` \| `end-user` \| `system`. | `"operator"` | [REQ-0081] |
| `actor.pseudonymous` | boolean | MUST | Whether `principal` is a pseudonym. | `true` | [REQ-0082] |
| `actor.on_behalf_of` | string | MAY | DID of the party on whose behalf the principal acted. | `"did:web:lineage.ol1n.com"` | [REQ-0083] |

- **[REQ-0080]** `principal` MUST be a DID [DID-CORE] or an `https` URL identifying the party accountable for the generation request. It need not be the signer.
- **[REQ-0081]** `role` semantics: `operator` runs the generating system for itself; `deployer` offers the system to others (AI Act "deployer"); `end-user` submitted the request through someone else's system; `system` is an automated agent acting without a human request in the loop for this artifact.
- **[REQ-0082]** `pseudonymous` MUST be `true` if `principal` cannot be linked to a natural or legal person without information held outside the manifest. See [REQ-0800].
- **[REQ-0083]** `on_behalf_of`, if present, MUST be a DID. It records, for example, that an end-user acted through a deployer.

### 4.7 `flags`

| Field | Type | Req. | Semantics | Example | REQ |
| --- | --- | --- | --- | --- | --- |
| `flags` | array of enum | MUST | Producer declarations. MAY be empty. Unique. | `["deepfake-candidate"]` | [REQ-0090] |

- **[REQ-0090]** `flags` MUST be present and MUST contain only the values below, each at most once.
- **[REQ-0091]** Flag semantics:
  - `deepfake-candidate` — the artifact depicts real persons, objects, places or events in a way that could falsely appear authentic (AI Act Art. 50(4)).
  - `public-interest-text` — text intended to inform the public on matters of public interest (AI Act Art. 50(4) second subparagraph).
  - `minor-depicted-declared` — the Producer declares that a minor may be depicted.
  - `synthetic-voice` — audio contains a synthetic human voice.
  - `training-opt-out` — the rights holder reserves the artifact from use as AI training data.
- **[REQ-0092]** A Producer SHOULD set `deepfake-candidate` and `public-interest-text` whenever its own labelling obligations apply.
- **[REQ-0093]** Flags are declarations of the Producer. A Verifier MUST NOT change the verification state because of a flag, and MUST NOT block, hide or down-rank content because of a flag. A Verifier MAY display flags.

### 4.8 `jurisdiction`

| Field | Type | Req. | Semantics | Example | REQ |
| --- | --- | --- | --- | --- | --- |
| `jurisdiction.produced_in` | string | MAY | ISO 3166-1 alpha-2 country of production. | `"CZ"` | [REQ-0100] |
| `jurisdiction.regimes` | array of string | MAY | Regulatory regimes the Producer considers applicable. | `["eu-ai-act-art50"]` | [REQ-0100] |

- **[REQ-0100]** `regimes` entries MUST be lowercase kebab-case identifiers. Identifiers defined for 0.1: `eu-ai-act-art50`, `eu-cop-marking-2026`, `cn-ai-labeling-2025`. Other identifiers MAY be used. `jurisdiction` is a declaration and creates no obligation for a Verifier.

### 4.9 `signature`

| Field | Type | Req. | Semantics | Example | REQ |
| --- | --- | --- | --- | --- | --- |
| `signature.alg` | enum | MUST | `ES256` \| `EdDSA`. | `"EdDSA"` | [REQ-0120] |
| `signature.kid` | string | MUST | Key identifier: DID URL with fragment, or an opaque id resolvable via `chain` or a Registry. | `"did:key:z6Mk…#z6Mk…"` | [REQ-0121] |
| `signature.ts` | string | MUST | Base64 DER RFC 3161 `TimeStampToken` over SHA-256 of the signature bytes. | | [REQ-0124] |
| `signature.sig` | string | MUST | Base64url (no padding) signature over the signing input. | | [REQ-0122] |
| `signature.chain` | array of string | MAY | PEM X.509 certificates, leaf first. | | [REQ-0127] |

- **[REQ-0120]** `alg` MUST be `ES256` or `EdDSA` as defined in §8.2 ([ADR-0005](adr/0005-signature-suites.md)).
- **[REQ-0121]** `kid` MUST identify the verification key unambiguously (§8.3).
- **[REQ-0122]** `sig` MUST be the base64url encoding without padding [RFC 4648 §5] of the raw signature bytes.
- **[REQ-0123]** The signing input is defined in §8.1.
- **[REQ-0124]** `ts` MUST be present. Its content is defined in §8.4.
- **[REQ-0127]** `chain`, if present, MUST contain PEM-encoded X.509 certificates, leaf first, and the leaf's public key MUST be the key identified by `kid`.

### 4.10 `extensions`

| Field | Type | Req. | Semantics | Example | REQ |
| --- | --- | --- | --- | --- | --- |
| `extensions` | object | MAY | Namespaced extension data. | `{"org.example.review": {"approved": true}}` | [REQ-0110] |

- **[REQ-0110]** Each key in `extensions` MUST be a reverse-DNS name (`^[a-z0-9-]+(\.[a-z0-9-]+)+$`) under a domain controlled by the extension's author. Values are unconstrained JSON (still subject to [REQ-0004]).
- **[REQ-0111]** A Verifier MUST NOT fail verification because of an unknown extension. It SHOULD emit `W_UNKNOWN_EXTENSION`.
- **[REQ-0112]** An extension MUST NOT change the meaning of any member defined by this specification. Extensions MUST NOT carry prompt plaintext ([REQ-0304]).

## 5. Identifiers

### 5.1 Artifact identifier

- **[REQ-0200]** `artifact.id` MUST be `urn:sha256:` followed by the 64 lowercase hex digits of SHA-256 over the **hashable bytes** of the artifact (digest format: §5.5). The hashable bytes are the artifact's bytes with every embedded AILineage manifest removed, as defined per container below.
- **[REQ-0201]** Producers MUST compute the identifier over the final encoded bytes, after any compression or encoding and before embedding the manifest. A Verifier MUST recompute the identifier from the artifact it is given, never trust the manifest's value.
- **[REQ-0202]** The removal procedure MUST be a pure byte operation: it MUST NOT decode and re-encode pixel, audio or text data.
- **[REQ-0203]** Any re-encoding of the artifact (JPEG re-save, image resizing, transcoding, newline conversion) produces different bytes and therefore a different artifact. A service that re-encodes SHOULD emit a new manifest with `generation.kind = derived` and the original as `input` parent. This is why `artifact.perceptual` and the Registry exist (§13, THREAT_MODEL T1).

Normative container rules exist for PNG, JPEG and sidecar files (§5.2–§5.4). Rules for WebP, MP4, PDF and Git are informative in 0.1 (§10) and will be specified in a separate `embed/` document.

### 5.2 PNG

- **[REQ-0210]** The hashable bytes of a PNG file are the file's bytes with every chunk removed whose type is `iTXt` and whose keyword (the bytes up to the first NUL) is exactly `ailineage`. Each removed chunk is removed whole: length, type, data and CRC. All other bytes, including the PNG signature and every other chunk, stay unchanged and in order.
- **[REQ-0211]** A Producer MUST embed at most one `ailineage` iTXt chunk. Its compression flag MUST be 0 and its language tag and translated keyword MUST be empty. Its text MUST be the UTF-8 manifest JSON. A Verifier that finds more than one such chunk MUST report `SCHEMA_INVALID`.
- **[REQ-0212]** The chunk MUST appear after `IHDR` and before `IEND`. A Producer SHOULD place it immediately before `IEND`, so that the hashable bytes equal the original encoder output.

Example: [`examples/png-itxt/`](examples/png-itxt/).

### 5.3 JPEG

- **[REQ-0215]** A Producer embedding into JPEG MUST write the manifest in a dedicated APP1 segment that starts with the XMP identifier `http://ns.adobe.com/xap/1.0/\0` and contains a single XMP packet whose only non-RDF namespace is `http://ailineage.org/ns/0.1/` (prefix `ailineage`). The manifest JSON is the value of property `ailineage:manifest`.
- **[REQ-0216]** The hashable bytes of a JPEG file are the file's bytes with every APP1 segment removed that satisfies [REQ-0215]: XMP identifier present and the namespace `http://ailineage.org/ns/0.1/` declared in the packet. Each removed segment is removed whole: the `FF E1` marker, the length field and the payload. Other APP1 segments, including the main XMP packet, stay unchanged.
- **[REQ-0217]** A Producer MUST NOT write AILineage properties into the main XMP packet, because removing them would require re-serializing XMP and break [REQ-0202].

The dedicated packet sits beside the file's main XMP packet. Most XMP readers read only the first packet; see OPEN_QUESTIONS.md.

### 5.4 Sidecar files and text

- **[REQ-0220]** For a sidecar manifest, the hashable bytes are the artifact file's bytes exactly as stored, with no newline or encoding normalization. The sidecar file MUST be named `<artifact file name>.lineage.json` and placed in the same directory.
- **[REQ-0221]** A text or code file MAY carry a header comment that points to its manifest. The header is a single line within the first three lines of the file containing the token `ailineage: urn:sha256:<64 hex>`, wrapped in the comment syntax of the language (`// ailineage: urn:sha256:…`, `# ailineage: urn:sha256:…`). The hashable bytes are the file's bytes with the first such line removed, including its line terminator. Only the first matching line within the first three lines is removed.
- **[REQ-0222]** The identifier in the header MUST equal `artifact.id`. A Verifier that finds a header with a different identifier MUST report `HASH_MISMATCH`.

Example: [`examples/sidecar/`](examples/sidecar/).

### 5.5 Digest format and algorithm agility

AILineage names the hash algorithm in every digest, so new algorithms can be added without changing the format ([ADR-0007](adr/0007-digest-format-sha256-extensible.md)).

- **[REQ-0230]** Every digest MUST have the form `<alg>:<hex>`, and every artifact identifier the form `urn:<alg>:<hex>`. `<alg>` is a lowercase algorithm name from the digest algorithm registry (§15). `<hex>` is the full, untruncated digest in lowercase hexadecimal, with the length the registry fixes for that algorithm.
- **[REQ-0231]** The registry for 0.1 contains exactly one algorithm, `sha256` (SHA-256, 64 hex digits). Producers MUST use `sha256`.
- **[REQ-0232]** A Verifier MUST report `SCHEMA_INVALID` for a digest whose algorithm it does not implement or whose length does not match the registry. It MUST NOT skip or ignore such a digest.
- **[REQ-0233]** A new algorithm is added only by an ADR, as a minor version change that appends an entry to the registry and a branch to `schema/defs/hash.json` and `schema/defs/urn-artifact.json`. Digests within one manifest MAY use different registered algorithms; each `parents[].id` MUST be identical to the parent manifest's `artifact.id` string.

The RFC 3161 `messageImprint` (§8.4) is not a digest in this sense and stays SHA-256.

## 6. Prompt commitment

### 6.1 What the prompt is

- **[REQ-0300]** `prompt.hash` MUST commit to the prompt as defined in [REQ-0301], canonicalized as specified in [CANONICALIZATION.md](CANONICALIZATION.md) for the declared `canonicalization` method.
- **[REQ-0301]** The *prompt* is the instruction authored by the principal for this generation: in a conversation, the current user turn only. The system prompt is committed separately in `system_prompt_hash`. Material placed in context (files, retrieved chunks, earlier turns) is committed in `context_refs`. Images or other non-text inputs given together with the instruction are attachments under `multimodal-v1`.

[ADR-0001](adr/0001-prompt-as-commitment.md) records why the prompt is committed rather than published.

### 6.2 Storage semantics

The `storage` value changes what a manifest reveals and who can later check it.

| `storage` | In manifest | Plaintext held by | Who can check the commitment |
| --- | --- | --- | --- |
| `none` | hash only | nobody under this spec | whoever later obtains the plaintext from the principal |
| `escrow` | hash + `escrow_ref` | custodian, as ciphertext | the requester after disclosure; anyone the plaintext is shown to |
| `public` | hash + `text` | everyone | every Verifier ([REQ-0302]) |

- **[REQ-0302]** If `storage` is `public`, a Verifier MUST recompute the hash from `prompt.text` using the declared canonicalization and MUST report `HASH_MISMATCH` if it differs from `prompt.hash`.
- **[REQ-0303]** An escrow custodian MUST store only ciphertext. The record MUST bind to `prompt.hash` and `artifact.id`, so that a disclosed plaintext can be checked against the commitment. The decryption key MUST NOT be held by the custodian alone in a form that allows decryption without the disclosure process of [REQ-0307].
- **[REQ-0304]** A Producer MUST NOT place prompt plaintext, or any reversible encoding of it, anywhere in the manifest other than `prompt.text` under `storage = public`. This includes `extensions`, `runtime` and `context_refs`.
- **[REQ-0305]** If `disclosure_policy` is `public`, `storage` SHOULD be `public` or `escrow`. If `storage` is `public`, `disclosure_policy` MUST be `public`.
- **[REQ-0306]** `contains_pii` is a Producer declaration, not a guarantee. A Verifier or Registry MUST NOT treat `contains_pii = false` as evidence that a prompt contains no personal data.

### 6.3 Disclosure

- **[REQ-0307]** A custodian MUST release an escrowed prompt only as permitted by `disclosure_policy`. Every disclosure request and its outcome MUST be recorded in an append-only audit log with at least: the escrow id, `prompt.hash`, the requester identity, the stated legal basis, the decision, the deciding party and the time. The disclosed plaintext is verified by any party by recomputing `prompt.hash`.

A commitment does not prove which prompt was used before disclosure. It proves that the Producer bound itself, at the time shown by `signature.ts`, to exactly one canonical prompt.

## 7. Lineage chain

- **[REQ-0400]** The graph formed by `parents` across manifests MUST be acyclic. It need not be a tree: an artifact may have many parents and a parent many children. A Verifier that detects a cycle while resolving parents MUST report `PARENT_UNRESOLVABLE`.
- **[REQ-0401]** Self-reference is forbidden ([REQ-0072]).
- **[REQ-0402]** A parent with relation `previous_version` MUST have the same media type (type and subtype, compared case-insensitively, parameters ignored) as the child. Exceptions require an ADR; none are defined in 0.1. A Verifier that resolves the parent and finds different media types MUST report `SCHEMA_INVALID`.
- **[REQ-0403]** `lineage_ref` resolution: an `https` URL is fetched with `Accept: application/vnd.ailineage+json`. A `urn:ailineage:registry:<host>:<hex>` URN is resolved per [REQ-0076]. A parent without `lineage_ref` MAY be looked up by `id` in Registries the Verifier is configured with.
- **[REQ-0404]** The resolved parent manifest's `artifact.id` MUST equal the `parents[].id` that pointed to it. Otherwise the Verifier MUST report `PARENT_UNRESOLVABLE`.
- **[REQ-0405]** A Verifier in chain mode MUST bound the resolution depth. The default limit is **16**. Parents beyond the limit are not evaluated and the Verifier MUST emit `W_DEPTH_LIMIT`. Reaching the limit does not change the state.
- **[REQ-0406]** A parent that has no `lineage_ref` and cannot be found in any configured Registry is a *leaf*: it is reported as `UNPROVENANCED` in the chain report with `W_PARENT_UNPROVENANCED`, and it does not change the child's state. A parent whose `lineage_ref` is present but cannot be fetched, or whose fetched manifest verifies as `PROVENANCE_BROKEN`, makes the child `PROVENANCE_BROKEN` with reason `PARENT_UNRESOLVABLE`.

Rationale: lineage frequently starts at material with no manifest, such as a photograph or a human-written file. That is normal. A `lineage_ref` is a claim that a manifest exists; a broken claim is a broken chain.

## 8. Signature and timestamp

### 8.1 Signing input

- **[REQ-0500]** The signing input is the UTF-8 encoding of the JCS serialization [RFC 8785] of the manifest object with the member `signature` removed. See [CANONICALIZATION.md](CANONICALIZATION.md) §2 and [ADR-0004](adr/0004-canonicalization-jcs.md).
- **[REQ-0501]** Annotation members ([REQ-0005]) are also removed before serialization.

Because the input is canonical, the manifest may be stored or embedded with any whitespace or member order and still verify.

### 8.2 Algorithms

- **[REQ-0502]** `EdDSA` means Ed25519 (pure, no pre-hash) per [RFC 8032], over the signing input; the signature is 64 bytes. `ES256` means ECDSA over P-256 with SHA-256; the signature is the 64-byte concatenation `r || s`, each big-endian and left-padded to 32 bytes, per [RFC 7518 §3.4]. DER-encoded ECDSA signatures MUST NOT be used. RSA is not supported in 0.1 ([ADR-0005](adr/0005-signature-suites.md)).
- **[REQ-0503]** A Verifier MUST reject a signature whose decoded length is not 64 bytes with `SIG_INVALID`.

### 8.3 Key identification

- **[REQ-0504]** If `kid` is a DID URL, the Verifier MUST resolve the DID document and use the verification method identified by the fragment. Verifiers MUST support `did:key` and SHOULD support `did:web`. Otherwise, `kid` MUST be resolvable via the `chain` leaf certificate or a Registry key directory. A Verifier MUST NOT trust key material only because it appears in the manifest: the key must chain to a trust anchor configured in the Verifier's trust policy (§9.3).

### 8.4 Timestamp

- **[REQ-0505]** `ts` MUST be the standard base64 encoding [RFC 4648 §4], with padding, of a DER-encoded RFC 3161 `TimeStampToken` (CMS `ContentInfo` with `SignedData`) [RFC 3161] [RFC 5816]. The `messageImprint` MUST use SHA-256 and its `hashedMessage` MUST be SHA-256 over the raw signature bytes (the decoded `sig`).
- **[REQ-0506]** A Producer MUST obtain the timestamp at signing time and MUST NOT publish a manifest without `ts`. If no TSA is reachable, the Producer MUST retry or defer publication. It MUST NOT emit an untimestamped manifest ([ADR-0002](adr/0002-three-state-verification.md)).
- **[REQ-0507]** A Producer SHOULD request `certReq = true`, so that the TSA certificate is included in the token.
- **[REQ-0508]** `artifact.created_at` MUST NOT be later than the token's `genTime` plus 300 seconds of allowed clock skew.

### 8.5 Key validity and revocation

- **[REQ-0509]** A key is revoked for a manifest if the revocation time published for the `kid` (DID document, Registry revocation list per [REQ-0008], or X.509 revocation for `chain`) is earlier than the token's `genTime`, or if the revocation reason is key compromise, regardless of time. A Verifier MUST then report `KEY_REVOKED`.

## 9. Verification algorithm

### 9.1 Inputs and output

Inputs: the artifact bytes; optionally a manifest supplied out of band; the Verifier's trust policy (trusted signing keys or DID methods, trusted TSA roots, Registries); the current time; whether chain mode is on.

Output: one state and a list of warnings.

| State | Meaning |
| --- | --- |
| `PROVENANCED` | A manifest was found for these exact bytes, is well-formed, is signed by a trusted, unrevoked key, and is timestamped. |
| `UNPROVENANCED` | No manifest was found for these bytes. This says nothing about how the artifact was made. |
| `PROVENANCE_BROKEN(reason)` | A manifest was found, but a check failed. |

- **[REQ-0600]** A Verifier MUST output exactly one state. `PROVENANCE_BROKEN` MUST carry exactly one reason: the reason of the first failing step in §9.2.
- **[REQ-0601]** Given the same inputs, trust policy and time, the algorithm MUST be deterministic.

### 9.2 Steps

1. **Locate.** Look for a manifest: the out-of-band manifest if supplied; the embedded manifest per the container (§5, §10); a sidecar `<file>.lineage.json`; configured Registries by the recomputed `artifact.id`. If none is found, the result is `UNPROVENANCED` ([REQ-0602]).
2. **Parse.** Parse as I-JSON. Failure, duplicate member names, or more than one embedded manifest → `SCHEMA_INVALID`.
3. **Version.** Check `spec`. An unsupported version → `SCHEMA_INVALID` (§16).
4. **Schema.** Validate against the JSON Schema of the declared version → `SCHEMA_INVALID`.
5. **Semantic rules.** Check [REQ-0072], [REQ-0075], [REQ-0077] → `SCHEMA_INVALID`.
6. **Artifact binding.** Recompute `artifact.id` from the hashable bytes (§5). Compare with `artifact.id`, `size_bytes` if present, and the header identifier if present ([REQ-0222]) → `HASH_MISMATCH`.
7. **Public prompt.** If `storage = public`, recompute `prompt.hash` ([REQ-0302]) → `HASH_MISMATCH`.
8. **Key resolution and trust.** Resolve `kid` (§8.3). Unresolvable, or not anchored in the trust policy → `KEY_UNTRUSTED`.
9. **Signature.** Verify `sig` over the signing input (§8.1) with the resolved key and `alg` → `SIG_INVALID`.
10. **Timestamp.** Decode `ts`; verify the TSA signature over the token; check that `messageImprint` equals SHA-256 of the signature bytes; check [REQ-0508]. Any failure → `TS_INVALID`. If the TSA certificate does not chain to a TSA root in the trust policy, emit `W_TSA_UNTRUSTED` and continue ([REQ-0604]).
11. **Revocation.** Apply §8.5 using `genTime` → `KEY_REVOKED`.
12. **Chain** (chain mode only). Resolve parents per §7, recursively up to the depth limit, applying steps 2–11 to each parent manifest and [REQ-0402] to each `previous_version` edge. Failures per [REQ-0404] and [REQ-0406] → `PARENT_UNRESOLVABLE`; a [REQ-0402] violation → `SCHEMA_INVALID`.
13. **Result.** `PROVENANCED` with the accumulated warnings.

- **[REQ-0602]** `UNPROVENANCED` MUST be returned only when no manifest claiming these bytes was found. A manifest that was found but cannot be parsed or validated MUST yield `PROVENANCE_BROKEN(SCHEMA_INVALID)`, not `UNPROVENANCED`.
- **[REQ-0603]** A Verifier MUST NOT fetch or decrypt prompt escrow as part of verification.
- **[REQ-0604]** An untrusted TSA root yields the warning `W_TSA_UNTRUSTED`, not a failure. A Verifier MAY be configured with a strict policy that turns `W_TSA_UNTRUSTED` into `TS_INVALID`; it MUST disclose that policy in its output.
- **[REQ-0605]** A Verifier MUST NOT change the state because of `flags` ([REQ-0093]), `jurisdiction`, `contains_pii` or unknown extensions.

### 9.3 Trust policy

- **[REQ-0606]** Trust decisions (which signing keys and TSAs are trusted) are local policy of the Verifier and MUST be configurable. A Verifier MUST report which trust policy produced the result. Test keys in `fixtures/keys/` MUST NOT be trusted outside of test mode.

### 9.4 Reason codes

| Reason | Step | Meaning |
| --- | --- | --- |
| `SCHEMA_INVALID` | 2–5, 12 | Unparsable, wrong version, schema or semantic rule violated. |
| `HASH_MISMATCH` | 6–7 | Artifact bytes, size, header or public prompt do not match the manifest. |
| `KEY_UNTRUSTED` | 8 | `kid` cannot be resolved or is not anchored in the trust policy. |
| `SIG_INVALID` | 9 | Signature does not verify. |
| `TS_INVALID` | 10 | Timestamp token invalid, imprint mismatch, or `created_at` after `genTime` + skew. |
| `KEY_REVOKED` | 11 | Signing key revoked before `genTime`, or compromised. |
| `PARENT_UNRESOLVABLE` | 12 | A declared parent manifest cannot be fetched, does not match, is broken, or forms a cycle. |

- **[REQ-0607]** Verifiers MUST use exactly these reason codes. Additional detail MAY be given in a free-text field.

### 9.5 Warnings

Warnings never change the state.

| Warning | Meaning |
| --- | --- |
| `W_TSA_UNTRUSTED` | Timestamp is cryptographically valid but its TSA is not in the trust policy. |
| `W_TS_DELAYED` | `genTime` is more than 24 hours after `artifact.created_at`. |
| `W_DEPTH_LIMIT` | Chain resolution stopped at the depth limit. |
| `W_PARENT_UNPROVENANCED` | A parent has no manifest (leaf). |
| `W_UNKNOWN_EXTENSION` | An extension namespace is unknown to the Verifier. |
| `W_ANNOTATION_PRESENT` | An annotation member (`_…`) is present. |
| `W_PERCEPTUAL_CANDIDATE` | No manifest for these bytes, but a Registry returned a perceptually similar artifact's manifest. |

- **[REQ-0608]** A Verifier MUST emit `W_TS_DELAYED` when `genTime − created_at > 24 h`.
- **[REQ-0609]** Warning codes not listed here MUST be prefixed `X_` and MUST be ignorable.
- **[REQ-0610]** A manifest found only through a perceptual lookup describes other bytes. The Verifier MUST report `UNPROVENANCED` with `W_PERCEPTUAL_CANDIDATE` and the candidate's `artifact.id`, and MUST NOT report `PROVENANCED` or `PROVENANCE_BROKEN` for it.
- **[REQ-0611]** A Verifier SHOULD present the chain report (each resolved node with its own state and warnings) alongside the top-level state.

## 10. Embedding (informative)

This section summarizes where a manifest lives in each container and what is hashed. Rules for PNG, JPEG and sidecar are normative in §5. All other rows are informative in 0.1 and will be specified in `embed/` documents.

| Format | Location | Hashable bytes |
| --- | --- | --- |
| PNG | `iTXt` chunk, keyword `ailineage`, before `IEND` | file minus that chunk (§5.2) |
| JPEG | dedicated APP1 XMP packet, namespace `http://ailineage.org/ns/0.1/`, property `ailineage:manifest` | file minus that APP1 segment (§5.3) |
| WebP | `XMP` chunk (FourCC `XMP` plus a trailing space) in the RIFF container, same namespace | file minus that chunk, with RIFF size field recomputed — **open**: the WebP container allows only one XMP chunk (see OPEN_QUESTIONS.md) |
| MP4 / MOV | `udta` box containing a box of type `ailn` with the UTF-8 manifest | file minus the `ailn` box, with ancestor box sizes recomputed — **open**: requires a canonical box-rewrite rule |
| PDF | XMP metadata stream with the AILineage namespace, appended as an incremental update | bytes of the PDF before the incremental update |
| Text / code | sidecar `<file>.lineage.json`; optional header comment `ailineage: urn:sha256:…` | file bytes, minus the header line if present (§5.4) |
| Git | `refs/notes/ailineage` note on the commit; JSON Lines, one manifest per changed file | each file's blob content bytes (SHA-256, not the Git object id) |

Examples: [`examples/png-itxt/`](examples/png-itxt/), [`examples/sidecar/`](examples/sidecar/), [`examples/git-notes/`](examples/git-notes/).

## 11. Interop profiles (informative)

AILineage is designed to travel inside existing provenance formats ([ADR-0003](adr/0003-embed-into-c2pa-and-in-toto.md)). Implementations are planned for phase 5; this section only fixes names and mappings.

### 11.1 C2PA

The full manifest is carried as a C2PA assertion with label `org.ailineage.lineage`, as a JSON assertion payload (CBOR serialization: see OPEN_QUESTIONS.md and [ADR-0004](adr/0004-canonicalization-jcs.md)). The C2PA claim signature does not replace `signature`; the AILineage manifest keeps its own signature so it can be extracted and verified independently.

| AILineage | C2PA 2.x |
| --- | --- |
| `generation.kind = created` | `c2pa.actions` action `c2pa.created`, `digitalSourceType` = IPTC `trainedAlgorithmicMedia` |
| `generation.kind = edited` | action `c2pa.edited`, `digitalSourceType` = IPTC `compositeWithTrainedAlgorithmicMedia` |
| `generation.kind = derived` | action `c2pa.created` with ingredients, `digitalSourceType` = IPTC `trainedAlgorithmicMedia` |
| `generation.kind = assisted` | action `c2pa.edited`, `digitalSourceType` = IPTC `algorithmicallyEnhanced` (approximate) |
| `generation.model.id` | action `softwareAgent` name |
| `generation.runtime.tool` | `claim_generator_info` |
| `parents[] relation = previous_version` | ingredient with relationship `parentOf` |
| `parents[] relation = input / template` | ingredient with relationship `inputTo` |
| `parents[] relation = reference` | ingredient with relationship `componentOf` (approximate) |
| `prompt.*` | no equivalent; carried only inside `org.ailineage.lineage` |
| `actor.*` | no direct equivalent (CAWG identity assertion is the closest) |
| `signature.ts` | C2PA time-stamp on the claim signature (separate; both kept) |

### 11.2 in-toto

| in-toto Statement v1 | AILineage |
| --- | --- |
| `subject[0].digest.sha256` | hex part of `artifact.id` |
| `subject[0].name` | file name, if known |
| `predicateType` | `https://ailineage.org/predicate/v0.1` |
| `predicate` | the manifest without `signature` |
| DSSE envelope signature | replaces `signature.sig`; `signature.alg`/`kid` map to DSSE `keyid` |
| timestamp | RFC 3161 token over the DSSE signature, or a Sigstore transparency-log entry (future keyless profile, [ADR-0005](adr/0005-signature-suites.md)) |

### 11.3 CycloneDX

| CycloneDX 1.6+ | AILineage |
| --- | --- |
| component `type: machine-learning-model`, `name`/`group` | `generation.model.id` |
| component `hashes` | `generation.model.version_hash` (when `sha256:`) |
| `externalReferences` type `model-card` | `generation.model.card_ref` |
| `formulation` | `generation.runtime` |
| `pedigree.ancestors` / `pedigree.variants` | `parents[]` |

## 12. Registry API (informative)

The Registry is optional ([ADR-0006](adr/0006-registry-and-escrow-model.md)). The normative OpenAPI 3.1 definition lives in the sister repository `ailineage/registry` as `registry/openapi.yaml`; it is not part of this repository. The endpoints below are indicative.

| Method and path | Purpose |
| --- | --- |
| `POST /v0/manifests` | Submit a manifest; Registry verifies it ([REQ-0007]) and stores it byte-exact ([REQ-0006]). |
| `GET /v0/manifests/{artifact_id}` | Fetch manifests for `urn:sha256:…`. Target of `lineage_ref` URNs. |
| `GET /v0/chain/{artifact_id}?depth=16` | Resolved lineage DAG with per-node state. |
| `POST /v0/lookup/perceptual` | Find candidate manifests by `perceptual` value (strip-check). |
| `POST /v0/escrow` | Store prompt ciphertext bound to `prompt.hash` and `artifact.id`; returns the escrow id. |
| `POST /v0/disclosures` | Request disclosure of an escrowed prompt, with legal basis. |
| `GET /v0/disclosures/{id}` | Status of a disclosure request. |
| `GET /v0/audit?prompt_hash=…` | Audit log entries for an escrow record ([REQ-0307]). |
| `GET /v0/revocations` | Signed key revocation list ([REQ-0008]). |

## 13. Privacy considerations

- **[REQ-0800]** For `role = end-user`, `actor.principal` SHOULD be a pseudonymous DID (for example a per-deployer `did:key`) with `pseudonymous = true`. The mapping from pseudonym to person, if any, stays with the deployer.
- **[REQ-0801]** Prompt plaintext MUST NOT appear in a manifest unless `storage = public` ([REQ-0304]).
- **[REQ-0802]** A Registry MUST hold escrowed prompts only as ciphertext ([REQ-0303]) and MUST NOT require plaintext for any operation.
- **[REQ-0803]** Every disclosure MUST be audited ([REQ-0307]). A Registry SHOULD make audit entries available to the principal.
- **[REQ-0804]** An unsalted hash of a short or predictable prompt can be found by guessing. A Producer SHOULD treat `prompt.hash` of low-entropy prompts as potentially revealing and MAY choose `storage = none` with `disclosure_policy = none` only when the prompt is not sensitive. A salted commitment is under consideration (OPEN_QUESTIONS.md).
- **[REQ-0805]** `seed`, `params_hash`, `context_refs` and `turn_index` can link manifests to each other and to a user. A Producer SHOULD omit them when linkage would harm the principal and they are not needed for accountability.
- **[REQ-0806]** A Registry operator MUST document its retention policy for manifests and escrow ciphertext, including how it handles data-subject erasure requests against the evidentiary purpose of escrow.

Artifact identifiers are content hashes. Publishing a manifest reveals that a party knew the artifact's exact bytes at signing time.

## 14. Security considerations

The full analysis is in [THREAT_MODEL.md](THREAT_MODEL.md). In summary:

- Metadata is routinely stripped by platforms. Embedded manifests are a convenience; Registries and `perceptual` lookups are the recovery path, and a stripped artifact is `UNPROVENANCED`, not broken.
- Backdating is prevented by the mandatory RFC 3161 timestamp over the signature, which binds the signature to a time attested by a third party.
- `generation.model` and `prompt` are Producer claims. Signatures make the Producer accountable for them; they do not make them true.
- Manifest transplant onto other bytes fails `HASH_MISMATCH` because `artifact.id` is recomputed by the Verifier.
- Key compromise is handled by revocation (§8.5); the timestamp distinguishes signatures made before revocation.
- Chain resolution is bounded (default depth 16) and cycle-checked to prevent resource exhaustion.
- Flags are not enforcement inputs, so they cannot be abused to suppress content via Verifiers.

## 15. IANA and registries considerations

This version reserves the names below. Registration is future work and tracked in [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) and the roadmap.

| Name | Value | Status |
| --- | --- | --- |
| Digest algorithm registry | `sha256` (64 hex digits) | defined by this specification (§5.5); extended only by ADR |
| Media type | `application/vnd.ailineage+json` | TODO: IANA vendor-tree registration; future IETF draft |
| XMP namespace | `http://ailineage.org/ns/0.1/`, prefix `ailineage` | reserved; IPTC/XMP registration planned |
| PNG iTXt keyword | `ailineage` | reserved; PNG keyword registry submission planned |
| MP4 box type | `ailn` | reserved; MP4RA registration planned |
| C2PA assertion label | `org.ailineage.lineage` | reserved (entity-specific label) |
| in-toto predicate type | `https://ailineage.org/predicate/v0.1` | reserved |
| URN namespaces | `urn:ailineage:registry:…`, `urn:ailineage:escrow:…` | informal; formal URN namespace (RFC 8141) not requested |
| Git notes ref | `refs/notes/ailineage` | convention |
| Sidecar suffix | `.lineage.json` | convention |

## 16. Versioning

- **[REQ-0900]** `spec` has the form `ailineage/<major>.<minor>`. A minor version only adds optional members, enum values or informative text. A major version may make breaking changes and MUST be accompanied by an ADR and migration notes.
- **[REQ-0901]** A Verifier MUST validate a manifest against the schema of the version it declares. A Verifier that does not implement the declared version MUST report `SCHEMA_INVALID` and SHOULD state that the version is unsupported.
- **[REQ-0902]** While the major version is `0`, a minor version MAY also make breaking changes, each recorded in an ADR and in [CHANGELOG.md](CHANGELOG.md). From 1.0 on, the deprecation policy of [GOVERNANCE.md](GOVERNANCE.md) applies.

## 17. References

### 17.1 Normative

- [RFC 2119] Bradner, S., "Key words for use in RFCs to Indicate Requirement Levels", BCP 14, RFC 2119. <https://www.rfc-editor.org/rfc/rfc2119>
- [RFC 8174] Leiba, B., "Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words", BCP 14, RFC 8174. <https://www.rfc-editor.org/rfc/rfc8174>
- [RFC 8785] Rundgren, A., Jordan, B., Erdtman, S., "JSON Canonicalization Scheme (JCS)", RFC 8785. <https://www.rfc-editor.org/rfc/rfc8785>
- [RFC 3161] Adams, C., et al., "Internet X.509 Public Key Infrastructure Time-Stamp Protocol (TSP)", RFC 3161. <https://www.rfc-editor.org/rfc/rfc3161>
- [RFC 5816] Santesson, S., Pope, N., "ESSCertIDv2 Update for RFC 3161", RFC 5816. <https://www.rfc-editor.org/rfc/rfc5816>
- [RFC 8259] Bray, T., "The JavaScript Object Notation (JSON) Data Interchange Format", RFC 8259. <https://www.rfc-editor.org/rfc/rfc8259>
- [RFC 7493] Bray, T., "The I-JSON Message Format", RFC 7493. <https://www.rfc-editor.org/rfc/rfc7493>
- [RFC 3339] Klyne, G., Newman, C., "Date and Time on the Internet: Timestamps", RFC 3339. <https://www.rfc-editor.org/rfc/rfc3339>
- [RFC 6838] Freed, N., Klensin, J., Hansen, T., "Media Type Specifications and Registration Procedures", RFC 6838. <https://www.rfc-editor.org/rfc/rfc6838>
- [RFC 4648] Josefsson, S., "The Base16, Base32, and Base64 Data Encodings", RFC 4648. <https://www.rfc-editor.org/rfc/rfc4648>
- [RFC 8032] Josefsson, S., Liusvaara, I., "Edwards-Curve Digital Signature Algorithm (EdDSA)", RFC 8032. <https://www.rfc-editor.org/rfc/rfc8032>
- [RFC 7518] Jones, M., "JSON Web Algorithms (JWA)", RFC 7518. <https://www.rfc-editor.org/rfc/rfc7518>
- [JSON-SCHEMA] "JSON Schema: A Media Type for Describing JSON Documents", draft 2020-12. <https://json-schema.org/draft/2020-12>
- [UAX15] Unicode Standard Annex #15, "Unicode Normalization Forms". <https://www.unicode.org/reports/tr15/>
- [DID-CORE] W3C, "Decentralized Identifiers (DIDs) v1.0". <https://www.w3.org/TR/did-core/>
- [DID-KEY] W3C CCG, "The did:key Method". <https://w3c-ccg.github.io/did-method-key/>
- [PNG] W3C, "Portable Network Graphics (PNG) Specification (Third Edition)". <https://www.w3.org/TR/png-3/>
- [XMP] ISO 16684-1, "Graphic technology — Extensible metadata platform (XMP) — Part 1: Data model, serialization and core properties".
- [C2PA] C2PA, "C2PA Technical Specification", version 2.x. <https://spec.c2pa.org/>
- [IN-TOTO] in-toto, "in-toto Attestation Framework Spec v1". <https://github.com/in-toto/attestation/tree/main/spec/v1>

### 17.2 Informative

- [AI-ACT] Regulation (EU) 2024/1689 (Artificial Intelligence Act), Article 50. <https://eur-lex.europa.eu/eli/reg/2024/1689/oj>
- [EU-COP] European Commission, "Code of Practice on marking and labelling of AI-generated content", final version, 10 June 2026. <https://digital-strategy.ec.europa.eu/en/news/commission-publishes-code-practice-marking-and-labelling-ai-generated-content>
- [NIST-AI-100-4] NIST, "Reducing Risks Posed by Synthetic Content: An Overview of Technical Approaches to Digital Content Transparency", NIST AI 100-4. <https://doi.org/10.6028/NIST.AI.100-4>
- [CN-LABEL] Cyberspace Administration of China et al., "Measures for Labeling Artificial Intelligence-Generated Synthetic Content", effective 1 September 2025, with national standard GB 45438-2025.
- [USCO] U.S. Copyright Office, "Copyright and Artificial Intelligence, Part 2: Copyrightability" (January 2025). <https://www.copyright.gov/ai/>
- [IPTC-DST] IPTC, "Digital Source Type" controlled vocabulary. <https://cv.iptc.org/newscodes/digitalsourcetype/>
- [DZONE] Mopathi, U., "Git Blame Isn't Enough: Building Verifiable Provenance for AI-Generated Code", DZone, 30 September 2026. <https://dzone.com/articles/verifiable-provenance-ai-code>
- [CISCO-MPK] Cisco AI Defense, "Model Provenance Kit". <https://github.com/cisco-ai-defense/model-provenance-kit>
- [RELATED] [RELATED_WORK.md](RELATED_WORK.md) for SLSA, Sigstore, CycloneDX, OpenLineage, W3C PROV and OpenTelemetry.
