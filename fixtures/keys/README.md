# Test keys — TEST ONLY

**These keys are public. They exist only to sign the fixtures in this repository. No Verifier may trust them outside of test mode ([REQ-0606]).**

| File | Purpose |
| --- | --- |
| `test-ed25519.key` / `test-ed25519.pub` | Ed25519 key (PKCS#8 / SPKI PEM) for `EdDSA` fixtures. `kid` is the matching `did:key`. |
| `test-p256.key` / `test-p256.pub` | P-256 key for `ES256` fixtures (fixture 04). |
| `freetsa-cacert.pem` | Root CA of [freetsa.org](https://freetsa.org/), the TSA used for fixture timestamps. Trust anchor for `make validate` only. |
| `freetsa-tsa.crt` | freetsa.org TSA signing certificate. |

`fixtures/regen.py` generates the test keys with `openssl genpkey` if they are missing. The freetsa.org certificates were downloaded from <https://freetsa.org/files/>.
