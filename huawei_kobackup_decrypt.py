#!/usr/bin/env python3
"""Huawei KoBackup v4 (BOPD) backup decryptor.

Supports both known v4 variants:
  - KoBackup 12.x (backupVersion 29):  file key = PBKDF2-SHA256(bkey, seed, 5000),  AES-256-CTR
  - KoBackup 14.x+ (HarmonyOS 4, backupVersion 31): file key = PBKDF2-SHA256(bkey, seed, 10000),
    AES-256-GCM with the 16-byte tag appended at the end of each file

Algorithm:
  1. K     = PBKDF2-HMAC-SHA256(password, pwkey_salt[:16], 10000, 32)
  2. bkey  = AES-256-GCM(K, nonce=pwkey_salt[16:]).decrypt(e_perbackupkey[:32])
             (e_perbackupkey[32:] is the GCM tag -> verifies the password)
  3. per module, encMsgV3 (48 bytes) = seed(32) || nonce/iv(16):
       file_key = PBKDF2-HMAC-SHA256(bkey.encode('utf-8'), seed, iters, 32)
     both variants are tried automatically; the right one is selected via a
     plaintext oracle on the first 4 KB and, for GCM, confirmed by the tag.
  4. checkMsgV3 (optional --verify): parts "hmac64hex_seed64hex" joined by '_';
       hmac_key = hex(PBKDF2(bkey, seed, 5000)) as UTF-8 bytes
       hmac     = HMAC-SHA256(hmac_key, stored_file_bytes)

Usage:
  python huawei_kobackup_decrypt.py <backup_dir> <output_dir> <password> [options]
  backup_dir = device folder containing backupFiles1/ (or the session folder itself)
Options:
  -x, --extract   extract decrypted .tar archives into <output>/extracted/
      --verify    verify checkMsgV3 HMACs (reads all module files again)
      --apk       also copy the (unencrypted) .apk files
  -v, --verbose   print every file
"""

import argparse
import binascii
import hashlib
import hmac as hmac_mod
import os
import sys
import tarfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    from Crypto.Cipher import AES
    from Crypto.Hash import HMAC, SHA256
    from Crypto.Protocol.KDF import PBKDF2
    from Crypto.Util import Counter
except ImportError:
    print("ERROR: pycryptodome is required:  pip install pycryptodome")
    sys.exit(1)

BKEY_ITERS = 10000
GCM_TAG = 16
CHUNK = 8 * 1024 * 1024
MODULE_MEDIA_DIRS = {
    "photo": ("photo", "pictures"),
    "video": ("video", "movies"),
    "audio": ("audio", "audios"),
}


def prf(p, s):
    return HMAC.new(p, s, SHA256).digest()


# ---------------------------------------------------------------------------
# info.xml parsing
# ---------------------------------------------------------------------------

def parse_info_xml(xml_path):
    """Return (modules, e_perbackupkey_hex, pwkey_salt_hex).
    modules: name -> dict(encMsgV3=..., checkMsgV3=...)"""
    root = ET.parse(xml_path).getroot()
    modules = {}
    e_pbk = pwkey = None

    for row in root.iter("row"):
        table = row.get("table", "")
        cols = {}
        for col in row.findall("column"):
            val = col.find("value")
            if val is None:
                continue
            for attr in ("String", "Integer", "Long", "Boolean"):
                v = val.get(attr)
                if v is not None:
                    cols[col.get("name", "")] = v
                    break
        if table == "BackupFilesTypeInfo":
            e_pbk = cols.get("e_perbackupkey")
            pwkey = cols.get("pwkey_salt")
        elif table in ("BackupFileModuleInfo", "BackupFileModuleInfo_Media",
                       "BackupFileModuleInfo_SystemData"):
            name = cols.get("name")
            if name:
                modules[name] = {
                    "encMsgV3": (cols.get("encMsgV3") or "").strip(),
                    "checkMsgV3": (cols.get("checkMsgV3") or "").strip(),
                }
    return modules, e_pbk, pwkey


