# Huawei KoBackup v4 Backup Decryptor

[English](README.md) | [中文版](README_CN.md)

---

A Python-based decryptor for password-protected **Huawei KoBackup v4
backups** created by Huawei phones and tablets running EMUI / HarmonyOS.

This project supports both:

-   **KoBackup 12.x / `backupVersion = 29`** --- AES-256-CTR +
    PBKDF2-SHA256 × 5000
-   **KoBackup 14.x / `backupVersion = 31`** --- AES-256-GCM +
    PBKDF2-SHA256 × 10000

The newer KoBackup 14.x format is especially important because older
KoBackup decryption tools generally assume the 12.x CTR parameters and
therefore fail on newer HarmonyOS backups.

The decryptor automatically detects the applicable file-encryption
variant and uses GCM authentication when available.

------------------------------------------------------------------------

## Features

-   Decrypt password-protected **KoBackup v4** backups.
-   Supports both the older **AES-256-CTR** and newer **AES-256-GCM**
    file formats.
-   Automatically tries the known PBKDF2 / cipher combinations.
-   Uses the **GCM authentication tag** in `e_perbackupkey` as a strong
    password oracle.
-   Uses plaintext signatures to identify the correct file-encryption
    variant.
-   Streams files in **8 MiB chunks**, avoiding the need to load large
    backup files entirely into RAM.
-   Optionally verifies `checkMsgV3` HMAC integrity metadata.
-   Optionally extracts decrypted TAR archives automatically.
-   Optionally copies unencrypted APK files.
-   Includes a separate password-checking utility that only needs
    `info.xml`.
-   Can generate date-shaped password candidates for backups whose
    passwords follow a predictable date-based pattern.

------------------------------------------------------------------------

## Supported Formats

| Format     | KoBackup | Example Password KDF  | File KDF              | File Cipher |
| ---------- | -------- | --------------------- | --------------------- | ----------- |
| Legacy v4  | 12.x     | PBKDF2-SHA256 × 10000 | PBKDF2-SHA256 × 5000  | AES-256-CTR |
| Current v4 | 14.7.x   | PBKDF2-SHA256 × 10000 | PBKDF2-SHA256 × 10000 | AES-256-GCM |


### A known KoBackup 14.7 example

The newer format has been verified against:

-   Device: **HUAWEI MatePad Pro (MRO-W10)**
-   HarmonyOS: **4.2.0**
-   KoBackup: **14.7.0.280**
-   `backupVersion`: **31**
-   File encryption: **AES-256-GCM**
-   File-key PBKDF2: **10000 iterations**
-   GCM authentication tag: **16 bytes appended to each encrypted file**

For comparison, KoBackup 12.0-era backups tested with this project use:

-   KoBackup: **12.0.0.360**
-   `backupVersion`: **29**
-   File encryption: **AES-256-CTR**
-   File-key PBKDF2: **5000 iterations**

------------------------------------------------------------------------

## Important: KoBackup 14.x Changed the File Encryption

A major source of compatibility problems is that the newer KoBackup format changed **two parameters** compared with KoBackup 12:

| Parameter       | KoBackup 12 / older backup | KoBackup 14.7 / `backupVersion = 31`         |
| --------------- | -------------------------- | -------------------------------------------- |
| File-key PBKDF2 | PBKDF2-SHA256 × **5000**   | PBKDF2-SHA256 × **10000**                    |
| File encryption | **AES-256-CTR**            | **AES-256-GCM**                              |
| GCM tag         | N/A                        | **16 bytes appended to the end of the file** |


Therefore, simply changing the PBKDF2 iteration count while keeping
AES-CTR is **not sufficient** for KoBackup 14.x.

The complete KoBackup 14.7 algorithm described below has been
experimentally verified, including successful GCM tag authentication.

------------------------------------------------------------------------

# Repository Contents

``` text
.
├── huawei_kobackup_decrypt.py
├── kobackup_password_check.py
└── README.md
```

### `huawei_kobackup_decrypt.py`

The main decryptor.

It:

1.  Locates the backup session.
2.  Reads `info.xml`.
3.  Derives and authenticates the backup key.
4.  Derives module/file keys.
5.  Detects the correct encryption variant.
6.  Decrypts backup files.
7.  Optionally verifies `checkMsgV3`.
8.  Optionally extracts TAR archives.
9.  Optionally copies unencrypted APK files.

