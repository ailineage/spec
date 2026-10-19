# ADR-0008: Mandatory salted prompt commitment

- Status: Accepted
- Date: 2026-10-19
- Deciders: Ol1n
- Affects: SPEC.md §4.4, §6.2–6.4, §13; REQ-0040, REQ-0041, REQ-0049, REQ-0052, REQ-0303, REQ-0307–0311, REQ-0804; CANONICALIZATION.md §5; schema `prompt`. Amends [ADR-0001](0001-prompt-as-commitment.md). Resolves OPEN_QUESTIONS.md question 2.

## Context

[ADR-0001](0001-prompt-as-commitment.md) replaced the prompt with a hash commitment so that manifests can be public while prompts stay private. A plain SHA-256 commitment does not achieve that for most real prompts:

- **Guessing.** Short, templated or partly known prompts can be recovered by hashing candidates until one matches. Canonicalization helps the attacker, because whitespace and line-ending variants no longer need to be tried. The 0.1 draft's own minimal fixture (`"Say hello."`) was recovered in five guesses; commodity GPUs try billions of candidates per second.
- **Linking.** Identical prompts give identical hashes, so anyone can see that two manifests, possibly from different people, came from the same instruction.

The change alters what is hashed, which changes every fixture and signature. It therefore had to be decided before the reference implementation (phase 2).

## Decision

1. A commitment that hides a prompt is **salted**: `prompt.hash = SHA-256(salt || canonical bytes)` with a fresh 32-byte salt from a CSPRNG, per commitment.
2. Salting is **mandatory** for `storage = escrow` and `storage = none`, expressed by the canonicalization methods `utf8-nfc-trim-salted-v1` and `multimodal-salted-v1`. The schema enforces the pairing.
3. `storage = public` keeps the unsalted methods `utf8-nfc-trim-v1` and `multimodal-v1`; the text is in the manifest anyway and Verifiers re-hash it.
4. `system_prompt_hash` uses the same method as `prompt.hash`, with its own salt.
5. The salt never appears in the manifest. It is kept with the plaintext: inside the escrow ciphertext, or with the principal. The pair (plaintext, salt) is the *opening*; a disclosure releases both.
6. No new manifest member is introduced; the method name carries the information.

## Consequences

- Guessing and hash-equality linking are no longer possible for hidden prompts.
- Losing the salt makes a commitment permanently unopenable. Custodians must keep salts as long as the escrow record; principals with `storage = none` must keep them if they may ever need to prove their prompt. Discarding the salt is allowed only with `disclosure_policy = none`.
- Cross-manifest searches such as "was this known prompt used anywhere" are impossible without the openings. This is intended.
- Producers need a CSPRNG and must persist the salt next to the plaintext; the escrow payload grows by 32 bytes.
- `context_refs` remain unsalted artifact identifiers; known documents in the context stay testable (SPEC.md [REQ-0804]).
- All valid fixtures except the public-prompt fixture were re-generated; test salts and openings are published in `fixtures/data/` as TEST ONLY material, and `make validate` verifies every opening.

## Alternatives

- **No salt, document the risk.** Rejected: the commitment would leak most real prompts, defeating the purpose of ADR-0001.
- **Optional salt chosen by the Producer.** Rejected: Producers would default to the simpler unsalted form, and Verifiers could not tell users whether a commitment is hiding.
- **HMAC with a per-principal key.** Rejected: disclosing one prompt would require releasing the key, which exposes every other prompt of that principal to guessing.
- **Salt reference in the manifest (`prompt.salt_ref`).** Rejected: adds a member and a second lookup for no gain; the salt belongs with the plaintext it protects.