def find_session_dir(backup_dir):
    p = Path(backup_dir)
    if (p / "info.xml").is_file():
        return p
    base = None
    for cand in ("backupFiles1", "backupFiles"):
        if (p / cand).is_dir():
            base = p / cand
            break
    if base is None:
        raise SystemExit(f"ERROR: no backupFiles1/ or info.xml under {p}")
    sessions = sorted((d for d in base.iterdir() if d.is_dir()),
                      key=lambda d: d.stat().st_mtime, reverse=True)
    if not sessions:
        raise SystemExit(f"ERROR: no session folder in {base}")
    if len(sessions) > 1:
        print(f"NOTE: multiple sessions, using newest: {sessions[0].name}")
    return sessions[0]


# ---------------------------------------------------------------------------
# key derivation
# ---------------------------------------------------------------------------

def derive_bkey(password, e_pbk_hex, pwkey_salt_hex):
    """Return bkey as UTF-8 hex string. Raises ValueError on wrong password."""
    pwkey = binascii.unhexlify(pwkey_salt_hex.strip())
    epbk = binascii.unhexlify(e_pbk_hex.strip())
    K = PBKDF2(password.encode("utf-8"), pwkey[:16], 32, BKEY_ITERS, prf)
    cipher = AES.new(K, AES.MODE_GCM, nonce=pwkey[16:])
    bkey = cipher.decrypt(epbk[:32])
    cipher.verify(epbk[32:])
    return bkey.decode("utf-8")


def module_candidates(bkey_str, encmsgv3_hex):
    """All plausible (mode, iters, key, nonce) tuples, best guesses first."""
    em = binascii.unhexlify(encmsgv3_hex.strip())
    seed, nonce = em[:32], em[32:]
    cands = []
    for iters, mode in ((10000, "gcm"), (5000, "ctr"), (10000, "ctr"), (5000, "gcm")):
        key = PBKDF2(bkey_str.encode("utf-8"), seed, 32, iters, prf)
        cands.append((mode, iters, key, nonce))
    return cands


# ---------------------------------------------------------------------------
# plaintext oracle
# ---------------------------------------------------------------------------

MAGICS = (
    (b"SQLite format 3\x00", 0),
    (b"PK\x03\x04", 0),
    (b"\x1f\x8b", 0),
    (b"\x89PNG", 0),
    (b"\xff\xd8\xff", 0),
    (b"ftyp", 4),
    (b"OggS", 0),
    (b"ID3", 0),
    (b"RIFF", 0),
)


def plaintext_score(buf):
    if not buf:
        return 0
    for magic, off in MAGICS:
        if buf[off:off + len(magic)] == magic:
            return 100
    if len(buf) > 262 and buf[257:262] == b"ustar":
        return 100
    n = len(buf)
    zeros = buf.count(0)
    if zeros / n > 0.25:
        return 70
    printable = sum(1 for b in buf if 32 <= b < 127 or b in (9, 10, 13))
    if printable / n > 0.85:
        return 50
    return 0


def prefix_score(src_path, mode, key, nonce):
    try:
        with open(src_path, "rb") as f:
            head = f.read(4096)
    except OSError:
        return 0
    if mode == "gcm":
        if len(head) <= GCM_TAG:
            return 0
        pt = AES.new(key, AES.MODE_GCM, nonce=nonce).decrypt(head)
    else:
        ctr = Counter.new(128, initial_value=int.from_bytes(nonce, "big"),
                          little_endian=False)
        pt = AES.new(key, AES.MODE_CTR, counter=ctr).decrypt(head)
    return plaintext_score(pt)


# ---------------------------------------------------------------------------
# streaming decryption
# ---------------------------------------------------------------------------