### `kobackup_password_check.py`

A standalone password checker / password-recovery helper.

It uses the authenticated encryption metadata in `info.xml` to test
passwords without decrypting the backup files themselves.

This means it can work even if the large `.tar` files are missing, as
long as the relevant `info.xml` is available.

------------------------------------------------------------------------

# Requirements

## Python

Python 3.8+ is recommended.

## Dependency

Install PyCryptodome:

``` bash
pip install pycryptodome
```

If your operating system uses a Python environment with externally
managed packages, create a virtual environment instead:

``` bash
python -m venv .venv
```

### Windows

``` powershell
.venv\Scripts\activate
pip install pycryptodome
```

### Linux / macOS

``` bash
source .venv/bin/activate
pip install pycryptodome
```

------------------------------------------------------------------------

# Backup Directory Structure

A typical Huawei backup may look approximately like this:

``` text
HuaweiBackup/
├── backupFiles1/
│   └── <session>/
│       ├── info.xml
│       ├── appInfo.db
│       ├── <module>.tar
│       ├── <module>.db
│       ├── <module>.zip
│       └── ...
└── media/
    └── <session>/
        ├── photo/
        ├── video/
        └── audio/
```

The main decryptor accepts either:

1.  The **backup root**, containing `backupFiles1/`; or
2.  The **session directory itself**, containing `info.xml`.

For example:

``` text
D:\Huawei\Backup\HUAWEI MatePad Pro__xxxx
```

or directly:

``` text
D:\Huawei\Backup\HUAWEI MatePad Pro__xxxx\backupFiles1\<session>
```

If the backup root contains multiple sessions, the script selects the
newest session by modification time and prints a notice.

------------------------------------------------------------------------

# Basic Usage

``` bash
python huawei_kobackup_decrypt.py <backup_dir> <output_dir> <password>
```

Example:

``` bash
python huawei_kobackup_decrypt.py \
    "D:\Huawei\Backup\HUAWEI MatePad Pro__xxx__yyy" \
    "D:\Huawei\Decrypted" \
    "your-password"
```

On Linux/macOS:

``` bash
python huawei_kobackup_decrypt.py \
    "/path/to/HuaweiBackup" \
    "/path/to/output" \
    "your-password"
```

------------------------------------------------------------------------

# Command-Line Options

``` text
-x, --extract
```

Extract decrypted TAR archives into:

``` text
<output>/extracted/
```

``` text
--verify
```

Verify the `checkMsgV3` HMAC metadata for successfully decrypted files.

This requires reading the encrypted source file again, so it increases
I/O and processing time.

``` text
--apk
```

Copy unencrypted `.apk` files from the backup session into:

``` text
<output>/app/
```

``` text
-v, --verbose
```

Print more detailed per-file information and retry information.

------------------------------------------------------------------------

# Recommended Usage

For most backups:

``` bash
python huawei_kobackup_decrypt.py \
    "D:\Huawei\Backup\HUAWEI MatePad Pro__xxx__yyy" \
    "D:\Huawei\Decrypted" \
    "your-password" \
    -x --verify --apk -v
```

If you only want decrypted files and do not need TAR extraction:

``` bash
python huawei_kobackup_decrypt.py \
    "D:\Huawei\Backup\HUAWEI MatePad Pro__xxx__yyy" \
    "D:\Huawei\Decrypted" \
    "your-password"
```

------------------------------------------------------------------------

# Output Structure

A typical output directory is:

``` text
Decrypted/
├── databases/
│   ├── <module>.tar
│   ├── <module>.db
│   ├── <module>.zip
│   └── ...
├── extracted/
│   └── <tar-name>/
│       └── ...
├── app/
│   └── *.apk
└── _meta/
    ├── info.xml
    ├── appInfo.db
    └── appInfo.db-journal
```

The exact module names depend on the backup.

### `databases/`

Contains the decrypted versions of encrypted backup files.

Despite the historical directory name, this may contain TAR, ZIP,
database, and other module files.

### `extracted/`

Only created/populated when `-x` / `--extract` is specified.

