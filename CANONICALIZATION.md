# AILineage Canonicalization 0.1

This document is normative. It defines the exact byte sequences that AILineage hashes and signs. Requirement IDs refer to [SPEC.md](SPEC.md).

All test vectors in §7 are computed by [`fixtures/regen.py`](fixtures/regen.py) and checked in CI by `make test-vectors`. They are never edited by hand. The same vectors are available as JSON in [`fixtures/vectors/canonicalization.json`](fixtures/vectors/canonicalization.json).

## 1. Overview

| What | Method | Used by |
| --- | --- | --- |
| Manifest signing input | JCS (RFC 8785) of the manifest minus `signature` and annotation members | `signature.sig` ([REQ-0500]) |
| Text prompt | `utf8-nfc-trim-v1` | `prompt.hash`, `prompt.system_prompt_hash` |
| Prompt with attachments | `multimodal-v1` | `prompt.hash` |
| Generation parameters | JCS of params minus `volatile` keys | `runtime.params_hash` |
| Workflow definition | JCS if JSON, raw bytes otherwise | `runtime.workflow_hash` |
| Artifact | per-container hashable bytes (SPEC.md §5) | `artifact.id`, `parents[].id`, `context_refs[]` |

The hash function is SHA-256 everywhere in 0.1. Digests are written as `sha256:<64 lowercase hex>` or, for artifacts, `urn:sha256:<64 lowercase hex>`.

## 2. JSON: RFC 8785 (JCS)

The manifest signing input is `UTF-8(JCS(M'))`, where `M'` is the manifest object with the top-level `signature` member and every top-level annotation member (`_…`) removed. JCS fixes:

- member order: members sorted by their names as arrays of UTF-16 code units;
- whitespace: none outside strings;
- strings: minimal escaping (`\"`, `\\`, `\b`, `\f`, `\n`, `\r`, `\t`, and `\u00xx` with lowercase hex for other control characters); all other characters literal, including non-ASCII;
- numbers: the ECMAScript `Number.prototype.toString` form (`1e+21`, `1e-7`, `-0` becomes `0`).

A manifest contains only integers ([REQ-0004]), so number formatting matters only for `params_hash` inputs, which may contain floats.

Why JCS: the manifest may be stored with any formatting (pretty-printed in a sidecar, compact in a PNG chunk, inside a C2PA assertion) and the signature must still verify. JCS is the IETF-published canonical form for JSON and has implementations in all major languages. [ADR-0004](adr/0004-canonicalization-jcs.md) records the alternatives.

## 3. Text prompt: `utf8-nfc-trim-v1`

Given the prompt as a sequence of Unicode code points:

1. **NFC.** Apply Unicode Normalization Form C [UAX15].
   *Why:* the same visible text arrives in different forms. macOS input and many web forms produce decomposed `Příliš` (NFD), other systems precomposed. Without NFC, two identical-looking prompts hash differently.
2. **Newlines.** Replace every `CR LF` (U+000D U+000A) with `LF`, then every remaining `CR` with `LF`.
   *Why:* Windows clients, HTTP form posts and terminals disagree on line endings. The meaning of the prompt does not depend on them.
3. **Trailing whitespace per line.** Split on `LF`. From the end of each line remove every code point with the Unicode property `White_Space=yes` (U+0009, U+000B, U+000C, U+000D, U+0020, U+0085, U+00A0, U+1680, U+2000–U+200A, U+2028, U+2029, U+202F, U+205F, U+3000). Join with `LF`.
   *Why:* trailing spaces are invisible, editors strip or keep them unpredictably, and they carry no instruction.
4. **Trim.** Remove all `White_Space` code points and `LF` from the beginning and the end of the whole text.
   *Why:* chat UIs and APIs add or drop leading and trailing blank lines. Leading indentation of the *first* line is also removed, which is acceptable: it carries no meaning in natural-language prompts. Interior indentation (for example code inside a prompt) is preserved.
5. **Encode.** Encode as UTF-8 without BOM.
6. **Hash.** `prompt.hash = "sha256:" || hex(SHA-256(bytes))`.

