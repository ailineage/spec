# JSON Schema

| File | Purpose |
| --- | --- |
| [`lineage-0.1.json`](lineage-0.1.json) | Main schema for `ailineage/0.1` manifests (JSON Schema draft 2020-12). |
| [`defs/hash.json`](defs/hash.json) | `sha256:<64 lowercase hex>`. |
| [`defs/urn-artifact.json`](defs/urn-artifact.json) | `urn:sha256:<64 lowercase hex>`. |
| [`defs/did.json`](defs/did.json) | DID or DID URL with fragment. |
| [`defs/rfc3339.json`](defs/rfc3339.json) | RFC 3339 date-time with mandatory offset. |

## Design rules

- `additionalProperties: false` on every object except `extensions` (whose keys must be reverse-DNS names) ([REQ-0003], [REQ-0110]).
- Conditional rules use `if`/`then`:
  - `prompt.storage = escrow` ⇒ `escrow_ref` required, `text` forbidden, salted `canonicalization` ([REQ-0043], [REQ-0052]);
  - `prompt.storage = public` ⇒ `text` required, `disclosure_policy = public`, unsalted `canonicalization` ([REQ-0045], [REQ-0305], [REQ-0052]);
  - `prompt.storage = none` ⇒ `escrow_ref` and `text` forbidden, salted `canonicalization` ([REQ-0046], [REQ-0052]);
  - `generation.kind = edited | derived` ⇒ `parents` has at least one entry ([REQ-0073]);
  - `generation.kind = created` ⇒ no parent with `relation = previous_version` ([REQ-0074]).
- `dependentRequired`: `runtime.volatile` requires `runtime.params_hash` ([REQ-0039]).
- Every `description` names the REQ-ID it implements.

## What the schema cannot check

These are Verifier checks (SPEC.md §9.2 step 5 and later) and are exercised by `fixtures/regen.py`:

- a parent id equal to `artifact.id` ([REQ-0072]);
- duplicate (`id`, `relation`) pairs and more than one `previous_version` ([REQ-0075], [REQ-0077]);
- duplicate JSON member names ([REQ-0004]);
- `prompt.text` matching `prompt.hash` ([REQ-0302]);
- `previous_version` media types across manifests ([REQ-0402]);
- everything involving bytes, signatures and timestamps.

## Identifiers and references

The schemas carry `$id`s under `https://ailineage.org/schema/`. Until that URL is live, validate with a local base URI, which the Makefile does:

```sh
check-jsonschema --schemafile schema/lineage-0.1.json \
  --base-uri "file://$PWD/schema/lineage-0.1.json" fixtures/valid/*.json
```