### `app/`

Only populated when `--apk` is specified.

### `_meta/`

Contains small backup metadata files copied without modification.

------------------------------------------------------------------------

# Extracting Minecraft Bedrock Worlds

One useful application of this tool is recovering Minecraft Bedrock
Edition worlds from an encrypted Huawei backup.

When the Minecraft module is successfully decrypted and extracted, the
world data commonly appears under a path similar to:

``` text
games/
└── com.mojang/
    └── minecraftWorlds/
        └── <world-id>/
```

For example:

``` text
extracted/
└── com.mojang.minecraftpe/
    └── games/
        └── com.mojang/
            └── minecraftWorlds/
                ├── <world-id-1>/
                └── <world-id-2>/
```

A Minecraft world directory normally contains files such as:

``` text
level.dat
levelname.txt
db/
```

The exact directory structure depends on the Minecraft version and
backup format.

If your objective is specifically to recover Minecraft worlds, using:

``` bash
python huawei_kobackup_decrypt.py <backup> <output> <password> -x
```

is generally the easiest approach.

------------------------------------------------------------------------

# Password Verification

The password is not stored directly in plaintext.

For KoBackup v4, `info.xml` contains encrypted key material including:

-   `e_perbackupkey`
-   `pwkey_salt`

The authentication tag on `e_perbackupkey` provides a reliable way to
determine whether a candidate password is correct.

The separate checker can test one or more explicit passwords:

``` bash
python kobackup_password_check.py <backup_dir> \
    -p "123456" "August11" "11111111Aaa"
```

Example output:

``` text
FAIL  '123456'
FAIL  'August11'
OK    '11111111Aaa'
```

Only `info.xml` is required for this check.

------------------------------------------------------------------------

# Wordlist Checking

To test a wordlist:

``` bash
python kobackup_password_check.py <backup_dir> -w wordlist.txt
```

The wordlist should contain one candidate password per line.

For example:

``` text
123456
password
Huawei123
August11
11111111Aaa
```

The checker uses the GCM authentication tag rather than decrypting every
backup file, making this much faster than attempting a full backup
decryption for every candidate.

Only use password-recovery functionality on backups you are authorized
to access.

------------------------------------------------------------------------

# Date-Shaped Password Candidates

If the password follows a predictable date-based pattern, the checker
can generate candidates automatically.

Example:

``` bash
python kobackup_password_check.py \
    <backup_dir> \
    --dates 1970:2027 \
    --suffix Aaa
```

You can also add a prefix:

``` bash
python kobackup_password_check.py \
    <backup_dir> \
    --dates 1970:2027 \
    --prefix Huawei \
    --suffix Aaa
```

The generator covers several common forms, including:

``` text
YYYYMMDD
DDMMYYYY
YYYYDDMM
YYYY-MM-DD

YYYYMonthD
DMonthYYYY
MonthDYYYY

MonthD
DMonth
MonthOrdinal
MonthOrdinalYYYY

YYYY
YY
```

For example, candidates can include patterns similar to:

``` text
20091130
30112009
20093011
2009-11-30
2009November30
30November2009
November302009
November30
30November
NovemberThirtieth
NovemberThirtieth2009
2009
09
```

The supplied suffix/prefix is added to each generated candidate.

------------------------------------------------------------------------

# How the Key Derivation Works

The encryption format consists of several stages.

The most important distinction is between:

1.  The password-derived key used to decrypt the per-backup key.
2.  The module/file key derived from that backup key.
3.  The cipher used to decrypt each stored file.

------------------------------------------------------------------------

## Step 1 --- Derive the Backup Key

The following values come from `info.xml`:

``` text
pwkey_salt
e_perbackupkey
```

For the current KoBackup 14.x format:

``` text
K = PBKDF2-HMAC-SHA256(
        password,
        pwkey_salt[:16],
        10000,
        32 bytes
    )
```

Then:

``` text
bkey = AES-256-GCM(
           key = K,
           nonce = pwkey_salt[16:]
       ).decrypt(
           e_perbackupkey[:32]
       )
```

The remaining bytes are the GCM authentication tag:

``` text
tag = e_perbackupkey[32:]
```

The tag must verify successfully.

If verification fails, the password is incorrect.

