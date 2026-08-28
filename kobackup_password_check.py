#!/usr/bin/env python3
"""Standalone password checker / brute-force helper for Huawei KoBackup v4 backups.

Uses the GCM tag on e_perbackupkey as a fast oracle: one PBKDF2 (10000 iters)
per candidate, no file I/O. Works even when the tar files are missing — only
info.xml is needed.

Usage:
  # check one or more explicit passwords
  python kobackup_password_check.py <backup_dir> -p pwd1 pwd2 ...

  # generate candidates from a date-shaped hint and try them all
  python kobackup_password_check.py <backup_dir> --dates 1970:2027 --suffix Amy

  # check a plain wordlist file (one password per line)
  python kobackup_password_check.py <backup_dir> -w wordlist.txt
"""

import argparse
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    from Crypto.Cipher import AES
    from Crypto.Hash import HMAC, SHA256
    from Crypto.Protocol.KDF import PBKDF2
except ImportError:
    print("ERROR: pycryptodome is required:  pip install pycryptodome")
    sys.exit(1)

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
ORDINALS = {1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth",
            6: "Sixth", 7: "Seventh", 8: "Eighth", 9: "Ninth", 10: "Tenth",
            11: "Eleventh", 12: "Twelfth", 13: "Thirteenth", 14: "Fourteenth",
            15: "Fifteenth", 16: "Sixteenth", 17: "Seventeenth",
            18: "Eighteenth", 19: "Nineteenth", 20: "Twentieth",
            21: "TwentyFirst", 22: "TwentySecond", 23: "TwentyThird",
            24: "TwentyFourth", 25: "TwentyFifth", 26: "TwentySixth",
            27: "TwentySeventh", 28: "TwentyEighth", 29: "TwentyNinth",
            30: "Thirtieth", 31: "ThirtyFirst"}


def prf(p, s):
    return HMAC.new(p, s, SHA256).digest()


def load_oracle(backup_dir):
    p = Path(backup_dir)
    if (p / "info.xml").is_file():
        info = p / "info.xml"
    else:
        infos = sorted((p / "backupFiles1").glob("*/info.xml"))
        if not infos:
            raise SystemExit(f"ERROR: no info.xml under {p}")
        info = infos[-1]
    root = ET.parse(info).getroot()
    e_pbk = pwkey = None
    for row in root.iter("row"):
        if row.get("table") != "BackupFilesTypeInfo":
            continue
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
        e_pbk = cols.get("e_perbackupkey")
        pwkey = cols.get("pwkey_salt")
    if not e_pbk or not pwkey:
        raise SystemExit("ERROR: not an encrypted v4 backup (no e_perbackupkey)")
    import binascii
    return binascii.unhexlify(pwkey), binascii.unhexlify(e_pbk)


def check(pw_bytes, pwkey, epbk):
    K = PBKDF2(pw_bytes, pwkey[:16], 32, 10000, prf)
    c = AES.new(K, AES.MODE_GCM, nonce=pwkey[16:])
    c.decrypt(epbk[:32])
    try:
        c.verify(epbk[32:])
        return True
    except ValueError:
        return False


def date_candidates(year_lo, year_hi, suffix="", prefix=""):
    seen = set()
    for y in range(year_lo, year_hi + 1):
        y2 = str(y)[2:]
        for mi, mon in enumerate(MONTHS, 1):
            for d in range(1, 32):
                d2 = f"{d:02d}"
                m2 = f"{mi:02d}"
                ordn = ORDINALS.get(d, "")
                for tpl in (f"{y}{m2}{d2}", f"{d2}{m2}{y}", f"{y}{d2}{m2}",
                            f"{y}-{m2}-{d2}", f"{y}{mon}{d}", f"{d}{mon}{y}",
                            f"{mon}{d}{y}", f"{mon}{d}", f"{d}{mon}",
                            f"{mon}{ordn}", f"{mon}{ordn}{y}"):
                    c = prefix + tpl + suffix
                    if c not in seen:
                        seen.add(c)
                        yield c
    # bare years / months too
    for y in range(year_lo, year_hi + 1):
        for tpl in (str(y), str(y)[2:]):
            c = prefix + tpl + suffix
            if c not in seen:
                seen.add(c)
                yield c


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("backup_dir")
    ap.add_argument("-p", "--password", nargs="+", default=[],
                    help="explicit passwords to check")
    ap.add_argument("-w", "--wordlist", help="file with one password per line")
    ap.add_argument("--dates", metavar="YEAR:YEAR",
                    help="generate date-shaped candidates, e.g. 1970:2027")
    ap.add_argument("--suffix", default="", help="append to every date candidate")
    ap.add_argument("--prefix", default="", help="prepend to every date candidate")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    pwkey, epbk = load_oracle(args.backup_dir)
    print(f"Loaded oracle from backup (salt={pwkey[:8].hex()}...)")

    def run(cands):
        n = t0 = None
        t0 = time.time()
        n = 0
        for pw in cands:
            n += 1
            if check(pw.encode("utf-8"), pwkey, epbk):
                print(f"\nFOUND PASSWORD: {pw!r}")
                return True
            if n % 500 == 0:
                rate = n / max(time.time() - t0, 1e-6)
                print(f"  tried {n} ({rate:.0f}/s)", flush=True)
        print(f"no match in {n} candidates ({time.time()-t0:.0f}s)")
        return False

    if args.password:
        for pw in args.password:
            ok = check(pw.encode("utf-8"), pwkey, epbk)
            print(f"{'OK  ' if ok else 'FAIL'}  {pw!r}")
            if ok:
                return
    if args.wordlist:
        with open(args.wordlist, encoding="utf-8", errors="replace") as f:
            if run(line.rstrip("\r\n") for line in f):
                return
    if args.dates:
        lo, _, hi = args.dates.partition(":")
        if run(date_candidates(int(lo), int(hi or lo), args.suffix, args.prefix)):
            return


if __name__ == "__main__":
    main()
