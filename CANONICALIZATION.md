# AILineage Canonicalization 0.1

This document is normative. It defines the exact byte sequences that AILineage hashes and signs. Requirement IDs refer to [SPEC.md](SPEC.md).

All test vectors in §8 are computed by [`fixtures/regen.py`](fixtures/regen.py) and checked in CI by `make test-vectors`. They are never edited by hand. The same vectors are available as JSON in [`fixtures/vectors/canonicalization.json`](fixtures/vectors/canonicalization.json).

## 1. Overview

| What | Method | Used by |
| --- | --- | --- |
| Manifest signing input | JCS (RFC 8785) of the manifest minus `signature` and annotation members | `signature.sig` ([REQ-0500]) |
| Text prompt, hidden (`storage` = `escrow` or `none`) | `utf8-nfc-trim-salted-v1` | `prompt.hash`, `prompt.system_prompt_hash` |
| Prompt with attachments, hidden | `multimodal-salted-v1` | `prompt.hash` |
| Text prompt, public (`storage` = `public`) | `utf8-nfc-trim-v1` | `prompt.hash`, `prompt.system_prompt_hash` |
| Prompt with attachments, public | `multimodal-v1` | `prompt.hash` |
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

## 5. Salted commitment: `utf8-nfc-trim-salted-v1`, `multimodal-salted-v1`

The salted methods hide the prompt from guessing ([REQ-0308]–[REQ-0311], [ADR-0008](adr/0008-mandatory-salted-prompt-commitment.md)). They are required whenever `storage` is `escrow` or `none` ([REQ-0052]).

1. Compute the canonical bytes `C` exactly as for the unsalted method: §3 steps 1–5 for `utf8-nfc-trim-salted-v1`, §4 steps 1–3 for `multimodal-salted-v1`.
2. Take a fresh 32-byte salt `S` from a cryptographically secure random number generator.
3. `prompt.hash = "sha256:" || hex(SHA-256(S || C))`, where `||` is byte concatenation and `S` comes first.
4. Keep the opening (plaintext, `S`) where the plaintext is kept: in the escrow ciphertext, or with the principal. Never in the manifest. As text, `S` is base64url without padding.

To check an opening, recompute step 1 from the disclosed plaintext and step 3 with the disclosed salt, and compare with `prompt.hash`.

*Why a 32-byte prefix and not HMAC:* the salt has a fixed length, so `S || C` is unambiguous, and the construction is a standard hash commitment: hiding because `S` is unknown and random, binding because SHA-256 is collision-resistant. HMAC would add nothing here. A per-principal HMAC key was rejected, because disclosing one prompt would require releasing the key and expose every other prompt of that principal to guessing.

*Why public prompts stay unsalted:* the text is in the manifest, so a salt would hide nothing, and every Verifier must be able to re-hash it ([REQ-0302]).

## 6. Parameters: `params_hash`

1. Take the generation parameter object as sent to the model or tool (`steps`, `cfg`, `temperature`, …).
2. Remove the top-level members whose names are listed in `generation.runtime.volatile`. Only top-level members can be listed.
3. Serialize with JCS (§2), encode as UTF-8.
4. `params_hash = "sha256:" || hex(SHA-256(bytes))`.

The Producer MUST NOT include the prompt text in the parameter object it hashes; the prompt is committed separately ([REQ-0304]).

## 7. Other digests

- `runtime.workflow_hash` — SHA-256 over `JCS(workflow)` if the workflow is JSON (ComfyUI API format, LangGraph JSON), over the raw bytes otherwise. Prompt-bearing values SHOULD be replaced with the literal `<prompt>` first ([REQ-0037]).
- `model.version_hash` — SHA-256 over the weights file, or over `JCS` of the array of per-file `"sha256:<hex>"` digests ordered by file name ([REQ-0032]).
- `ts` imprint — SHA-256 over the raw signature bytes (decoded `sig`) ([REQ-0505]).

## 8. Test vectors

The salted vectors use the fixed salt `00 01 02 … 1f`. Real salts MUST be random ([REQ-0308]). The input strings below are written as Python string literals so that every code point (including decomposed diacritics, zero-width joiners and control characters) is unambiguous. The UTF-8 hex of each input is also given.

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

### Salted prompt vectors (`utf8-nfc-trim-salted-v1`)

Same inputs as the vectors of the same name above. Salt (32 bytes, test only):

```text
000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f
```

#### `ascii` (salted)

Hashed bytes `salt || canonical` (hex):

```text
000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f4472617720612072656420636972636c65206f6e2061207768697465206261636b67726f756e642e
```

SHA-256:

```text
sha256:dba55bb3d4fedf6a9406f2ea4f638deaa5f7ef7d581a4da8fa83a25edf5d4ccb
```

#### `czech-diacritics-nfd` (salted)

Hashed bytes `salt || canonical` (hex):

```text
000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f50c599c3ad6c69c5a120c5be6c75c5a56f75c48d6bc3bd206bc5afc58820c3ba70c49b6c20c48fc3a162656c736bc3a920c3b36479
```

SHA-256:

```text
sha256:b53ad33fe9df6feec7959acc4251b3b5df9e2241b3a0d9c7d184521a8834f25a
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

### Multimodal salted vector (`multimodal-salted-v1`)

Same input and canonical form as above, same test salt. SHA-256:

```text
sha256:5445606d123e927148bd36afe29016d160c327c3566419d1ceffdf18d77fe2fb
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

## 9. References

- [RFC 8785] JSON Canonicalization Scheme (JCS). <https://www.rfc-editor.org/rfc/rfc8785>
- [UAX15] Unicode Normalization Forms. <https://www.unicode.org/reports/tr15/>
- Unicode `PropList.txt`, property `White_Space`. <https://www.unicode.org/Public/UCD/latest/ucd/PropList.txt>