The resulting `bkey` is a 32-byte ASCII hexadecimal string.

------------------------------------------------------------------------

# Step 2 --- Derive the File / Module Key

Each module has an `encMsgV3` value in `info.xml`.

For the known format:

``` text
encMsgV3 = seed || nonce/IV
```

with:

``` text
seed       = encMsgV3[:32]
nonce / IV = encMsgV3[32:]
```

The file key is derived as:

``` text
file_key = PBKDF2-HMAC-SHA256(
               bkey.encode("utf-8"),
               seed,
               iterations,
               32 bytes
           )
```

The iteration count depends on the KoBackup generation:

``` text
KoBackup 12.x:
    iterations = 5000

KoBackup 14.x:
    iterations = 10000
```

------------------------------------------------------------------------

# Step 3A --- KoBackup 14.x File Decryption

For `backupVersion = 31` / KoBackup 14.7, the encrypted file uses:

``` text
AES-256-GCM
```

The GCM nonce is:

``` text
nonce = encMsgV3[32:]
```

The encrypted file layout is:

``` text
ciphertext || 16-byte GCM tag
```

Therefore:

``` text
ciphertext = encrypted_file[:-16]
tag        = encrypted_file[-16:]
```

Decryption is conceptually:

``` text
plaintext =
    AES-256-GCM(
        key=file_key,
        nonce=encMsgV3[32:]
    ).decrypt(ciphertext)
```

followed by:

``` text
verify(tag)
```

The GCM tag is not optional. Successful authentication confirms that the
derived key and encryption parameters are correct.

------------------------------------------------------------------------

# Step 3B --- KoBackup 12.x File Decryption

The older tested format uses:

``` text
AES-256-CTR
```

The counter starts from the big-endian integer represented by:

``` text
encMsgV3[32:]
```

Conceptually:

``` text
counter = int.from_bytes(encMsgV3[32:], "big")
```

and:

``` text
plaintext =
    AES-256-CTR(
        key=file_key,
        initial_counter=counter
    ).decrypt(encrypted_file)
```

Unlike GCM, CTR does not provide an authentication tag.

For this reason, the decryptor uses plaintext signatures to determine
whether a candidate CTR key produced plausible data.

------------------------------------------------------------------------

# Automatic Variant Detection

The main decryptor knows several combinations:

``` text
PBKDF2 × 10000 + AES-GCM
PBKDF2 × 5000  + AES-CTR
PBKDF2 × 10000 + AES-CTR
PBKDF2 × 5000  + AES-GCM
```

The expected combinations are prioritized first:

``` text
10000 + GCM
5000  + CTR
```

The remaining combinations are retained as compatibility fallbacks.

For each candidate, the script examines the beginning of the decrypted
data and checks for common file signatures.

Known signatures include:

``` text
SQLite:
    SQLite format 3\x00

ZIP:
    PK\x03\x04

GZIP:
    \x1f\x8b

PNG:
    \x89PNG

JPEG:
    \xff\xd8\xff

MP4 / ISO Base Media:
    ftyp

Ogg:
    OggS

MP3:
    ID3

RIFF:
    RIFF

TAR:
    ustar
```

For GCM, a successful tag verification is the authoritative
confirmation.

For CTR, the plaintext score is used to avoid writing obviously invalid
output.

------------------------------------------------------------------------

# `checkMsgV3` Integrity Verification

Some modules contain `checkMsgV3` metadata.

The format can contain multiple entries:

``` text
<hmac-hex><seed-hex>_<hmac-hex><seed-hex>_...
```

For each entry, the verifier derives:

``` text
derived =
    PBKDF2-HMAC-SHA256(
        bkey.encode("utf-8"),
        seed,
        5000,
        32 bytes
    )
```

The derived bytes are converted to hexadecimal ASCII:

``` text
hmac_key = hex(derived).encode("utf-8")
```

Then:

``` text
HMAC-SHA256(
    key=hmac_key,
    message=encrypted_file_bytes
)
```

is compared with the stored HMAC.

This is why `--verify` reads the encrypted source files again.

GCM authentication already protects the newer file format, but
`checkMsgV3` is useful as an additional consistency check and for
compatibility with metadata generated by older formats.

------------------------------------------------------------------------

