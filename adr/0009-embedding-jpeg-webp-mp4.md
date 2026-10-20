# ADR-0009: Embedding in JPEG, WebP and MP4

- Status: Accepted
- Date: 2026-10-20
- Deciders: Ol1n
- Affects: SPEC.md §5.1, §5.3, §5.4, §10, §15, §17; REQ-0215–0219 (replaced), REQ-0225–0228 (new). Sidecar and digest sections renumbered to §5.5 and §5.6. Resolves OPEN_QUESTIONS.md question 5.

## Context

`artifact.id` is SHA-256 over the artifact's bytes with the embedded manifest removed, and that removal must be a pure byte operation ([REQ-0202]). The 0.1 draft had a clean rule only for PNG (an `iTXt` chunk). The other image and video carriers had problems:

- **JPEG.** The draft used a second, dedicated APP1 XMP packet. XMP expects one packet per file: most readers only read the first, and metadata tools merge, rewrite or drop a second one. An APP segment also has a 64 KiB limit and the draft defined no way to split a larger manifest.
- **WebP.** The container allows exactly one XMP chunk (FourCC `XMP` followed by a space), so the manifest would collide with ordinary metadata.
- **MP4.** A box inside `moov/udta` changes the size of its ancestors. If `moov` precedes `mdat`, inserting it also shifts every media-data offset in `stco`/`co64`. Removal would need a canonical box-rewrite rule, which is no longer a simple byte operation.

The reference implementation (phase 2) ships JPEG and WebP support in its first version, so their rules must be normative now.

## Decision

1. **JPEG:** the manifest is a JUMBF superbox (ISO/IEC 19566-5) with JSON content type and label `ailineage`, carried in APP11 marker segments with the `JP` common identifier and its own box instance number `En`; large manifests are split across segments by packet sequence number `Z`. Hashable bytes are the file minus those segments ([REQ-0215]–[REQ-0219]). This is the carrier C2PA uses for JPEG, so tooling that parses C2PA can parse it, and C2PA readers skip boxes with an unknown label.
2. **WebP:** the manifest is a top-level RIFF chunk with FourCC `AILN`, in the extended (`VP8X`) format. Simple-format files are converted by inserting `VP8X` before the identifier is computed. Hashable bytes are the file minus the chunk, with the RIFF size field reduced ([REQ-0225]–[REQ-0228]).
3. **MP4 / ISO BMFF:** the manifest is a top-level `uuid` box with user type `2243035f-b214-4a85-b066-27aee0493d17`, placed as the last box of the file. Removal is a truncation and no other box or offset changes. This mirrors C2PA's top-level `uuid` box for BMFF. It stays informative (§10) until milestone M2, when it is specified in the `embed/` document with fixtures. Until then video uses a sidecar or the Registry.
4. AILineage data is never written into XMP, Exif or another application's JUMBF box. The XMP namespace `http://ailineage.org/ns/0.1/` remains reserved for the PDF row of §10 only.
5. Each container carries at most one AILineage manifest. More than one is `SCHEMA_INVALID`, as for PNG.

## Consequences

- Removal is a parse of the container's top-level structure plus a byte copy in all three formats. No metadata is re-serialized and no media data is touched.
- Existing XMP, Exif and C2PA data in the same file is left alone, and AILineage and C2PA can coexist in one JPEG.
- Generic XMP viewers do not show the AILineage manifest. Tools need the AILineage SDK or a JUMBF-aware reader such as the C2PA SDKs.
- Converting a simple-format WebP to the extended format changes its bytes. The identifier therefore covers the extended-format file, and the original simple-format hash is not the artifact's identifier. Fixture 14 demonstrates this.
- MP4 editors that rewrite the file may drop a trailing unknown `uuid` box, or move it. A moved box is still removable, but [REQ-0201] binding then needs the box at the end. M2 will define whether a Verifier accepts a non-final box.
- New conformance material: fixtures 13 (JPEG) and 14 (WebP), examples `examples/jpeg-jumbf/` and `examples/webp-chunk/`. `regen.py check` verifies strip(embed(x)) = x for both and a multi-segment JPEG round trip.

## Alternatives

- **Second APP1 XMP packet (the 0.1 draft).** Rejected because of reader and tool behaviour and the missing multi-segment rule.
- **Properties inside the main XMP packet (JPEG, WebP).** Rejected because removing them requires re-serializing XMP, and the result depends on the serializer.
- **Custom APPn segment (e.g. APP12–APP15 with an `ailineage` identifier).** Simple, but APPn numbers are shared without a registry and collide with vendor data. It also gives no reuse of C2PA tooling.
- **Only inside C2PA (`org.ailineage.lineage` assertion).** Still the preferred path when a C2PA manifest is present ([ADR-0003](0003-embed-into-c2pa-and-in-toto.md)). It requires a C2PA signer and claim generator, though, and the standalone carrier must work without them.
- **MP4 `moov/udta/ailn` box.** Rejected because it requires ancestor size rewriting and, depending on layout, chunk-offset rewriting.
