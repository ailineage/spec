# Security Policy

## Scope

This repository is a specification. Security reports are welcome for:

- flaws in the **specification** that allow a forged, transplanted, backdated or replayed manifest to verify as `PROVENANCED`;
- ambiguities in **canonicalization** or **per-format hashing** that let two conforming implementations disagree;
- weaknesses in the **escrow and disclosure model** (prompt confidentiality, audit integrity, custodian trust);
- privacy issues, such as fields that leak more about the principal than documented;
- errors in fixtures or test vectors that would lead implementers to insecure behaviour.

Vulnerabilities in implementations belong to the respective sister repository's security policy.

## Reporting

Please do **not** open a public issue. Report privately via:

1. GitHub **private vulnerability reporting** on this repository (*Security* tab → *Report a vulnerability*), or
2. e-mail to <security@ailineage.org>.

Include the affected section or REQ-ID, a description, and if possible a manifest or artifact that demonstrates the issue.

## Process

| Step | Target |
| --- | --- |
| Acknowledgement | 3 working days |
| Initial assessment | 10 working days |
| Fix in the specification (ADR + errata) | depends on severity; coordinated with the reporter |
| Public disclosure | after a fix is published, or 90 days after the report, whichever comes first |

Reporters are credited in the ADR and CHANGELOG unless they ask otherwise.

## Test keys

The keys in `fixtures/keys/` are **public test keys**. They sign only test fixtures. Reports that these keys are exposed are not vulnerabilities; reports of software trusting them outside test mode are, and belong to that software's maintainers.