The canonical form is not case-folded and does not collapse interior whitespace. Changing either would make distinct instructions collide (`"use  2 spaces"` versus `"use 2 spaces"` in a code prompt).

## 4. Prompt with attachments: `multimodal-v1`

A prompt consisting of text plus non-text inputs (images, audio, documents attached to the instruction) is represented as the JSON object:

```json
{ "text": "<text>", "attachments": ["urn:sha256:<hex>", "..."] }
```

1. `text` is the text part after steps 1–4 of §3. If there is no text, `text` is the empty string.
2. `attachments` lists the `urn:sha256:` identifier of each attachment, computed over its bytes as submitted to the model, in the order the attachments were submitted. Order is significant.
3. The object is serialized with JCS (§2) and encoded as UTF-8.
4. `prompt.hash = "sha256:" || hex(SHA-256(bytes))`.

Attachments that are themselves AILineage artifacts SHOULD also appear in `parents` with relation `input` or `reference`.

## 5. Parameters: `params_hash`

1. Take the generation parameter object as sent to the model or tool (`steps`, `cfg`, `temperature`, …).
2. Remove the top-level members whose names are listed in `generation.runtime.volatile`. Only top-level members can be listed.
3. Serialize with JCS (§2), encode as UTF-8.
4. `params_hash = "sha256:" || hex(SHA-256(bytes))`.

The Producer MUST NOT include the prompt text in the parameter object it hashes; the prompt is committed separately ([REQ-0304]).

## 6. Other digests

- `runtime.workflow_hash` — SHA-256 over `JCS(workflow)` if the workflow is JSON (ComfyUI API format, LangGraph JSON), over the raw bytes otherwise. Prompt-bearing values SHOULD be replaced with the literal `<prompt>` first ([REQ-0037]).
- `model.version_hash` — SHA-256 over the weights file, or over `JCS` of the array of per-file `"sha256:<hex>"` digests ordered by file name ([REQ-0032]).
- `ts` imprint — SHA-256 over the raw signature bytes (decoded `sig`) ([REQ-0505]).

## 7. Test vectors

The input strings below are written as Python string literals so that every code point (including decomposed diacritics, zero-width joiners and control characters) is unambiguous. The UTF-8 hex of each input is also given.

<!-- BEGIN GENERATED: test-vectors (fixtures/regen.py) -->

### Prompt vectors (`utf8-nfc-trim-v1`)

#### `ascii`

Input (Python string literal, exact code points):

```python
'Draw a red circle on a white background.'
```

Input UTF-8 bytes (hex):

```text
4472617720612072656420636972636c65206f6e2061207768697465206261636b67726f756e642e
```

Canonical form (Python string literal):

```python
'Draw a red circle on a white background.'
```

SHA-256:

```text
sha256:82611d94764edb70f41067b56384c1e5f1180d9d3609e78943112ea0ed876614
```

#### `czech-diacritics-nfd`

Input (Python string literal, exact code points):

```python
'Příliš žluťoučký kůň úpěl ďábelské ódy'
```

Input UTF-8 bytes (hex):

```text
5072cc8c69cc816c6973cc8c207acc8c6c7574cc8c6f7563cc8c6b79cc81206b75cc8a6ecc8c2075cc817065cc8c6c2064cc8c61cc8162656c736b65cc81206fcc816479
```

Canonical form (Python string literal):

```python
'Příliš žluťoučký kůň úpěl ďábelské ódy'
```

SHA-256:

```text
sha256:6f33ad2f13da6ec45a14dd2854c3bf486310af3832123272feb4d78461b8c96c
```

#### `emoji`

Input (Python string literal, exact code points):

```python
'Make the icon friendlier 🦊✨ and add a 👨\u200d💻'
```

Input UTF-8 bytes (hex):

```text
4d616b65207468652069636f6e20667269656e646c69657220f09fa68ae29ca820616e6420616464206120f09f91a8e2808df09f92bb
```

Canonical form (Python string literal):

