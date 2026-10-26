#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""AILineage spec 0.1 -- fixture generator and checker.

This is the only executable code in the spec repository. It uses the
Python standard library plus the `openssl` command line tool (3.0+).

Subcommands:
  regen         regenerate sample data, fixtures, examples, test vectors and
                generated Markdown blocks.  Existing signatures and RFC 3161
                tokens are reused when the signing input is unchanged, so the
                command is idempotent and does not hit the TSA needlessly.
  check         verify every valid fixture (artifact hash, prompt hash,
                signature, timestamp, semantic rules) and every example.
  semantic F..  apply verifier-only semantic rules (SPEC.md section 9) to the
                given manifests; exit 1 if any manifest violates them.
  test-vectors  recompute CANONICALIZATION.md test vectors and check that the
                document and fixtures/vectors/canonicalization.json agree.

TEST ONLY: the keys under fixtures/keys/ are public test keys.  Never trust
them outside of test fixtures.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import math
import os
import re
import struct
import subprocess
import sys
import tempfile
import unicodedata
import urllib.request
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "fixtures"
DATA = FIX / "data"
KEYS = FIX / "keys"
VALID = FIX / "valid"
INVALID = FIX / "invalid"
VECTORS = FIX / "vectors"
EXAMPLES = ROOT / "examples"

SALTS_FILE = DATA / "salts.json"
OPENINGS_FILE = DATA / "openings.json"
INDEX_FILE = FIX / "index.json"
TSA_URL = os.environ.get("AILINEAGE_TSA_URL", "https://freetsa.org/tsr")
TSA_CA = KEYS / "freetsa-cacert.pem"
TSA_CERT = KEYS / "freetsa-tsa.crt"
PLACEHOLDER_NOTE = "ts is placeholder"

ED_KEY, ED_PUB = KEYS / "test-ed25519.key", KEYS / "test-ed25519.pub"
P256_KEY, P256_PUB = KEYS / "test-p256.key", KEYS / "test-p256.pub"

# ---------------------------------------------------------------------------
# JCS (RFC 8785)
# ---------------------------------------------------------------------------


def _es_number(x) -> str:
    """Serialize a number the way ECMAScript Number.prototype.toString does."""
    if isinstance(x, bool):
        raise TypeError("bool is not a number")
    if isinstance(x, int):
        if abs(x) > 2**53 - 1:
            raise ValueError("integer outside IEEE-754 safe range: %d" % x)
        return str(x)
    if not math.isfinite(x):
        raise ValueError("NaN/Infinity are not allowed in JCS")
    if x == 0:
        return "0"
    sign = "-" if x < 0 else ""
    r = repr(abs(x))  # shortest round-trip representation
    if "e" in r:
        mant, exp = r.split("e")
        exp = int(exp)
    else:
        mant, exp = r, 0
    if "." in mant:
        ip, fp = mant.split(".")
    else:
        ip, fp = mant, ""
    digits = (ip + fp).lstrip("0")
    # position of decimal point relative to the start of `digits`
    lead_zeros = len(ip + fp) - len((ip + fp).lstrip("0"))
    n = len(ip) - lead_zeros + exp
    digits = digits.rstrip("0") or "0"
    k = len(digits)
    if k <= n <= 21:
        out = digits + "0" * (n - k)
    elif 0 < n <= 21:
        out = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        out = "0." + "0" * (-n) + digits
    else:
        e = n - 1
        es = ("+" if e >= 0 else "-") + str(abs(e))
        out = digits[0] + ("." + digits[1:] if k > 1 else "") + "e" + es
    return sign + out


def _jcs_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def jcs(value) -> str:
    """Return the RFC 8785 canonical serialization of `value` as str."""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return _es_number(value)
    if isinstance(value, str):
        return _jcs_str(value)
    if isinstance(value, list):
        return "[" + ",".join(jcs(v) for v in value) + "]"
    if isinstance(value, dict):
        keys = sorted(value.keys(), key=lambda k: k.encode("utf-16-be"))
        return "{" + ",".join(_jcs_str(k) + ":" + jcs(value[k]) for k in keys) + "}"
    raise TypeError("unsupported type %r" % type(value))


def jcs_bytes(value) -> bytes:
    return jcs(value).encode("utf-8")


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def h(b: bytes) -> str:
    return "sha256:" + sha256_hex(b)


def urn(b: bytes) -> str:
    return "urn:sha256:" + sha256_hex(b)


# ---------------------------------------------------------------------------
# Prompt canonicalization (CANONICALIZATION.md section 3/4)
# ---------------------------------------------------------------------------

# Unicode White_Space=yes code points, minus U+000A LINE FEED (line separator)
WS = "\u0009\u000b\u000c\u000d \u0085  " + "".join(
    chr(c) for c in range(0x2000, 0x200B)
) + "    　"


def canon_text(text: str) -> str:
    t = unicodedata.normalize("NFC", text)                 # step 1
    t = t.replace("\r\n", "\n").replace("\r", "\n")         # step 2
    t = "\n".join(line.rstrip(WS) for line in t.split("\n"))  # step 3
    t = t.strip(WS + "\n")                                  # step 4
    return t


def prompt_bytes_v1(text: str) -> bytes:
    return canon_text(text).encode("utf-8")                 # step 5


def prompt_bytes_multimodal(text: str, attachments: list[str]) -> bytes:
    return jcs_bytes({"attachments": list(attachments), "text": canon_text(text)})


SALTED = {"utf8-nfc-trim-v1": "utf8-nfc-trim-salted-v1",
          "multimodal-v1": "multimodal-salted-v1"}
UNSALTED = {v: k for k, v in SALTED.items()}


def salted_commit(canonical: bytes, salt: bytes) -> str:
    """CANONICALIZATION.md section 5: SHA-256(salt || canonical bytes)."""
    if len(salt) != 32:
        raise ValueError("salt must be exactly 32 bytes")
    return h(salt + canonical)


def params_hash(params: dict, volatile: list[str]) -> str:
    kept = {k: v for k, v in params.items() if k not in set(volatile)}
    return h(jcs_bytes(kept))