# Why Older Decryptors May Fail

Older projects commonly assume something like:

``` text
file key:
    PBKDF2-SHA256 × 5000

file cipher:
    AES-256-CTR
```

That works for the tested KoBackup 12 / `backupVersion = 29` format.

It does not correctly describe the tested KoBackup 14.7 /
`backupVersion = 31` format.

For KoBackup 14.7:

``` text
file key:
    PBKDF2-SHA256 × 10000

file cipher:
    AES-256-GCM

authentication:
    16-byte tag appended to the encrypted file
```

Therefore, a tool can successfully derive `bkey` and still fail to
decrypt the actual backup files if it continues using the old CTR
parameters.

------------------------------------------------------------------------

# Streaming and Large Files

The decryptor processes files in chunks of:

``` text
8 MiB
```

This is important for large media files and TAR archives.

The basic workflow is:

``` text
encrypted file
      |
      v
read 8 MiB
      |
      v
decrypt
      |
      v
write plaintext
      |
      v
repeat
```

For GCM, the final 16 bytes are held back and used as the authentication
tag.

Temporary output is written using a `.part` suffix. The final
destination is replaced only after successful decryption.

This prevents an invalid GCM decryption from being presented as a valid
completed file.

------------------------------------------------------------------------

# Media Files

Huawei backups can store media outside the normal
`backupFiles1/<session>/` tree.

The decryptor searches for a `media/` directory associated with the
backup root and handles known media module directories.

Known mappings include:

``` text
photo -> photo / pictures
video -> video / movies
audio -> audio / audios
```

Therefore, for media recovery, keep the original backup directory
structure intact.

Do not move only `backupFiles1/` somewhere else if the corresponding
`media/` directory is required.

------------------------------------------------------------------------

# Limitations

## Backup Version

This project is intended for:

``` text
KoBackup v4
```

identified by the presence of encrypted per-backup key material such as:

``` text
e_perbackupkey
pwkey_salt
```

It does **not** claim compatibility with older HiSuite / KoBackup backup
generations that use different key-storage and encryption schemes.

Older v1/v2/v3 formats may require tools specifically designed for those
formats.

## Password Requirement

The main decryptor still requires the correct password.

The password checker can test candidates, but it cannot magically
recover an arbitrary strong password.

## Media Layout

Media recovery depends on the original `media/` directory being
available in the expected location.

## CTR Authentication

AES-CTR itself does not authenticate ciphertext.

For legacy CTR files, the decryptor relies on plaintext signatures and
other structural checks rather than a cryptographic authentication tag.

------------------------------------------------------------------------

# Troubleshooting

## `password check failed`

Example:

``` text
ERROR: password check failed (GCM tag on e_perbackupkey)
```

This normally means one of:

-   The password is wrong.
-   The backup is not the expected password-protected KoBackup v4
    format.
-   `info.xml` is damaged.
-   The backup was modified or is incomplete.

First verify the password with:

``` bash
python kobackup_password_check.py <backup_dir> -p "your-password"
```

------------------------------------------------------------------------

## `no backupFiles1/ or info.xml`

The path supplied to the program is not a recognized backup root or
session directory.

Make sure the directory contains either:

``` text
info.xml
```

or:

``` text
backupFiles1/
```

------------------------------------------------------------------------

## `no session folder`

The supplied backup root contains `backupFiles1/`, but no session
directory was found.

Check that the backup was copied completely.

------------------------------------------------------------------------

## Files are `FAILED`

For a newer KoBackup 14.x backup, verify that:

-   `info.xml` belongs to the same backup.
-   The encrypted files were copied without modification.
-   The backup is complete.
-   You are using the correct password.
-   The files are actually associated with the module described by
    `encMsgV3`.

Run with:

``` bash
-v
```

to see candidate retries and failure details.

------------------------------------------------------------------------

## Decryption succeeds but extracted data looks invalid

If using a legacy CTR backup, an incorrect candidate can occasionally
produce data that looks partially plausible.

Try:

``` bash
--verify
```

where `checkMsgV3` is available.

For KoBackup 14.x, GCM tag verification provides a much stronger
authenticity check.

------------------------------------------------------------------------

# Security Notes