```python
'Make the icon friendlier 🦊✨ and add a 👨\u200d💻'
```

SHA-256:

```text
sha256:411b6d0a15353fd397a49f41179dbf7cec011c46fdef4fd56576d63bec0fc982
```

#### `crlf`

Input (Python string literal, exact code points):

```python
'Line one\r\nLine two\rLine three\r\n'
```

Input UTF-8 bytes (hex):

```text
4c696e65206f6e650d0a4c696e652074776f0d4c696e652074687265650d0a
```

Canonical form (Python string literal):

```python
'Line one\nLine two\nLine three'
```

SHA-256:

```text
sha256:46c949c0b79bc3c1eef1d2970222427b7a0e8d70233d4cc2429535f0f41a0e9a
```

#### `trailing-spaces`

Input (Python string literal, exact code points):

```python
'  Indented first line   \nsecond line\t \n\n\n  '
```

Input UTF-8 bytes (hex):

```text
2020496e64656e746564206669727374206c696e652020200a7365636f6e64206c696e6509200a0a0a2020
```

Canonical form (Python string literal):

```python
'Indented first line\nsecond line'
```

SHA-256:

```text
sha256:117a85e46ec77376d0335c11e64842995413395fc358a9d07a4f327577392daa
```

### JCS vector

Input (Python literal; `-0.0`, `1e21` and `1e-7` exercise number serialization):

```python
{'spec': 'ailineage/0.1', 'z': [3, 1.5, 1e+21, 1e-07, -0.0, 100], 'a': {'€': 'euro', '\r': 'cr', '😀': 'emoji', 'ﬁ': 'fi-ligature (sorts after U+1F600 in UTF-16 order)', '1': 'one'}, 'text': 'Příliš\n"quoted"\t\x01', 'flag': True, 'none': None}
```

Canonical UTF-8 output:

```text
{"a":{"\r":"cr","1":"one","€":"euro","😀":"emoji","ﬁ":"fi-ligature (sorts after U+1F600 in UTF-16 order)"},"flag":true,"none":null,"spec":"ailineage/0.1","text":"Příliš\n\"quoted\"\t\u0001","z":[3,1.5,1e+21,1e-7,0,100]}
```

SHA-256:

```text
sha256:a4c7335e3aaec1ef4da825efc1a92a67fd880adca270b9a9ffa91a7141d16a1e
```

### Multimodal vector (`multimodal-v1`)

Input:

```python
{'text': '  Describe this image\r\nin one sentence.  ', 'attachments': ['urn:sha256:1f9cd740c721f1adfd070b4cc2ea3fc84e8406eacbad8e362dca26fc0dd273fa']}
```

Canonical form:

```text
{"attachments":["urn:sha256:1f9cd740c721f1adfd070b4cc2ea3fc84e8406eacbad8e362dca26fc0dd273fa"],"text":"Describe this image\nin one sentence."}
```

SHA-256:

```text
sha256:66d8f81622273184235c23fc9913fd8d553fe80480aaa5560191f4129fc6a8e5
```

### Params vector (`params_hash`)

Input:

```python
{'params': {'steps': 4, 'cfg': 1.0, 'sampler_name': 'euler', 'client_id': 'c0ffee-run-7', 'queued_at': '2026-10-19T06:59:58Z'}, 'volatile': ['client_id', 'queued_at']}
```

Canonical form:

```text
{"cfg":1,"sampler_name":"euler","steps":4}
```

SHA-256:

```text
sha256:3c18fc58cd350eccc0d092bc00e9d4c9d58ae7918cd7c1e78ad8975e18464698
```

<!-- END GENERATED: test-vectors -->

## 8. References

- [RFC 8785] JSON Canonicalization Scheme (JCS). <https://www.rfc-editor.org/rfc/rfc8785>
- [UAX15] Unicode Normalization Forms. <https://www.unicode.org/reports/tr15/>
- Unicode `PropList.txt`, property `White_Space`. <https://www.unicode.org/Public/UCD/latest/ucd/PropList.txt>