# ---------------------------------------------------------------------------
# Container helpers: PNG, JPEG, WebP, text header comment
# ---------------------------------------------------------------------------

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def png_chunk(ctype: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + ctype + data + struct.pack(
        ">I", zlib.crc32(ctype + data) & 0xFFFFFFFF
    )


def png_chunks(b: bytes):
    assert b[:8] == PNG_SIG, "not a PNG"
    i = 8
    while i < len(b):
        (n,) = struct.unpack(">I", b[i:i + 4])
        ctype = b[i + 4:i + 8]
        data = b[i + 8:i + 8 + n]
        yield i, i + 12 + n, ctype, data
        i += 12 + n


def png_is_ailineage_itxt(ctype: bytes, data: bytes) -> bool:
    return ctype == b"iTXt" and data.split(b"\x00", 1)[0] == b"ailineage"


def png_strip(b: bytes) -> bytes:
    out = bytearray(PNG_SIG)
    for s, e, ctype, data in png_chunks(b):
        if not png_is_ailineage_itxt(ctype, data):
            out += b[s:e]
    return bytes(out)


def png_embed(b: bytes, manifest_json: bytes) -> bytes:
    """Insert an iTXt 'ailineage' chunk immediately before IEND."""
    data = b"ailineage\x00" + b"\x00\x00" + b"\x00" + b"\x00" + manifest_json
    out = bytearray(PNG_SIG)
    for s, e, ctype, _ in png_chunks(png_strip(b)):
        if ctype == b"IEND":
            out += png_chunk(b"iTXt", data)
        out += png_strip(b)[s:e]
    return bytes(out)


def make_png(w: int, h_: int, pixel) -> bytes:
    raw = bytearray()
    for y in range(h_):
        raw.append(0)  # filter type None
        for x in range(w):
            raw += bytes(pixel(x, y))
    ihdr = struct.pack(">IIBBBBB", w, h_, 8, 2, 0, 0, 0)
    return PNG_SIG + png_chunk(b"IHDR", ihdr) + png_chunk(
        b"IDAT", zlib.compress(bytes(raw), 9)
    ) + png_chunk(b"IEND", b"")


# JPEG: APP11 segments carrying a JUMBF superbox labelled 'ailineage' (§5.3)
JUMBF_JSON_UUID = bytes.fromhex("6a736f6e00110010800000aa00389b71")
JPEG_LABEL = b"ailineage"
JPEG_MAX_PAYLOAD = 0xFFFF - 2 - 8 - 8  # Le, CI+En+Z, repeated LBox+TBox


def jpeg_segments(b: bytes):
    """Yield (start, end, marker) for each marker segment before the first SOS,
    then (start, len(b), 0xDA) for SOS and everything after it."""
    assert b[:2] == b"\xff\xd8", "not a JPEG"
    i = 2
    while i < len(b):
        assert b[i] == 0xFF, "bad marker at %d" % i
        m = b[i + 1]
        if m == 0xDA:
            yield i, len(b), m
            return
        (n,) = struct.unpack(">H", b[i + 2:i + 4])
        yield i, i + 2 + n, m
        i += 2 + n


def jpeg_ailineage_en(b: bytes) -> set[int]:
    """Box instance numbers (En) of JUMBF boxes whose description label is 'ailineage'."""
    ens = set()
    for s, e, m in jpeg_segments(b):
        seg = b[s + 4:e]
        if m != 0xEB or seg[:2] != b"JP":
            continue
        (en,), (z,) = struct.unpack(">H", seg[2:4]), struct.unpack(">I", seg[4:8])
        box = seg[8:]
        if z == 1 and box[4:8] == b"jumb" and box[12:16] == b"jumd" and \
                box[16:32] == JUMBF_JSON_UUID and box[32] & 0x02 and \
                box[33:].split(b"\x00", 1)[0] == JPEG_LABEL:
            ens.add(en)
    return ens


def jpeg_strip(b: bytes) -> bytes:
    ens = jpeg_ailineage_en(b)
    out = bytearray(b[:2])
    for s, e, m in jpeg_segments(b):
        if m == 0xEB and b[s + 4:s + 6] == b"JP" and \
                struct.unpack(">H", b[s + 6:s + 8])[0] in ens:
            continue
        out += b[s:e]
    return bytes(out)


def jpeg_embed(b: bytes, manifest_json: bytes, en: int = 0x4149) -> bytes:
    """Insert the manifest as APP11/JUMBF segment(s) after the last APPn segment
    before the first non-APPn marker (or directly after SOI)."""
    b = jpeg_strip(b)
    label = JPEG_LABEL + b"\x00"
    jumd = struct.pack(">I", 8 + 16 + 1 + len(label)) + b"jumd" + JUMBF_JSON_UUID + b"\x03" + label
    jbox = struct.pack(">I", 8 + len(manifest_json)) + b"json" + manifest_json
    payload = jumd + jbox
    head = struct.pack(">I", 8 + len(payload)) + b"jumb"
    segs = bytearray()
    for z, off in enumerate(range(0, len(payload), JPEG_MAX_PAYLOAD), start=1):
        body = b"JP" + struct.pack(">HI", en, z) + head + payload[off:off + JPEG_MAX_PAYLOAD]
        segs += b"\xff\xeb" + struct.pack(">H", 2 + len(body)) + body
    at = 2
    for s, e, m in jpeg_segments(b):
        if 0xE0 <= m <= 0xEF:
            at = e
        else:
            break
    return b[:at] + bytes(segs) + b[at:]


# WebP: top-level RIFF chunk 'AILN' in the extended (VP8X) format (§5.4)
def riff_chunks(b: bytes):
    assert b[:4] == b"RIFF" and b[8:12] == b"WEBP", "not a WebP"
    i = 12
    while i < len(b):
        fourcc = b[i:i + 4]
        (n,) = struct.unpack("<I", b[i + 4:i + 8])
        yield i, i + 8 + n + (n & 1), fourcc
        i += 8 + n + (n & 1)


def riff_build(chunks: bytes) -> bytes:
    return b"RIFF" + struct.pack("<I", 4 + len(chunks)) + b"WEBP" + chunks


def webp_strip(b: bytes) -> bytes:
    return riff_build(b"".join(b[s:e] for s, e, c in riff_chunks(b) if c != b"AILN"))


def webp_extend(b: bytes) -> bytes:
    """Convert a simple-format WebP (one VP8 or VP8L chunk) to the extended format
    by prepending a VP8X chunk. Pure container rewrite; the bitstream is untouched."""
    chunks = list(riff_chunks(b))
    if chunks[0][2] == b"VP8X":
        return b
    (s, e, c), = chunks
    data = b[s + 8:e]
    if c == b"VP8L":
        v = int.from_bytes(data[1:5], "little")
        w, h_, alpha = (v & 0x3FFF) + 1, ((v >> 14) & 0x3FFF) + 1, (v >> 28) & 1
    elif c == b"VP8 ":
        w, h_, alpha = (struct.unpack("<H", data[6:8])[0] & 0x3FFF,
                        struct.unpack("<H", data[8:10])[0] & 0x3FFF, 0)
    else:
        raise ValueError("unsupported WebP chunk %r" % c)
    vp8x = bytes([0x10 if alpha else 0]) + b"\x00\x00\x00" + \
        (w - 1).to_bytes(3, "little") + (h_ - 1).to_bytes(3, "little")
    return riff_build(b"VP8X" + struct.pack("<I", 10) + vp8x + b[s:e])


def webp_embed(b: bytes, manifest_json: bytes) -> bytes:
    """Append an 'AILN' chunk as the last chunk of the extended-format file."""
    b = webp_strip(webp_extend(b))
    pad = b"\x00" if len(manifest_json) & 1 else b""
    return riff_build(b[12:] + b"AILN" + struct.pack("<I", len(manifest_json)) +
                      manifest_json + pad)


HEADER_RE = re.compile(rb"ailineage: urn:sha256:[0-9a-f]{64}")


def text_strip_header(b: bytes) -> bytes:
    """Remove the first line (within the first 3 lines) carrying the
    'ailineage: urn:sha256:<hex>' header comment, including its terminator."""
    lines = b.splitlines(keepends=True)
    for i, line in enumerate(lines[:3]):
        if HEADER_RE.search(line):
            return b"".join(lines[:i] + lines[i + 1:])
    return b


def make_wav(seconds: float = 0.1, rate: int = 48000, freq: float = 440.0) -> bytes:
    n = int(seconds * rate)
    frames = b"".join(
        struct.pack("<h", int(12000 * math.sin(2 * math.pi * freq * i / rate)))
        for i in range(n)
    )
    fmt = struct.pack("<HHIIHH", 1, 1, rate, rate * 2, 2, 16)
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack(
        "<I", len(frames)
    ) + frames
    return b"RIFF" + struct.pack("<I", len(body)) + body


def dhash64(png: bytes) -> str:
    """Tiny 8x8 difference hash over the luminance of an 8-bit RGB PNG
    without interlace, using only filter type 0 (as produced here)."""
    w = h_ = None
    idat = b""
    for _, _, ctype, data in png_chunks(png):
        if ctype == b"IHDR":
            w, h_ = struct.unpack(">II", data[:8])
        elif ctype == b"IDAT":
            idat += data
    raw = zlib.decompress(idat)
    stride = 1 + 3 * w

    def lum(x, y):
        o = y * stride + 1 + 3 * x
        r, g, b = raw[o], raw[o + 1], raw[o + 2]
        return 0.299 * r + 0.587 * g + 0.114 * b

    def cell(cx, cy):  # mean luminance of a 9x8 grid cell
        xs = range(cx * w // 9, (cx + 1) * w // 9)
        ys = range(cy * h_ // 8, (cy + 1) * h_ // 8)
        vals = [lum(x, y) for y in ys for x in xs]
        return sum(vals) / len(vals)

    bits = 0
    for cy in range(8):
        row = [cell(cx, cy) for cx in range(9)]
        for cx in range(8):
            bits = (bits << 1) | (1 if row[cx] > row[cx + 1] else 0)
    return "%016x" % bits


# ---------------------------------------------------------------------------
# Keys, did:key, signing (via openssl CLI)
# ---------------------------------------------------------------------------

B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58(b: bytes) -> str:
    n = int.from_bytes(b, "big")
    s = ""
    while n:
        n, r = divmod(n, 58)
        s = B58[r] + s
    return "1" * (len(b) - len(b.lstrip(b"\x00"))) + s


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def b64u_dec(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def run(args, inp: bytes | None = None, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(args, input=inp, capture_output=True, check=check)


def ensure_keys():
    KEYS.mkdir(parents=True, exist_ok=True)
    if not ED_KEY.exists():
        run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(ED_KEY)])
        run(["openssl", "pkey", "-in", str(ED_KEY), "-pubout", "-out", str(ED_PUB)])
    if not P256_KEY.exists():
        run(["openssl", "genpkey", "-algorithm", "EC", "-pkeyopt",
             "ec_paramgen_curve:P-256", "-out", str(P256_KEY)])
        run(["openssl", "pkey", "-in", str(P256_KEY), "-pubout", "-out", str(P256_PUB)])


def pub_der(pub: Path) -> bytes:
    return run(["openssl", "pkey", "-pubin", "-in", str(pub), "-outform", "DER"]).stdout


def did_key(alg: str) -> str:
    if alg == "EdDSA":
        raw = pub_der(ED_PUB)[-32:]
        mc = b"\xed\x01" + raw
    else:
        pt = pub_der(P256_PUB)[-65:]  # uncompressed point 04||X||Y
        assert pt[0] == 4
        x, y = pt[1:33], pt[33:]
        mc = b"\x80\x24" + bytes([2 + (y[-1] & 1)]) + x  # p256-pub varint 0x1200
    fp = "z" + b58(mc)
    return "did:key:%s#%s" % (fp, fp)


def _der_int(b: bytes, i: int):
    assert b[i] == 2
    n = b[i + 1]
    return int.from_bytes(b[i + 2:i + 2 + n], "big"), i + 2 + n


def _ecdsa_der_to_raw(der: bytes) -> bytes:
    assert der[0] == 0x30
    i = 2 if der[1] < 0x80 else 3
    r, i = _der_int(der, i)
    s, _ = _der_int(der, i)
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


def _int_der(n: int) -> bytes:
    b = n.to_bytes(32, "big").lstrip(b"\x00") or b"\x00"
    if b[0] & 0x80:
        b = b"\x00" + b
    return b"\x02" + bytes([len(b)]) + b


def _ecdsa_raw_to_der(raw: bytes) -> bytes:
    body = _int_der(int.from_bytes(raw[:32], "big")) + _int_der(int.from_bytes(raw[32:], "big"))
    return b"\x30" + bytes([len(body)]) + body


def sign(alg: str, msg: bytes) -> bytes:
    with tempfile.NamedTemporaryFile() as f:
        f.write(msg)
        f.flush()
        if alg == "EdDSA":
            return run(["openssl", "pkeyutl", "-sign", "-inkey", str(ED_KEY),
                        "-rawin", "-in", f.name]).stdout
        der = run(["openssl", "dgst", "-sha256", "-sign", str(P256_KEY), f.name]).stdout
        return _ecdsa_der_to_raw(der)


def verify_sig(alg: str, msg: bytes, sig: bytes) -> bool:
    with tempfile.TemporaryDirectory() as d:
        m, s = Path(d) / "m", Path(d) / "s"
        m.write_bytes(msg)
        if alg == "EdDSA":
            s.write_bytes(sig)
            r = run(["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(ED_PUB),
                     "-rawin", "-in", str(m), "-sigfile", str(s)], check=False)
        else:
            if len(sig) != 64:
                return False
            s.write_bytes(_ecdsa_raw_to_der(sig))
            r = run(["openssl", "dgst", "-sha256", "-verify", str(P256_PUB),
                     "-signature", str(s), str(m)], check=False)
        return r.returncode == 0


# ---------------------------------------------------------------------------
# RFC 3161
# ---------------------------------------------------------------------------


def tsa_token(imprint_hex: str) -> bytes | None:
    """Return a DER TimeStampToken for the SHA-256 imprint, or None."""
    with tempfile.TemporaryDirectory() as d:
        q, r, t = Path(d) / "q.tsq", Path(d) / "r.tsr", Path(d) / "t.der"
        run(["openssl", "ts", "-query", "-digest", imprint_hex, "-sha256", "-cert",
             "-out", str(q)])
        try:
            req = urllib.request.Request(
                TSA_URL, data=q.read_bytes(),
                headers={"Content-Type": "application/timestamp-query"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                r.write_bytes(resp.read())
        except Exception as e:  # network or HTTP failure
            print("  ! TSA unavailable (%s): %s" % (TSA_URL, e), file=sys.stderr)
            return None
        p = run(["openssl", "ts", "-reply", "-in", str(r), "-token_out", "-out", str(t)],
                check=False)
        if p.returncode != 0:
            print("  ! TSA reply unparsable", file=sys.stderr)
            return None
        return t.read_bytes()


def ts_verify(token_der: bytes, imprint_hex: str) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as d:
        t = Path(d) / "t.der"
        t.write_bytes(token_der)
        r = run(["openssl", "ts", "-verify", "-digest", imprint_hex, "-in", str(t),
                 "-token_in", "-CAfile", str(TSA_CA), "-untrusted", str(TSA_CERT)],
                check=False)
        txt = run(["openssl", "ts", "-reply", "-in", str(t), "-token_in", "-text"],
                  check=False).stdout.decode(errors="replace")
        m = re.search(r"Time stamp: (.+)", txt)
        return r.returncode == 0, (m.group(1).strip() if m else "?")


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

D = {}  # name -> bytes


def gradient(x, y):
    return ((x * 4) % 256, (y * 4) % 256, ((x + y) * 2) % 256)


def inpainted(x, y):
    if 24 <= x < 40 and 24 <= y < 40:  # inpainted 16x16 centre region
        return (250, 200, 40)
    return gradient(x, y)


TEXT_FILES = {
    "chat-answer.txt": (
        "A sourdough starter is a fermented mixture of flour and water that hosts\n"
        "wild yeast and lactic acid bacteria. Feed it equal weights of flour and\n"
        "water every 24 hours and keep it at 24-26 C until it doubles reliably.\n"
    ),
    "hello-v0.go": (
        "package main\n\n"
        "import \"fmt\"\n\n"
        "func main() {\n"
        "\tfmt.Println(\"hello\")\n"
        "}\n"
    ),
    "hello.go": (
        "package main\n\n"
        "import (\n"
        "\t\"fmt\"\n"
        "\t\"os\"\n"
        ")\n\n"
        "func main() {\n"
        "\tname := \"world\"\n"
        "\tif len(os.Args) > 1 {\n"
        "\t\tname = os.Args[1]\n"
        "\t}\n"
        "\tfmt.Printf(\"hello, %s\\n\", name)\n"
        "}\n"
    ),
    "CLAUDE.md": (
        "# hello\n\n"
        "- Go 1.24, standard library only.\n"
        "- Keep `main.go` minimal; no global state.\n"
        "- Run `go vet ./...` before committing.\n"
    ),
    "notes-v1.md": "# Release notes\n\n- Initial draft.\n",
    "notes-v2.md": "# Release notes\n\n- Initial draft.\n- Added PNG embedding.\n",
    "notes-v3.md": (
        "# Release notes\n\n- Initial draft.\n- Added PNG embedding.\n"
        "- Fixed JPEG XMP stripping.\n"
    ),
    "ctx-ticket.txt": "TICKET-4127: Customer reports invoice PDF totals off by one cent.\n",
    "ctx-rag-chunk.txt": (
        "Rounding policy: amounts are rounded half-even to two decimals only at\n"
        "the final total, never per line item.\n"
    ),
    "agent-report.md": (
        "# Incident summary TICKET-4127\n\n"
        "Root cause: line items were rounded individually before summation,\n"
        "violating the rounding policy. Fix: round once at the total.\n"
    ),
    "essay.txt": (
        "Provenance is not a verdict about truth. It is a record of who stood\n"
        "behind an artifact and how it was made, so that a claim can be traced\n"
        "back to a person who can be asked.\n"
    ),
    "haiku.txt": "Metadata stripped;\nthe registry still recalls\nwho first asked for this.\n",
    "minimal.txt": "hello\n",
    "pseudonymous.txt": "An anonymous reviewer's AI-drafted summary of a public budget.\n",
}

COMFY_WORKFLOW = {
    "1": {"class_type": "UNETLoader",
          "inputs": {"unet_name": "flux1-schnell.safetensors", "weight_dtype": "default"}},
    "2": {"class_type": "DualCLIPLoader",
          "inputs": {"clip_name1": "t5xxl_fp8_e4m3fn.safetensors",
                     "clip_name2": "clip_l.safetensors", "type": "flux"}},
    "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": "<prompt>"}},
    "4": {"class_type": "EmptySD3LatentImage",
          "inputs": {"width": 64, "height": 64, "batch_size": 1}},
    "5": {"class_type": "KSampler",
          "inputs": {"model": ["1", 0], "positive": ["3", 0], "negative": ["3", 0],
                     "latent_image": ["4", 0], "seed": 424242, "steps": 4, "cfg": 1.0,
                     "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
    "6": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
    "7": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["6", 0]}},
    "8": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": "ail"}},
}


def build_data(write: bool):
    D["image-64.png"] = make_png(64, 64, gradient)
    D["image-64-inpaint.png"] = make_png(64, 64, inpainted)
    D["song.wav"] = make_wav()
    D["comfyui-workflow.json"] = (json.dumps(COMFY_WORKFLOW, indent=2) + "\n").encode()
    for name, txt in TEXT_FILES.items():
        D[name] = txt.encode("utf-8")
    if write:
        DATA.mkdir(parents=True, exist_ok=True)
        for name, b in D.items():
            (DATA / name).write_bytes(b)
    load_salts(write)
    # clip.mp4 is produced once by ffmpeg (see fixtures/README.md) and committed.
    D["clip.mp4"] = (DATA / "clip.mp4").read_bytes()
    # image-64.jpg and image-64.webp are produced once by ffmpeg and cwebp
    # (see fixtures/README.md). The WebP artifact is the extended-format file
    # (REQ-0226), derived here by a pure container rewrite.
    D["image-64.jpg"] = (DATA / "image-64.jpg").read_bytes()
    D["image-64.webp"] = (DATA / "image-64.webp").read_bytes()
    D["image-64.ext.webp"] = webp_extend(D["image-64.webp"])


SALTS: dict[str, bytes] = {}


def load_salts(write: bool):
    """TEST ONLY salts, one per committed prompt. Created once with a CSPRNG
    and kept in data/salts.json so that regeneration is idempotent."""
    stored = json.loads(SALTS_FILE.read_text()) if SALTS_FILE.exists() else {}
    needed = [k for k in PROMPTS if k not in PUBLIC_PROMPTS]
    changed = False
    for k in needed:
        if k not in stored:
            if not write:
                raise SystemExit("missing salt for prompt %r; run make fixtures-regen" % k)
            stored[k] = b64u(os.urandom(32))
            changed = True
    if write and changed:
        SALTS_FILE.write_text(json.dumps(
            {"_note": "TEST ONLY salts for fixture prompts", **dict(sorted(
                (k, v) for k, v in stored.items() if not k.startswith("_")))}, indent=2) + "\n")
    for k, v in stored.items():
        if not k.startswith("_"):
            SALTS[k] = b64u_dec(v)


def commit(pid: str) -> str:
    return salted_commit(prompt_bytes_v1(PROMPTS[pid]), SALTS[pid])


def stand_in(label: str) -> str:
    """version_hash stand-in: real weights are not shipped with the spec."""
    return h(("TEST-ONLY weights stand-in: " + label).encode())


# ---------------------------------------------------------------------------
# Fixture definitions
# ---------------------------------------------------------------------------

REG = "registry.ailineage.org"
ESC = "urn:ailineage:escrow:" + REG + ":"


def reg_ref(b: bytes) -> str:
    return "urn:ailineage:registry:%s:%s" % (REG, sha256_hex(b))


OPERATOR = "did:web:ol1n.com"
DEPLOYER = "did:web:lineage.ol1n.com"

PROMPTS = {
    "01": "A watercolor fox sleeping under a birch tree, soft morning light, 64x64 icon",
    "02": "How do I keep a sourdough starter alive? Short answer please.",
    "02-system": "You are a concise baking assistant. Answer in three sentences or fewer.",
    "03": "Make hello.go greet the name passed as the first CLI argument, default to world.",
    "04": "lo-fi piano loop, 70 bpm, warm vinyl crackle, A minor",
    "05": "Slow 1-second push-in on the fox icon, keep the palette.",
    "06": "Replace the centre with a glowing yellow lantern.",
    "07-1": "Start release notes with a single 'Initial draft.' bullet.",
    "07-2": "Add a bullet about PNG embedding.",
    "07-3": "Add a bullet about the JPEG XMP stripping fix.",
    "08": "Investigate TICKET-4127 using the rounding policy and write an incident summary.",
    "09": "Suggest a tighter final sentence for my paragraph about provenance.",
    "10": "Write a haiku about stripped metadata and a registry that remembers.",
    "11": "Say hello.",
    "12": "Summarise the 2027 municipal budget proposal in two sentences.",
    "13": "A watercolor fox sleeping under a birch tree, JPEG output for the web gallery",
    "14": "A watercolor fox sleeping under a birch tree, lossless WebP sticker",
}


PUBLIC_PROMPTS = {"10"}


def base(name, media_type, created_at, kind, model, prompt, parents=None, actor=None,
         flags=None, runtime=None, extra=None, alg="EdDSA"):
    m = {
        "spec": "ailineage/0.1",
        "artifact": {
            "id": urn(D[name]),
            "media_type": media_type,
            "created_at": created_at,
            "size_bytes": len(D[name]),
        },
        "generation": {"kind": kind, "model": model},
        "prompt": prompt,
        "parents": parents or [],
        "actor": actor or {"principal": OPERATOR, "role": "operator", "pseudonymous": False},
        "flags": flags or [],
        "signature": {"alg": alg, "kid": did_key(alg)},
    }
    if runtime:
        m["generation"]["runtime"] = runtime
    for k, v in (extra or {}).items():
        m[k] = v
    return m


def p_escrow(pid, esc_id, policy="on-legal-request", pii=False, **kw):
    d = {"hash": commit(pid), "canonicalization": "utf8-nfc-trim-salted-v1",
         "storage": "escrow", "escrow_ref": ESC + esc_id, "disclosure_policy": policy,
         "contains_pii": pii}
    d.update(kw)
    return d


def p_none(pid, policy="none", **kw):
    d = {"hash": commit(pid), "canonicalization": "utf8-nfc-trim-salted-v1",
         "storage": "none", "disclosure_policy": policy, "contains_pii": False}
    d.update(kw)
    return d


FIXTURES = {}  # filename -> (manifest, data file name, container)


def define_fixtures():
    flux = {"id": "black-forest-labs/flux-schnell", "provider": "bfl.ai",
            "version_hash": stand_in("black-forest-labs/flux-schnell flux1-schnell.safetensors"),
            "card_ref": "https://huggingface.co/black-forest-labs/FLUX.1-schnell"}
    flux_params = {"steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple",
                   "width": 64, "height": 64, "client_id": "c0ffee-run-7",
                   "queued_at": "2026-10-19T06:59:58Z"}
    flux_volatile = ["client_id", "queued_at"]

    FIXTURES["01-image-created-comfyui.json"] = (base(
        "image-64.png", "image/png", "2026-10-19T07:00:00Z", "created", flux,
        p_escrow("01", "01J9ZK3V7Q8M4N5P6R7S8T9V0W"),
        runtime={"tool": "ComfyUI 0.4.1", "workflow_hash": h(jcs_bytes(COMFY_WORKFLOW)),
                 "seed": 424242, "params_hash": params_hash(flux_params, flux_volatile),
                 "volatile": flux_volatile},
        extra={"jurisdiction": {"produced_in": "CZ", "regimes": ["eu-ai-act-art50"]}},
    ), "image-64.png", "png")
    FIXTURES["01-image-created-comfyui.json"][0]["artifact"]["perceptual"] = {
        "alg": "dhash", "value": dhash64(D["image-64.png"])}

    FIXTURES["02-text-created-chat-escrow.json"] = (base(
        "chat-answer.txt", "text/plain; charset=utf-8", "2026-10-19T07:05:12+02:00", "created",
        {"id": "anthropic/claude-sonnet-5-5", "provider": "anthropic.com",
         "version_hash": "build:claude-sonnet-5-5"},
        p_escrow("02", "01J9ZK4A1B2C3D4E5F6G7H8J9K", policy="owner", pii=False,
                 system_prompt_hash=commit("02-system"), turn_index=2),
        runtime={"tool": "AiStack gateway 0.3"},
        actor={"principal": "did:key:z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH",
               "role": "end-user", "pseudonymous": True, "on_behalf_of": DEPLOYER},
    ), "chat-answer.txt", "sidecar")

    FIXTURES["03-code-created-claude-code-sidecar.json"] = (base(
        "hello.go", "text/x-go; charset=utf-8", "2026-10-19T07:10:00Z", "edited",
        {"id": "anthropic/claude-fable-5-1", "provider": "anthropic.com",
         "version_hash": "build:claude-fable-5-1",
         "card_ref": "https://www.anthropic.com/claude/fable"},
        p_escrow("03", "01J9ZK5B2C3D4E5F6G7H8J9K0M", policy="owner",
                 context_refs=[urn(D["CLAUDE.md"])], turn_index=0),
        parents=[{"id": urn(D["hello-v0.go"]), "relation": "previous_version"}],
        runtime={"tool": "Claude Code 2.x"},
    ), "hello.go", "sidecar")

    FIXTURES["04-audio-created-acestep.json"] = (base(
        "song.wav", "audio/wav", "2026-10-19T07:15:00Z", "created",
        {"id": "ace-step/acestep-v15-turbo", "provider": "ace-step.github.io",
         "version_hash": stand_in("ace-step/acestep-v15-turbo")},
        p_escrow("04", "01J9ZK6C3D4E5F6G7H8J9K0M1N", policy="owner"),
        runtime={"tool": "AiStack services/audio 0.3", "seed": 7, "params_hash":
                 params_hash({"duration_s": 0.1, "sample_rate": 48000, "infer_steps": 8},
                             [])},
        flags=["training-opt-out"], alg="ES256",
    ), "song.wav", "sidecar")

    img_parent = [{"id": urn(D["image-64.png"]), "relation": "input",
                   "lineage_ref": reg_ref(D["image-64.png"])}]
    FIXTURES["05-video-derived-from-image.json"] = (base(
        "clip.mp4", "video/mp4", "2026-10-19T07:20:00Z", "derived",
        {"id": "wan-ai/wan2.2-ti2v-5b", "provider": "wan.video",
         "version_hash": stand_in("wan-ai/wan2.2-ti2v-5b")},
        p_escrow("05", "01J9ZK7D4E5F6G7H8J9K0M1N2P"),
        parents=img_parent, runtime={"tool": "ComfyUI 0.4.1", "seed": 99},
        flags=["deepfake-candidate"],
    ), "clip.mp4", "sidecar")

    FIXTURES["06-image-edited-inpaint.json"] = (base(
        "image-64-inpaint.png", "image/png", "2026-10-19T07:25:00Z", "edited",
        {"id": "black-forest-labs/flux-fill-dev", "provider": "bfl.ai",
         "version_hash": stand_in("black-forest-labs/flux-fill-dev")},
        p_escrow("06", "01J9ZK8E5F6G7H8J9K0M1N2P3Q"),
        parents=img_parent, runtime={"tool": "ComfyUI 0.4.1", "seed": 31337},
    ), "image-64-inpaint.png", "png")

    opus = {"id": "anthropic/claude-opus-5-5", "provider": "anthropic.com",
            "version_hash": "build:claude-opus-5-5"}
    for i, prev in ((1, None), (2, "notes-v1.md"), (3, "notes-v2.md")):
        parents = [] if prev is None else [{
            "id": urn(D[prev]), "relation": "previous_version",
            "lineage_ref": "https://%s/v0/manifests/%s" % (REG, urn(D[prev]))}]
        FIXTURES["07-chain-v%d.json" % i] = (base(
            "notes-v%d.md" % i, "text/markdown; charset=utf-8",
            "2026-10-19T07:3%d:00Z" % i, "created" if prev is None else "edited", opus,
            p_none("07-%d" % i, policy="none"), parents=parents,
            runtime={"tool": "Claude Code 2.x"},
        ), "notes-v%d.md" % i, "sidecar")

    FIXTURES["08-agent-run-context-refs.json"] = (base(
        "agent-report.md", "text/markdown; charset=utf-8", "2026-10-19T07:40:00Z", "created",
        opus,
        p_escrow("08", "01J9ZK9F6G7H8J9K0M1N2P3Q4R", pii=True,
                 context_refs=[urn(D["ctx-ticket.txt"]), urn(D["ctx-rag-chunk.txt"])],
                 turn_index=5),
        parents=[{"id": urn(D["ctx-rag-chunk.txt"]), "relation": "reference"}],
        runtime={"tool": "Claude Agent SDK 1.x"},
        actor={"principal": "did:web:lineage.ol1n.com:agents:support-triage", "role": "system",
               "pseudonymous": False, "on_behalf_of": OPERATOR},
    ), "agent-report.md", "sidecar")

    FIXTURES["09-assisted-human-authored.json"] = (base(
        "essay.txt", "text/plain; charset=utf-8", "2026-10-19T07:45:00Z", "assisted",
        {"id": "anthropic/claude-haiku-5-5", "provider": "anthropic.com"},
        p_none("09", policy="owner"),
        actor={"principal": "https://olin.now", "role": "end-user", "pseudonymous": False},
        extra={"extensions": {"org.ailineage.example.human-share": {
            "declared_human_words_pct": 85}}},
    ), "essay.txt", "sidecar")

    FIXTURES["10-prompt-public.json"] = (base(
        "haiku.txt", "text/plain; charset=utf-8", "2026-10-19T07:50:00Z", "created",
        {"id": "meta-llama/llama-3.3-70b-instruct", "provider": "llama.com",
         "version_hash": stand_in("meta-llama/Llama-3.3-70B-Instruct")},
        {"hash": h(prompt_bytes_v1(PROMPTS["10"])), "canonicalization": "utf8-nfc-trim-v1",
         "storage": "public", "text": PROMPTS["10"], "disclosure_policy": "public",
         "contains_pii": False},
        runtime={"tool": "AiStack gateway 0.3"},
    ), "haiku.txt", "sidecar")

    m11 = base("minimal.txt", "text/plain", "2026-10-19T07:55:00Z", "created",
               {"id": "anthropic/claude-haiku-5-5", "provider": "anthropic.com"},
               p_none("11"))
    del m11["artifact"]["size_bytes"]
    FIXTURES["11-minimal.json"] = (m11, "minimal.txt", "sidecar")

    FIXTURES["12-pseudonymous-actor.json"] = (base(
        "pseudonymous.txt", "text/plain; charset=utf-8", "2026-10-19T08:00:00Z", "created",
        {"id": "mistralai/mistral-small-3.2-24b-instruct", "provider": "mistral.ai"},
        p_escrow("12", "01J9ZKAG7H8J9K0M1N2P3Q4R5S"),
        actor={"principal": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
               "role": "end-user", "pseudonymous": True},
        flags=["public-interest-text"],
        extra={"jurisdiction": {"produced_in": "CZ", "regimes": ["eu-ai-act-art50"]}},
    ), "pseudonymous.txt", "sidecar")

    FIXTURES["13-image-jpeg-jumbf.json"] = (base(
        "image-64.jpg", "image/jpeg", "2026-10-20T08:00:00Z", "created", flux,
        p_escrow("13", "01J9ZKBH8J9K0M1N2P3Q4R5S6T"),
        runtime={"tool": "ComfyUI 0.4.1", "seed": 424243},
    ), "image-64.jpg", "jpeg")

    FIXTURES["14-image-webp-chunk.json"] = (base(
        "image-64.ext.webp", "image/webp", "2026-10-20T08:05:00Z", "created", flux,
        p_escrow("14", "01J9ZKCJ9K0M1N2P3Q4R5S6T7V"),
        runtime={"tool": "ComfyUI 0.4.1", "seed": 424244},
    ), "image-64.webp", "webp")


def invalid_fixtures(valid: dict) -> dict:
    """Derive negative fixtures from valid ones by a single mutation each."""
    src01 = valid["01-image-created-comfyui.json"]
    src06 = valid["06-image-edited-inpaint.json"]
    src05 = valid["05-video-derived-from-image.json"]
    src10 = valid["10-prompt-public.json"]
    src11 = valid["11-minimal.json"]
    out = {}

    def mut(src, note, fn):
        m = copy.deepcopy(src)
        fn(m)
        m["_note"] = note
        return m

    out["missing-prompt-hash.json"] = mut(src11, "REQ-0040: prompt.hash missing",
                                          lambda m: m["prompt"].pop("hash"))
    out["bad-hash-format.json"] = mut(
        src11, "REQ-0040: prompt.hash not 'sha256:<64 lowercase hex>'",
        lambda m: m["prompt"].__setitem__("hash", "sha256:" + "A" * 64))
    out["escrow-without-ref.json"] = mut(src01, "REQ-0043: storage=escrow without escrow_ref",
                                         lambda m: m["prompt"].pop("escrow_ref"))
    out["escrow-with-text.json"] = mut(src01, "REQ-0043: storage=escrow with text",
                                       lambda m: m["prompt"].__setitem__("text", PROMPTS["01"]))
    out["public-without-text.json"] = mut(src10, "REQ-0045: storage=public without text",
                                          lambda m: m["prompt"].pop("text"))
    out["public-wrong-disclosure-policy.json"] = mut(
        src10, "REQ-0305: storage=public requires disclosure_policy=public",
        lambda m: m["prompt"].__setitem__("disclosure_policy", "owner"))
    out["escrow-unsalted.json"] = mut(
        src01, "REQ-0052: storage=escrow requires a salted canonicalization",
        lambda m: m["prompt"].__setitem__("canonicalization", "utf8-nfc-trim-v1"))
    out["none-unsalted.json"] = mut(
        src11, "REQ-0052: storage=none requires a salted canonicalization",
        lambda m: m["prompt"].__setitem__("canonicalization", "utf8-nfc-trim-v1"))
    out["public-salted.json"] = mut(
        src10, "REQ-0052: storage=public requires an unsalted canonicalization",
        lambda m: m["prompt"].__setitem__("canonicalization", "utf8-nfc-trim-salted-v1"))
    out["none-with-text.json"] = mut(src11, "REQ-0046: storage=none with text",
                                     lambda m: m["prompt"].__setitem__("text", PROMPTS["11"]))
    out["none-with-escrow-ref.json"] = mut(
        src11, "REQ-0046: storage=none with escrow_ref",
        lambda m: m["prompt"].__setitem__("escrow_ref", ESC + "01J9ZKBH8J9K0M1N2P3Q4R5S6T"))
    out["unknown-kind.json"] = mut(src11, "REQ-0030: generation.kind not in enum",
                                   lambda m: m["generation"].__setitem__("kind", "generated"))
    out["edited-without-parents.json"] = mut(src06, "REQ-0073: kind=edited with no parents",
                                             lambda m: m.__setitem__("parents", []))
    out["derived-without-parents.json"] = mut(src05, "REQ-0073: kind=derived with no parents",
                                              lambda m: m.__setitem__("parents", []))

    def created_prev(m):
        m["parents"] = [{"id": urn(D["notes-v1.md"]), "relation": "previous_version"}]
    out["created-with-previous-version.json"] = mut(
        src11, "REQ-0074: kind=created with relation=previous_version", created_prev)
    out["parent-self-reference.json"] = mut(
        src06, "REQ-0072: parent id equals artifact id (semantic rule, schema-valid)",
        lambda m: m["parents"].__setitem__(0, {"id": m["artifact"]["id"], "relation": "input"}))
    out["signature-missing-ts.json"] = mut(src11, "REQ-0124: signature.ts missing",
                                           lambda m: m["signature"].pop("ts"))
    out["unknown-top-level-field.json"] = mut(
        src11, "REQ-0003: additionalProperties=false at top level",
        lambda m: m.__setitem__("model", "anthropic/claude-haiku-5-5"))
    out["extension-not-namespaced.json"] = mut(
        src11, "REQ-0110: extension key not reverse-DNS namespaced",
        lambda m: m.__setitem__("extensions", {"foo": True}))
    return out


SEMANTIC_INVALID = {"parent-self-reference.json"}


def build_index(final: dict) -> dict:
    """Machine-readable test plan for SDK golden tests (fixtures/index.json)."""
    cases = []
    for name, (_m, data, container) in FIXTURES.items():
        if container == "webp":  # the artifact is the extended-format file (REQ-0226)
            continue
        cases.append({"manifest": "fixtures/valid/" + name, "artifact": "fixtures/data/" + data,
                      "locate": "out-of-band", "expect": "PROVENANCED"})
    for d, f, fx in (("png-itxt", "image-64.ailineage.png", "01-image-created-comfyui.json"),
                     ("jpeg-jumbf", "image-64.ailineage.jpg", "13-image-jpeg-jumbf.json"),
                     ("webp-chunk", "image-64.ailineage.webp", "14-image-webp-chunk.json")):
        cases.append({"manifest": "fixtures/valid/" + fx, "artifact": "examples/%s/%s" % (d, f),
                      "locate": "embedded", "expect": "PROVENANCED"})
    cases.append({"manifest": "fixtures/valid/03-code-created-claude-code-sidecar.json",
                  "artifact": "examples/sidecar/hello.go", "locate": "sidecar",
                  "expect": "PROVENANCED"})
    for name in sorted(invalid_fixtures(final)):
        cases.append({"manifest": "fixtures/invalid/" + name, "artifact": None,
                      "locate": "out-of-band", "expect": "PROVENANCE_BROKEN",
                      "reason": "SCHEMA_INVALID"})
    return {
        "_note": "Generated by fixtures/regen.py. 'artifact: null' means a structure-only "
                 "case: Verifier steps 2-5 must fail before the artifact is needed.",
        "trust_policy": {
            "name": "ailineage-test-fixtures (TEST ONLY)",
            "signing_keys": [did_key("EdDSA").split("#")[0], did_key("ES256").split("#")[0]],
            "tsa_roots": ["fixtures/keys/freetsa-cacert.pem"],
        },
        "cases": cases,
    }


def build_openings(final: dict) -> dict:
    """Openings (plaintext + salt) of every salted commitment in the valid
    fixtures. TEST ONLY: in production an opening lives only in escrow or
    with the principal and is released by disclosure (SPEC.md 6.3)."""
    out = {"_note": "TEST ONLY openings of salted prompt commitments"}
    for name, m in sorted(final.items()):
        entries = []
        for field in ("hash", "system_prompt_hash"):
            target = m["prompt"].get(field)
            if not target or m["prompt"]["canonicalization"] not in UNSALTED:
                continue
            for pid, text in PROMPTS.items():
                if pid in SALTS and commit(pid) == target:
                    entries.append({"field": "prompt." + field,
                                    "canonicalization": m["prompt"]["canonicalization"],
                                    "text": text, "salt": b64u(SALTS[pid])})
                    break
            else:
                raise SystemExit("%s: no opening found for prompt.%s" % (name, field))
        if entries:
            out[name] = entries
    return out


def opening_errors(final: dict, openings: dict) -> list[str]:
    errs = []
    for name, entries in openings.items():
        if name.startswith("_"):
            continue
        for e in entries:
            if e["canonicalization"] != "utf8-nfc-trim-salted-v1":
                errs.append("%s: unsupported opening canonicalization" % name)
                continue
            got = salted_commit(prompt_bytes_v1(e["text"]), b64u_dec(e["salt"]))
            want = final[name]["prompt"][e["field"].split(".", 1)[1]]
            if got != want:
                errs.append("%s: opening does not match %s" % (name, e["field"]))
    for name, m in final.items():
        if m["prompt"]["canonicalization"] in UNSALTED and name not in openings:
            errs.append("%s: salted commitment without opening" % name)
    return errs

# ---------------------------------------------------------------------------
# Signing + timestamping a fixture
# ---------------------------------------------------------------------------


def signing_input(m: dict) -> bytes:
    """JCS(manifest) without 'signature' and without annotation members (REQ-0501)."""
    return jcs_bytes({k: v for k, v in m.items()
                      if k != "signature" and not k.startswith("_")})


def finalize(m: dict, path: Path) -> dict:
    """Sign and timestamp `m`; reuse signature+ts from `path` if still valid."""
    alg = m["signature"]["alg"]
    msg = signing_input(m)
    old = None
    if path.exists():
        try:
            old = json.loads(path.read_text())
        except ValueError:
            old = None
    if old is not None:
        old_sig = old.get("signature", {})
        old_m = dict(old)
        old_m.pop("_note", None)
        reusable = (
            signing_input(old_m) == msg
            and old_sig.get("alg") == alg
            and old_sig.get("kid") == m["signature"]["kid"]
            and "_note" not in old
            and verify_sig(alg, msg, b64u_dec(old_sig.get("sig", "")))
        )
        if reusable:
            m["signature"] = old_sig
            return m
    sig = sign(alg, msg)
    token = tsa_token(sha256_hex(sig))
    m["signature"]["ts"] = (base64.b64encode(token).decode() if token else
                            base64.b64encode(b"AILINEAGE-TS-PLACEHOLDER").decode())
    m["signature"]["sig"] = b64u(sig)
    order = ["alg", "kid", "ts", "sig", "chain"]
    m["signature"] = {k: m["signature"][k] for k in order if k in m["signature"]}
    if token is None:
        m = {"_note": PLACEHOLDER_NOTE, **m}
    print("  signed %s (%s)" % (path.name, "ts ok" if token else "ts PLACEHOLDER"))
    return m


def dump(m: dict) -> str:
    return json.dumps(m, indent=2, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------
# Test vectors
# ---------------------------------------------------------------------------

PROMPT_VECTORS = [
    ("ascii", "Draw a red circle on a white background."),
    ("czech-diacritics-nfd", unicodedata.normalize("NFD", "Příliš žluťoučký kůň úpěl ďábelské ódy")),
    ("emoji", "Make the icon friendlier \U0001F98A✨ and add a \U0001F468‍\U0001F4BB"),
    ("crlf", "Line one\r\nLine two\rLine three\r\n"),
    ("trailing-spaces", "  Indented first line   \nsecond line\t \n\n\n  "),
]

JCS_VECTOR = {
    "spec": "ailineage/0.1",
    "z": [3, 1.5, 1e21, 1e-7, -0.0, 100],
    "a": {"€": "euro", "\r": "cr", "\U0001F600": "emoji", "\ufb01": "fi-ligature (sorts after U+1F600 in UTF-16 order)",
          "1": "one"},
    "text": "Příliš\n\"quoted\"\t\u0001",
    "flag": True,
    "none": None,
}

MULTIMODAL_VECTOR = {
    "text": "  Describe this image\r\nin one sentence.  ",
    "attachments": ["urn:sha256:" + sha256_hex(b"<placeholder image bytes>")],
}

SALT_VECTOR = bytes(range(32))  # fixed salt for test vectors only (00 01 .. 1f)
SALTED_VECTORS = ["ascii", "czech-diacritics-nfd"]

PARAMS_VECTOR = {
    "params": {"steps": 4, "cfg": 1.0, "sampler_name": "euler", "client_id": "c0ffee-run-7",
               "queued_at": "2026-10-19T06:59:58Z"},
    "volatile": ["client_id", "queued_at"],
}


def compute_vectors() -> dict:
    v = {"prompt": [], "salted": [], "jcs": {}, "multimodal": {}, "multimodal_salted": {},
         "params": {}}
    for name, text in PROMPT_VECTORS:
        c = prompt_bytes_v1(text)
        v["prompt"].append({"name": name, "input": text,
                            "input_utf8_hex": text.encode("utf-8").hex(),
                            "canonical": c.decode("utf-8"), "hash": h(c)})
    for name, text in PROMPT_VECTORS:
        if name in SALTED_VECTORS:
            c = prompt_bytes_v1(text)
            v["salted"].append({"name": name, "input": text, "salt_hex": SALT_VECTOR.hex(),
                                "salt_b64url": b64u(SALT_VECTOR),
                                "hashed_bytes_hex": (SALT_VECTOR + c).hex(),
                                "hash": salted_commit(c, SALT_VECTOR)})
    c = jcs_bytes(JCS_VECTOR)
    v["jcs"] = {"input": JCS_VECTOR, "canonical": c.decode("utf-8"), "hash": h(c)}
    c = prompt_bytes_multimodal(MULTIMODAL_VECTOR["text"], MULTIMODAL_VECTOR["attachments"])
    v["multimodal"] = {"input": MULTIMODAL_VECTOR, "canonical": c.decode("utf-8"), "hash": h(c)}
    v["multimodal_salted"] = {"input": MULTIMODAL_VECTOR, "salt_hex": SALT_VECTOR.hex(),
                              "hash": salted_commit(c, SALT_VECTOR)}
    p = PARAMS_VECTOR
    kept = {k: x for k, x in p["params"].items() if k not in p["volatile"]}
    v["params"] = {"input": p, "canonical": jcs(kept),
                   "hash": params_hash(p["params"], p["volatile"])}
    return v


def md_code(s: str) -> str:
    return "```text\n" + s + "\n```"


def vectors_markdown(v: dict) -> str:
    out = ["### Prompt vectors (`utf8-nfc-trim-v1`)", ""]
    for p in v["prompt"]:
        out += ["#### `%s`" % p["name"], "",
                "Input (Python string literal, exact code points):", "",
                "```python", repr(p["input"]), "```", "",
                "Input UTF-8 bytes (hex):", "", md_code(p["input_utf8_hex"]), "",
                "Canonical form (Python string literal):", "",
                "```python", repr(p["canonical"]), "```", "",
                "SHA-256:", "", md_code(p["hash"]), ""]
    out += ["### Salted prompt vectors (`utf8-nfc-trim-salted-v1`)", "",
            "Same inputs as the vectors of the same name above. Salt (32 bytes, test only):", "",
            md_code(SALT_VECTOR.hex()), ""]
    for p in v["salted"]:
        out += ["#### `%s` (salted)" % p["name"], "",
                "Hashed bytes `salt || canonical` (hex):", "", md_code(p["hashed_bytes_hex"]), "",
                "SHA-256:", "", md_code(p["hash"]), ""]
    j = v["jcs"]
    out += ["### JCS vector", "", "Input (Python literal; `-0.0`, `1e21` and `1e-7` exercise "
            "number serialization):", "", "```python", repr(j["input"]), "```", "",
            "Canonical UTF-8 output:", "", md_code(j["canonical"]), "",
            "SHA-256:", "", md_code(j["hash"]), ""]
    mm = v["multimodal"]
    out += ["### Multimodal vector (`multimodal-v1`)", "", "Input:", "",
            "```python", repr(mm["input"]), "```", "", "Canonical form:", "",
            md_code(mm["canonical"]), "", "SHA-256:", "", md_code(mm["hash"]), "",
            "### Multimodal salted vector (`multimodal-salted-v1`)", "",
            "Same input and canonical form as above, same test salt. SHA-256:", "",
            md_code(v["multimodal_salted"]["hash"]), ""]
    pv = v["params"]
    out += ["### Params vector (`params_hash`)", "", "Input:", "",
            "```python", repr(pv["input"]), "```", "", "Canonical form:", "",
            md_code(pv["canonical"]), "", "SHA-256:", "", md_code(pv["hash"])]
    return "\n".join(out)


def replace_block(path: Path, name: str, content: str, write: bool) -> bool:
    """Replace text between generated markers. Return True if up to date."""
    text = path.read_text()
    begin = "<!-- BEGIN GENERATED: %s (fixtures/regen.py) -->" % name
    end = "<!-- END GENERATED: %s -->" % name
    pat = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.S)
    if not pat.search(text):
        raise SystemExit("%s: missing generated block %r" % (path, name))
    new = pat.sub(lambda _: begin + "\n\n" + content + "\n\n" + end, text)
    if write and new != text:
        path.write_text(new)
    return new == text


# ---------------------------------------------------------------------------
# Examples
# ---------------------------------------------------------------------------


def hexdump(b: bytes, base_off: int = 0) -> str:
    lines = []
    for i in range(0, len(b), 16):
        chunk = b[i:i + 16]
        hx = " ".join("%02x" % c for c in chunk)
        asc = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
        lines.append("%08x  %-47s  |%s|" % (base_off + i, hx, asc))
    return "\n".join(lines)


def build_examples(valid: dict, write: bool) -> list[str]:
    errs = []
    m01 = valid["01-image-created-comfyui.json"]
    emb = png_embed(D["image-64.png"], jcs_bytes(m01))
    if png_strip(emb) != D["image-64.png"]:
        errs.append("png-itxt: strip(embed(x)) != x")
    itxt = [(s, e) for s, e, t, d in png_chunks(emb) if png_is_ailineage_itxt(t, d)][0]
    dump_txt = (
        "# iTXt chunk 'ailineage' in examples/png-itxt/image-64.ailineage.png\n"
        "# generated by fixtures/regen.py; first 8 lines and last 2 lines of the chunk\n"
        "# layout: length(4) 'iTXt'(4) 'ailineage' 00 | comp_flag=00 comp_method=00 |\n"
        "#         lang='' 00 | translated='' 00 | UTF-8 JCS manifest | CRC(4)\n")
    seg = emb[itxt[0]:itxt[1]]
    lines = hexdump(seg, itxt[0]).split("\n")
    dump_txt += "\n".join(lines[:8] + ["..."] + lines[-2:]) + "\n"
    dump_txt += "\nartifact.id (PNG without the chunk): %s\n" % urn(png_strip(emb))
    m13, m14 = valid["13-image-jpeg-jumbf.json"], valid["14-image-webp-chunk.json"]
    jpg = jpeg_embed(D["image-64.jpg"], jcs_bytes(m13))
    if jpeg_strip(jpg) != D["image-64.jpg"] or urn(jpeg_strip(jpg)) != m13["artifact"]["id"]:
        errs.append("jpeg-jumbf: strip(embed(x)) != x")
    # multi-segment split: a 70 000-byte payload must round-trip too
    if jpeg_strip(jpeg_embed(D["image-64.jpg"], b"{" + b" " * 70000 + b"}")) != D["image-64.jpg"]:
        errs.append("jpeg-jumbf: multi-segment strip mismatch")
    s, e, _ = next(t for t in jpeg_segments(jpg) if t[2] == 0xEB)
    jdump = (
        "# APP11 segment in examples/jpeg-jumbf/image-64.ailineage.jpg\n"
        "# generated by fixtures/regen.py; first 4 lines and last 2 lines of the segment\n"
        "# layout: FF EB | Le(2) | CI='JP' | En(2) | Z(4)=1 |\n"
        "#         jumb: LBox(4) 'jumb' | jumd: LBox(4) 'jumd' UUID(16)=json toggles=03 'ailineage' 00 |\n"
        "#         json: LBox(4) 'json' UTF-8 JCS manifest\n")
    lines = hexdump(jpg[s:e], s).split("\n")
    jdump += "\n".join(lines[:4] + ["..."] + lines[-2:]) + "\n"
    jdump += "\nartifact.id (JPEG without the segment): %s\n" % urn(jpeg_strip(jpg))
    wbp = webp_embed(D["image-64.webp"], jcs_bytes(m14))
    if webp_strip(wbp) != D["image-64.ext.webp"] or urn(webp_strip(wbp)) != m14["artifact"]["id"]:
        errs.append("webp-chunk: strip(embed(x)) != extend(x)")
    wdump = (
        "# RIFF chunks in examples/webp-chunk/image-64.ailineage.webp\n"
        "# generated by fixtures/regen.py\n"
        "# offset  fourcc  size (bytes, without header and pad)\n")
    wdump += "riff    %s\n" % struct.unpack("<I", wbp[4:8])[0]
    for cs, ce, c in riff_chunks(wbp):
        wdump += "%06d  %s    %d\n" % (cs, c.decode(), struct.unpack("<I", wbp[cs + 4:cs + 8])[0])
    vs, ve, _ = next(t for t in riff_chunks(wbp) if t[2] == b"VP8X")
    wdump += "\nVP8X chunk:\n" + hexdump(wbp[vs:ve], vs) + "\n"
    wdump += "\nartifact.id (WebP without the AILN chunk, RIFF size rewritten): %s\n" % \
        urn(webp_strip(wbp))
    sidecar_go = b"// ailineage: " + urn(D["hello.go"]).encode() + b"\n" + D["hello.go"]
    if text_strip_header(sidecar_go) != D["hello.go"]:
        errs.append("sidecar: header strip mismatch")
    if write:
        (EXAMPLES / "png-itxt" / "image-64.ailineage.png").write_bytes(emb)
        (EXAMPLES / "png-itxt" / "hexdump.txt").write_text(dump_txt)
        for d, f, b, t in (("jpeg-jumbf", "image-64.ailineage.jpg", jpg, jdump),
                           ("webp-chunk", "image-64.ailineage.webp", wbp, wdump)):
            (EXAMPLES / d).mkdir(exist_ok=True)
            (EXAMPLES / d / f).write_bytes(b)
            (EXAMPLES / d / ("hexdump.txt" if d == "jpeg-jumbf" else "chunks.txt")).write_text(t)
        (EXAMPLES / "sidecar" / "hello.go").write_bytes(sidecar_go)
        (EXAMPLES / "sidecar" / "hello.go.lineage.json").write_text(
            dump(valid["03-code-created-claude-code-sidecar.json"]))
        notes = "\n".join(jcs(valid["07-chain-v%d.json" % i]) for i in (1, 2, 3)) + "\n"
        (EXAMPLES / "git-notes" / "note-payload.jsonl").write_text(notes)
    else:
        for rel, b in (("png-itxt/image-64.ailineage.png", emb),
                       ("png-itxt/hexdump.txt", dump_txt.encode()),
                       ("jpeg-jumbf/image-64.ailineage.jpg", jpg),
                       ("jpeg-jumbf/hexdump.txt", jdump.encode()),
                       ("webp-chunk/image-64.ailineage.webp", wbp),
                       ("webp-chunk/chunks.txt", wdump.encode()),
                       ("sidecar/hello.go", sidecar_go)):
            if (EXAMPLES / rel).read_bytes() != b:
                errs.append("examples/%s is stale; run make fixtures-regen" % rel)
        sc = json.loads((EXAMPLES / "sidecar" / "hello.go.lineage.json").read_text())
        if sc != valid["03-code-created-claude-code-sidecar.json"]:
            errs.append("examples/sidecar/hello.go.lineage.json is stale")
        if urn(text_strip_header((EXAMPLES / "sidecar" / "hello.go").read_bytes())) != \
                sc["artifact"]["id"]:
            errs.append("examples/sidecar: artifact.id mismatch after header strip")
    return errs


# ---------------------------------------------------------------------------
# Semantic checks (verifier rules JSON Schema cannot express)
# ---------------------------------------------------------------------------


def semantic_errors(m: dict) -> list[str]:
    errs = []
    aid = m.get("artifact", {}).get("id")
    ids = [p.get("id") for p in m.get("parents", [])]
    if aid in ids:
        errs.append("REQ-0072: parent id equals artifact.id")
    pairs = [(p.get("id"), p.get("relation")) for p in m.get("parents", [])]
    if len(pairs) != len(set(pairs)):
        errs.append("REQ-0075: duplicate (id, relation) in parents")
    if sum(1 for p in m.get("parents", []) if p.get("relation") == "previous_version") > 1:
        errs.append("REQ-0077: more than one previous_version parent")
    pr = m.get("prompt", {})
    if pr.get("storage") == "public" and "text" in pr:
        if pr.get("canonicalization") == "utf8-nfc-trim-v1" and \
                h(prompt_bytes_v1(pr["text"])) != pr.get("hash"):
            errs.append("REQ-0302: prompt.text does not match prompt.hash")
    return errs


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def readme_manifest(final: dict) -> str:
    """Fixture 11 with signature values shortened so the README fits a screen."""
    m = copy.deepcopy(final["11-minimal.json"])
    for k in ("ts", "sig"):
        v = m["signature"][k]
        m["signature"][k] = v[:12] + "…" + v[-6:]
    body = ",\n".join("  %s: %s" % (json.dumps(k), json.dumps(
        v, ensure_ascii=False, separators=(", ", ": "))) for k, v in m.items())
    return ("```json\n{\n" + body + "\n}\n```\n\n"
            "`ts` and `sig` are shortened here; the complete, verifiable file is "
            "[`fixtures/valid/11-minimal.json`](fixtures/valid/11-minimal.json).")


def cmd_regen(_args) -> int:
    ensure_keys()
    build_data(write=True)
    define_fixtures()
    VALID.mkdir(parents=True, exist_ok=True)
    INVALID.mkdir(parents=True, exist_ok=True)
    final = {}
    for name, (m, _data, _c) in FIXTURES.items():
        final[name] = finalize(m, VALID / name)
        (VALID / name).write_text(dump(final[name]))
    for name, m in invalid_fixtures(final).items():
        (INVALID / name).write_text(dump(m))
    OPENINGS_FILE.write_text(dump(build_openings(final)))
    INDEX_FILE.write_text(dump(build_index(final)))
    errs = build_examples(final, write=True)
    v = compute_vectors()
    VECTORS.mkdir(parents=True, exist_ok=True)
    (VECTORS / "canonicalization.json").write_text(dump(v))
    replace_block(ROOT / "CANONICALIZATION.md", "test-vectors", vectors_markdown(v), True)
    replace_block(ROOT / "README.md", "minimal-manifest", readme_manifest(final), True)
    for e in errs:
        print("ERROR", e, file=sys.stderr)
    print("regen: %d valid, %d invalid fixtures" % (len(final), len(invalid_fixtures(final))))
    return 1 if errs else 0


def data_for(name: str, container: str) -> bytes:
    b = (DATA / name).read_bytes()
    return {"png": png_strip, "jpeg": jpeg_strip,
            "webp": lambda x: webp_strip(webp_extend(x))}.get(container, lambda x: x)(b)


def cmd_check(_args) -> int:
    build_data(write=False)
    define_fixtures()
    fails, warns = [], []
    final = {}
    for name, (_m, data, container) in FIXTURES.items():
        path = VALID / name
        m = json.loads(path.read_text())
        final[name] = m
        got = urn(data_for(data, container))
        if m["artifact"]["id"] != got:
            fails.append("%s: HASH_MISMATCH artifact.id (data/%s = %s)" % (name, data, got))
        if "size_bytes" in m["artifact"] and m["artifact"]["size_bytes"] != len(
                data_for(data, container)):
            fails.append("%s: size_bytes mismatch" % name)
        for e in semantic_errors(m):
            fails.append("%s: %s" % (name, e))
        sig = m["signature"]
        if not verify_sig(sig["alg"], signing_input(m), b64u_dec(sig["sig"])):
            fails.append("%s: SIG_INVALID" % name)
        if sig["kid"] != did_key(sig["alg"]):
            fails.append("%s: KEY_UNTRUSTED (kid is not the test key)" % name)
        if m.get("_note") == PLACEHOLDER_NOTE:
            warns.append("%s: ts is placeholder (not verified)" % name)
        else:
            ok, when = ts_verify(base64.b64decode(sig["ts"]),
                                 sha256_hex(b64u_dec(sig["sig"])))
            if not ok:
                fails.append("%s: TS_INVALID" % name)
            else:
                print("  ok %-44s ts %s" % (name, when))
    # chain: previous_version parents must share media_type (REQ-0402)
    by_id = {m["artifact"]["id"]: m for m in final.values()}
    for name, m in final.items():
        for p in m["parents"]:
            pm = by_id.get(p["id"])
            if p["relation"] == "previous_version" and pm and \
                    pm["artifact"]["media_type"] != m["artifact"]["media_type"]:
                fails.append("%s: REQ-0402 previous_version media_type differs" % name)
    fails += build_examples(final, write=False)
    openings = json.loads(OPENINGS_FILE.read_text())
    if openings != build_openings(final):
        fails.append("data/openings.json is stale; run make fixtures-regen")
    if json.loads(INDEX_FILE.read_text()) != build_index(final):
        fails.append("fixtures/index.json is stale; run make fixtures-regen")
    fails += opening_errors(final, openings)
    for s in sorted(SEMANTIC_INVALID):
        if not semantic_errors(json.loads((INVALID / s).read_text())):
            fails.append("invalid/%s: expected a semantic violation" % s)
    for w in warns:
        print("WARN", w)
    for f in fails:
        print("FAIL", f, file=sys.stderr)
    print("check: %d fixtures, %d failures, %d warnings" % (len(final), len(fails), len(warns)))
    return 1 if fails else 0


def cmd_semantic(args) -> int:
    bad = 0
    for f in args.files:
        errs = semantic_errors(json.loads(Path(f).read_text()))
        for e in errs:
            print("%s: %s" % (f, e))
        bad += bool(errs)
    return 1 if bad else 0


def cmd_test_vectors(_args) -> int:
    v = compute_vectors()
    ok = True
    stored = json.loads((VECTORS / "canonicalization.json").read_text())
    if stored != v:
        print("FAIL fixtures/vectors/canonicalization.json differs from computed vectors")
        ok = False
    if not replace_block(ROOT / "CANONICALIZATION.md", "test-vectors", vectors_markdown(v),
                         False):
        print("FAIL CANONICALIZATION.md test vectors are stale; run make fixtures-regen")
        ok = False
    doc = (ROOT / "CANONICALIZATION.md").read_text()
    hashes = [p["hash"] for p in v["prompt"]] + [p["hash"] for p in v["salted"]] + [
        v["jcs"]["hash"], v["multimodal"]["hash"], v["multimodal_salted"]["hash"],
        v["params"]["hash"]]
    for x in hashes:
        if x not in doc:
            print("FAIL hash %s not found in CANONICALIZATION.md" % x)
            ok = False
    # independent sanity checks of the algorithms themselves
    assert canon_text("a \r\nb\t\r\n") == "a\nb"
    assert canon_text("é") == "é"
    assert salted_commit(b"", bytes(32)) == h(bytes(32))
    assert jcs({"b": 1, "a": [True, None]}) == '{"a":[true,null],"b":1}'
    assert _es_number(1e21) == "1e+21" and _es_number(1e-7) == "1e-7"
    assert _es_number(0.000001) == "0.000001" and _es_number(123.456) == "123.456"
    assert _es_number(-0.0) == "0" and _es_number(1.0) == "1"
    print("test-vectors: %d hashes %s" % (len(hashes), "ok" if ok else "FAILED"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("regen").set_defaults(fn=cmd_regen)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    s = sub.add_parser("semantic")
    s.add_argument("files", nargs="+")
    s.set_defaults(fn=cmd_semantic)
    sub.add_parser("test-vectors").set_defaults(fn=cmd_test_vectors)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