def stream_decrypt(src_path, dst_path, mode, key, nonce):
    """Decrypt src -> dst. Returns (ok, message)."""
    with open(src_path, "rb") as fi, open(dst_path, "wb") as fo:
        if mode == "gcm":
            remaining = os.path.getsize(src_path) - GCM_TAG
            if remaining < 0:
                return False, "file shorter than a GCM tag"
            cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
            while remaining > 0:
                buf = fi.read(min(CHUNK, remaining))
                if not buf:
                    return False, "short read"
                fo.write(cipher.decrypt(buf))
                remaining -= len(buf)
            tag = fi.read(GCM_TAG)
            try:
                cipher.verify(tag)
            except ValueError:
                return False, "GCM tag invalid"
            return True, "AES-256-GCM (tag verified)"
        ctr = Counter.new(128, initial_value=int.from_bytes(nonce, "big"),
                          little_endian=False)
        cipher = AES.new(key, AES.MODE_CTR, counter=ctr)
        while True:
            buf = fi.read(CHUNK)
            if not buf:
                break
            fo.write(cipher.decrypt(buf))
        return True, "AES-256-CTR"


def decrypt_module_file(src, dst, bkey_str, encmsgv3_hex, cache, verbose=False):
    tmp = dst.with_suffix(dst.suffix + ".part")
    order = module_candidates(bkey_str, encmsgv3_hex)
    if cache.get("cand") is not None:
        order = [cache["cand"]] + [c for c in order if c != cache["cand"]]
    ranked = sorted(order, key=lambda c: -prefix_score(src, c[0], c[2], c[3]))
    last_msg = "no candidate produced plausible plaintext"
    for mode, iters, key, nonce in ranked:
        score = prefix_score(src, mode, key, nonce)
        if mode == "ctr" and score < 50:
            continue
        ok, msg = stream_decrypt(src, tmp, mode, key, nonce)
        if ok:
            os.replace(tmp, dst)
            cache["cand"] = (mode, iters, key, nonce)
            return True, f"{msg} (iters={iters})"
        last_msg = msg
        if verbose:
            print(f"    retry after {msg}")
    if tmp.exists():
        tmp.unlink()
    return False, last_msg


# ---------------------------------------------------------------------------
# checkMsgV3 verification
# ---------------------------------------------------------------------------

def verify_checkmsg(path, bkey_str, checkmsgv3):
    if not checkmsgv3:
        return None
    for part in checkmsgv3.split("_"):
        try:
            b = binascii.unhexlify(part.strip())
            expected, seed = b[:32], b[32:]
            key_hex = binascii.hexlify(
                PBKDF2(bkey_str.encode("utf-8"), seed, 32, 5000, prf))
            mac = hmac_mod.new(key_hex, digestmod=hashlib.sha256)
            with open(path, "rb") as f:
                while True:
                    buf = f.read(CHUNK)
                    if not buf:
                        break
                    mac.update(buf)
            if mac.digest() == expected:
                return True
        except (ValueError, binascii.Error):
            continue
    return False


# ---------------------------------------------------------------------------
# tar extraction
# ---------------------------------------------------------------------------