This project is intended for recovering and analyzing backups that you
are authorized to access.

The backup password is processed locally by the scripts. No network
service is required by the decryption code.

The decrypted output may contain highly sensitive information,
including:

-   Application databases
-   Authentication/session data
-   Messages
-   Photos and videos
-   Minecraft worlds
-   Other application-private data

Treat the decrypted output with the same care as the original device.

Do not upload decrypted backup contents to untrusted services.

------------------------------------------------------------------------

# Example End-to-End Workflow

## 1. Install the dependency

``` bash
python -m pip install pycryptodome
```

## 2. Check the password

``` bash
python kobackup_password_check.py \
    "D:\Huawei\Backup\HUAWEI MatePad Pro__xxx__yyy" \
    -p "your-password"
```

Expected:

``` text
OK    'your-password'
```

## 3. Decrypt and extract

``` bash
python huawei_kobackup_decrypt.py \
    "D:\Huawei\Backup\HUAWEI MatePad Pro__xxx__yyy" \
    "D:\Huawei\Decrypted" \
    "your-password" \
    -x
```

## 4. Optionally verify integrity and copy APKs

``` bash
python huawei_kobackup_decrypt.py \
    "D:\Huawei\Backup\HUAWEI MatePad Pro__xxx__yyy" \
    "D:\Huawei\Decrypted" \
    "your-password" \
    -x --verify --apk
```

------------------------------------------------------------------------

# Technical Summary

For the verified KoBackup 14.7 / `backupVersion = 31` format:

``` text
password
   |
   | PBKDF2-HMAC-SHA256
   | salt = pwkey_salt[:16]
   | iterations = 10000
   | dkLen = 32
   v
K
   |
   | AES-256-GCM
   | nonce = pwkey_salt[16:]
   | ciphertext = e_perbackupkey[:32]
   | tag = e_perbackupkey[32:]
   v
bkey
   |
   | UTF-8 encode
   |
   | PBKDF2-HMAC-SHA256
   | salt = encMsgV3[:32]
   | iterations = 10000
   | dkLen = 32
   v
file_key
   |
   | AES-256-GCM
   | nonce = encMsgV3[32:]
   |
   | encrypted file = ciphertext || 16-byte tag
   v
plaintext
```

For KoBackup 12 / `backupVersion = 29`, the second KDF changes to 5000
iterations and the file cipher changes to AES-256-CTR.

------------------------------------------------------------------------

# Compatibility Matrix

| Component                       | KoBackup 12 / v29 | KoBackup 14.7 / v31 |
| ------------------------------- | ----------------- | ------------------- |
| Password KDF                    | PBKDF2-SHA256     | PBKDF2-SHA256       |
| Password KDF iterations         | 10000             | 10000               |
| Password KDF output             | 32 bytes          | 32 bytes            |
| `e_perbackupkey` authentication | GCM tag           | GCM tag             |
| File-key KDF                    | PBKDF2-SHA256     | PBKDF2-SHA256       |
| File-key iterations             | **5000**          | **10000**           |
| File cipher                     | **AES-256-CTR**   | **AES-256-GCM**     |
| File tag                        | None              | **16 bytes**        |
| Streaming decryption            | Yes               | Yes                 |
| `checkMsgV3` verification       | Yes               | Yes                 |
| TAR extraction                  | Yes               | Yes                 |
| APK copying                     | Yes               | Yes                 |


# Credits and Background

Thanks to project mauronofrio/Huawei-Backup-V4-Decrypt for the base of this project. This project is based on reverse-engineering and practical verification
of Huawei KoBackup v4 backup metadata and encryption behavior.

The project was made by Zhipu GLM-5.3.

The KoBackup 14.7 algorithm documented here is not merely inferred from
an older implementation: the following properties have been verified
experimentally:

-   `PBKDF2-SHA256 × 10000` for the password-derived key.
-   AES-256-GCM authentication of `e_perbackupkey`.
-   Recovery of a valid 32-byte ASCII hexadecimal `bkey`.
-   `PBKDF2-SHA256 × 10000` for the KoBackup 14.x file key.
-   AES-256-GCM for file encryption.
-   A 16-byte authentication tag appended to the encrypted file.
-   Successful GCM tag verification on the resulting plaintext.

