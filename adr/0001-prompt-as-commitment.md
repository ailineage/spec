# ADR-0001: Prompt as commitment, not plaintext

- Status: Accepted
- Date: 2026-10-19
- Deciders: Ol1n
- Affects: SPEC.md §4.4, §6, §13; REQ-0040–0051, REQ-0300–0307, REQ-0801–0804

## Context

Accountability for an AI artifact often depends on the instruction that produced it: was the defamatory image requested, or did the model drift? Was the code written to a specification? Yet prompts routinely contain trade secrets, personal data, unreleased product details or private conversations. A format that publishes prompts will not be adopted by companies, and it would turn every shared artifact into a privacy leak. A format that records nothing about the prompt cannot support later disputes.

## Decision

The manifest carries a **commitment** to the prompt, `prompt.hash` = SHA-256 over a canonical form ([CANONICALIZATION.md](../CANONICALIZATION.md)), never the plaintext by default.

- `storage` declares where the plaintext is: `none`, `escrow` (ciphertext at a custodian, referenced by `escrow_ref`) or `public` (in `prompt.text`).
- `disclosure_policy` declares who may later obtain it.
- Disclosure happens outside the manifest and is audited; anyone can check a disclosed plaintext against the commitment.
- System prompt and context material get their own commitments (`system_prompt_hash`, `context_refs`).

## Consequences

- Manifests can be shared publicly without exposing prompts.
- A commitment proves binding, not content: until disclosure, nobody can tell which prompt was used (THREAT_MODEL T5). The spec says so explicitly.
- Canonicalization becomes critical: two systems must produce identical bytes for the same prompt. Test vectors are mandatory and machine-checked.
- Short or predictable prompts can be recovered by guessing the hash input. This is documented ([REQ-0804]); a salted variant is an open question.
- Escrow introduces a custodian role with legal duties (retention, erasure, disclosure). That role is optional ([ADR-0006](0006-registry-and-escrow-model.md)).

## Alternatives

- **Plaintext always.** Simplest to verify. Rejected: unacceptable for confidential and personal data, conflicts with GDPR data minimisation, would block adoption by deployers.
- **Nothing about the prompt.** Maximum privacy. Rejected: removes the "from what" in "who asked, which model, from what"; disputes would rely on unverifiable recollection.
- **Encrypted prompt inside the manifest.** Rejected: ciphertext travels with every copy forever, keys get lost or leaked, and later algorithm breaks expose all copies. Keeping ciphertext at a custodian limits copies and allows audited release.
- **Salted or keyed commitment (HMAC).** Defeats guessing attacks. Deferred to a future version because it needs a salt-handling story for disclosure; tracked in OPEN_QUESTIONS.md.
