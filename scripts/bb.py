#!/usr/bin/env python3
"""Python 3 port of airpyrt's basebinary parse/extract.

Keys are read at runtime from the airpyrt-tools checkout (src/airpyrt-tools),
not embedded here.
"""
import argparse, pathlib, re, struct, sys, zlib
from Crypto.Cipher import AES

ROOT = pathlib.Path(__file__).resolve().parent.parent
MAGIC = b"APPLE-FIRMWARE\x00"
HDR = struct.Struct(">15sB2I4BI")

def load_keys():
    src = (ROOT / "third_party/airpyrt-tools/acp/basebinary.py").read_text()
    table = re.search(r"_basebinary_keys\s*=\s*\{(.*?)\}", src, re.S).group(1)
    return {int(m): bytes.fromhex(k) for m, k in re.findall(r'^\s*(\d+)\s*:\s*"([0-9a-f]+)"', table, re.M)}

def derive_key(model):
    key = load_keys().get(model)
    if key is None:
        sys.exit(f"no key for model {model}")
    return bytes(b ^ (i + 0x19) for i, b in enumerate(key))

def decrypt_chunk(data, key, iv):
    c = AES.new(key, AES.MODE_CBC, iv)
    n = len(data) & ~0xF
    return c.decrypt(data[:n]) + data[n:]

def decrypt(data, model, b0f):
    iv = MAGIC + bytes([b0f])
    key = derive_key(model)
    return b"".join(decrypt_chunk(data[i:i + 0x8000], key, iv) for i in range(0, len(data), 0x8000))

def parse(data, verbose=True):
    magic, b0f, model, version, b18, b19, b1a, flags, unk = HDR.unpack(data[:HDR.size])
    if magic != MAGIC:
        sys.exit("bad magic")
    stored, = struct.unpack(">I", data[-4:])
    inner = data[HDR.size:-4]
    if verbose:
        print(f"model={model} version={version:#x} b0f={b0f:#x} b18/19/1a={b18:#x}/{b19:#x}/{b1a:#x} flags={flags:#x} unk={unk:#x} inner_len={len(inner):#x}")
    if flags & 2:
        inner = decrypt(inner, model, b0f)
    calc = zlib.adler32(data[:HDR.size] + inner) & 0xFFFFFFFF
    if verbose:
        print(f"adler32 stored={stored:#x} calc={calc:#x} {'OK' if stored == calc else 'MISMATCH'}")
    if stored != calc:
        sys.exit("checksum mismatch")
    return inner

def extract(data):
    off = data.index(b"\x1f\x8b\x08")
    print(f"gzip at {off:#x}")
    return zlib.decompress(data[off:], 16 + zlib.MAX_WBITS)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["parse", "extract", "info"])
    ap.add_argument("inp"); ap.add_argument("out", nargs="?")
    a = ap.parse_args()
    data = pathlib.Path(a.inp).read_bytes()
    if a.cmd == "info":
        parse(data); return
    out = parse(data) if a.cmd == "parse" else extract(data)
    pathlib.Path(a.out).write_bytes(out)
    print(f"wrote {a.out} ({len(out):#x} bytes)")

if __name__ == "__main__":
    main()