def extract_tar(tar_path, dest):
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    with tarfile.open(tar_path, "r:") as tf:
        for m in tf:
            tf.extract(m, dest, filter="data")
            count += 1
            if count % 5000 == 0:
                print(f"    extracted {count} entries ...")
    return count


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Huawei KoBackup v4 decryptor (12.x CTR and 14.x+ GCM variants)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    ap.add_argument("backup_dir")
    ap.add_argument("output_dir")
    ap.add_argument("password")
    ap.add_argument("-x", "--extract", action="store_true",
                    help="extract decrypted .tar archives")
    ap.add_argument("--verify", action="store_true",
                    help="verify checkMsgV3 HMACs")
    ap.add_argument("--apk", action="store_true",
                    help="copy unencrypted .apk files too")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    backup_dir = Path(args.backup_dir)
    out_dir = Path(args.output_dir)
    session = find_session_dir(backup_dir)
    media_root = None
    for parent in [backup_dir] + list(Path(backup_dir).parents):
        if (parent / "media").is_dir() and parent.name != "media":
            media_root = parent / "media"
            break

    print(f"Backup  : {backup_dir}")
    print(f"Session : {session.name}")
    print(f"Output  : {out_dir}")
    print()

    modules, e_pbk, pwkey = parse_info_xml(session / "info.xml")
    if not e_pbk or not pwkey:
        raise SystemExit("ERROR: e_perbackupkey / pwkey_salt missing in info.xml "
                         "(backup is probably not password-encrypted v4)")
    print(f"Modules : {', '.join(modules)}")

    t0 = time.time()
    try:
        bkey_str = derive_bkey(args.password, e_pbk, pwkey)
    except ValueError:
        raise SystemExit("ERROR: password check failed (GCM tag on e_perbackupkey)")
    print(f"Password OK  (bkey = {bkey_str})")
    print()

    (out_dir / "databases").mkdir(parents=True, exist_ok=True)
    meta = out_dir / "_meta"
    meta.mkdir(exist_ok=True)
    for small in ("info.xml", "appInfo.db", "appInfo.db-journal"):
        s = session / small
        if s.is_file():
            (meta / small).write_bytes(s.read_bytes())

    ok_count = err_count = 0
    failures = []

    for mod_name, mod in modules.items():
        if not mod["encMsgV3"]:
            continue
        cache = {}

        files = []
        for ext in (".tar", ".db", ".zip"):
            p = session / (mod_name + ext)
            if p.is_file():
                files.append(p)
        sub = session / mod_name
        if sub.is_dir():
            files.extend(f for f in sub.rglob("*") if f.is_file())

        if media_root is not None:
            msession = media_root / session.name
            for folder in MODULE_MEDIA_DIRS.get(mod_name, (mod_name,)):
                mdir = msession / folder
                if mdir.is_dir():
                    files.extend(f for f in mdir.rglob("*") if f.is_file())

        if not files:
            continue
        print(f"[{mod_name}]  {len(files)} file(s)")
        for i, src in enumerate(files):
            rel = src.relative_to(session)
            dst = out_dir / "databases" / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if os.path.getsize(src) == 0:
                dst.write_bytes(b"")
                ok_count += 1
                continue
            ok, msg = decrypt_module_file(src, dst, bkey_str, mod["encMsgV3"],
                                          cache, args.verbose)
            if ok:
                ok_count += 1
                if args.verbose or i < 3 or (i + 1) % 20 == 0:
                    print(f"  {i+1}/{len(files)}  {rel}  [{msg}]")
                if args.verify:
                    v = verify_checkmsg(src, bkey_str, mod["checkMsgV3"])
                    if v is False:
                        print(f"    WARNING: checkMsgV3 mismatch for {rel}")
                    elif v and args.verbose:
                        print(f"    checkMsgV3: OK")
                if args.extract and src.suffix == ".tar":
                    dest = out_dir / "extracted" / src.stem
                    print(f"    extracting {src.name} -> {dest}")
                    n = extract_tar(dst, dest)
                    print(f"    extracted {n} entries")
            else:
                err_count += 1
                failures.append((str(rel), msg))
                print(f"  FAILED {rel}: {msg}")

    if args.apk:
        for apk in session.glob("*.apk"):
            dst = out_dir / "app" / apk.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            print(f"copying {apk.name}")
            with open(apk, "rb") as fi, open(dst, "wb") as fo:
                while True:
                    buf = fi.read(CHUNK)
                    if not buf:
                        break
                    fo.write(buf)
            ok_count += 1

    print()
    print(f"Done in {time.time()-t0:.0f}s: {ok_count} ok, {err_count} failed")
    if failures:
        print("Failures:")
        for name, msg in failures:
            print(f"  {name}: {msg}")
    print(f"Output: {out_dir}")


if __name__ == "__main__":
    main()
