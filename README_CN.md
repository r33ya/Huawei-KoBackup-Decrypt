# 华为 KoBackup v4 备份解密工具

[English](README.md) | [中文版](README_CN.md)

---

一个基于 Python 的解密器，用于解密华为手机和平板（EMUI / HarmonyOS）
创建的**受密码保护的 KoBackup v4 备份**。

本项目同时支持：

-   **KoBackup 12.x / `backupVersion = 29`** —— AES-256-CTR +
    PBKDF2-SHA256 × 5000
-   **KoBackup 14.x / `backupVersion = 31`** —— AES-256-GCM +
    PBKDF2-SHA256 × 10000

较新的 KoBackup 14.x 格式尤为重要，因为旧版 KoBackup 解密工具通常
假设使用 12.x 的 CTR 参数，因此在较新的 HarmonyOS 备份上会解密失败。

本解密器会自动检测适用的文件加密变体，并在可用时使用 GCM 认证。

------------------------------------------------------------------------

## 功能特性

-   解密受密码保护的 **KoBackup v4** 备份。
-   同时支持较旧的 **AES-256-CTR** 和较新的 **AES-256-GCM**
    文件格式。
-   自动尝试已知的 PBKDF2 / 加密组合。
-   利用 `e_perbackupkey` 中的 **GCM 认证标签**作为强密码校验预言机。
-   利用明文特征识别正确的文件加密变体。
-   以 **8 MiB 分块**流式处理文件，无需将大型备份文件整体载入内存。
-   可选校验 `checkMsgV3` HMAC 完整性元数据。
-   可选自动解压已解密的 TAR 归档。
-   可选复制未加密的 APK 文件。
-   附带独立的密码校验工具，只需要 `info.xml` 即可运行。
-   可针对密码符合可预测日期格式的备份，自动生成日期形态的密码候选。

------------------------------------------------------------------------

## 支持的格式

  ---------------------------------------------------------------------------------------
  格式        KoBackup               示例              密码 KDF         文件 KDF        文件加密
                            `backupVersion`                                  
  ----------- ----------- ----------------- --------------- --------------- -------------
  旧版 v4     12.x                       29 PBKDF2-SHA256 × PBKDF2-SHA256 × AES-256-CTR
                                            10000           5000            

  现行 v4     14.7.x                     31 PBKDF2-SHA256 × PBKDF2-SHA256 × AES-256-GCM
                                            10000           10000           
  ---------------------------------------------------------------------------------------

### 已验证的 KoBackup 14.7 实例

较新的格式已在以下环境验证通过：

-   设备：**HUAWEI MatePad Pro (MRO-W10)**
-   HarmonyOS：**4.2.0**
-   KoBackup：**14.7.0.280**
-   `backupVersion`：**31**
-   文件加密：**AES-256-GCM**
-   文件密钥 PBKDF2：**10000 次迭代**
-   GCM 认证标签：**16 字节，附加在每个加密文件末尾**

作为对比，用本项目测试过的 KoBackup 12.0 时代备份使用：

-   KoBackup：**12.0.0.360**
-   `backupVersion`：**29**
-   文件加密：**AES-256-CTR**
-   文件密钥 PBKDF2：**5000 次迭代**

------------------------------------------------------------------------

## 重要说明：KoBackup 14.x 更改了文件加密方式

兼容性问题的一个主要来源是：较新的 KoBackup 格式相比 KoBackup 12
更改了**两个参数**：

  -----------------------------------------------------------------------
  参数                     KoBackup 12 / 旧备份    KoBackup 14.7 /
                                                  `backupVersion = 31`
  ----------------------- ----------------------- -----------------------
  文件密钥 PBKDF2          PBKDF2-SHA256 ×         PBKDF2-SHA256 ×
                           **5000**                **10000**

  文件加密                 **AES-256-CTR**         **AES-256-GCM**

  GCM 标签                 无                      **16 字节，附加在文件
                                                   末尾**
  -----------------------------------------------------------------------

因此，仅更改 PBKDF2 迭代次数而继续使用 AES-CTR，对 KoBackup 14.x
来说**是不够的**。

下文描述的完整 KoBackup 14.7 算法已经过实验验证，包括成功的 GCM
标签认证。

------------------------------------------------------------------------

# 仓库内容

``` text
.
├── huawei_kobackup_decrypt.py
├── kobackup_password_check.py
└── README.md
```

### `huawei_kobackup_decrypt.py`

主解密器。

它的工作流程：

1.  定位备份会话目录。
2.  读取 `info.xml`。
3.  派生并认证备份密钥。
4.  派生模块/文件密钥。
5.  检测正确的加密变体。
6.  解密备份文件。
7.  可选校验 `checkMsgV3`。
8.  可选解压 TAR 归档。
9.  可选复制未加密的 APK 文件。

### `kobackup_password_check.py`

独立的密码校验 / 密码找回辅助工具。

它利用 `info.xml` 中的认证加密元数据来测试密码，而无需解密备份文件
本身。

这意味着即使大型 `.tar` 文件缺失，只要相关的 `info.xml` 可用，它
依然可以工作。

------------------------------------------------------------------------

# 环境要求

## Python

建议使用 Python 3.8+。

## 依赖

安装 PyCryptodome：

``` bash
pip install pycryptodome
```

如果你的操作系统使用外部管理包的 Python 环境，请改为创建虚拟环境：

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

# 备份目录结构

一个典型的华为备份大致如下：

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

主解密器接受以下两者之一：

1.  包含 `backupFiles1/` 的**备份根目录**；或
2.  包含 `info.xml` 的**会话目录本身**。

例如：

``` text
D:\Huawei\Backup\HUAWEI MatePad Pro__xxxx
```

或直接使用：

``` text
D:\Huawei\Backup\HUAWEI MatePad Pro__xxxx\backupFiles1\<session>
```

如果备份根目录包含多个会话，脚本会按修改时间选择最新的会话并打印
提示。

------------------------------------------------------------------------

# 基本用法

``` bash
python huawei_kobackup_decrypt.py <backup_dir> <output_dir> <password>
```

示例：

``` bash
python huawei_kobackup_decrypt.py \
    "D:\Huawei\Backup\HUAWEI MatePad Pro__xxx__yyy" \
    "D:\Huawei\Decrypted" \
    "your-password"
```

在 Linux/macOS 上：

``` bash
python huawei_kobackup_decrypt.py \
    "/path/to/HuaweiBackup" \
    "/path/to/output" \
    "your-password"
```

------------------------------------------------------------------------

# 命令行选项

``` text
-x, --extract
```

将解密后的 TAR 归档解压到：

``` text
<output>/extracted/
```

``` text
--verify
```

对成功解密的文件校验 `checkMsgV3` HMAC 元数据。

这需要再次读取加密的源文件，因此会增加 I/O 和处理时间。

``` text
--apk
```

将备份会话中未加密的 `.apk` 文件复制到：

``` text
<output>/app/
```

``` text
-v, --verbose
```

打印更详细的逐文件信息和重试信息。

------------------------------------------------------------------------

# 推荐用法

对大多数备份：

``` bash
python huawei_kobackup_decrypt.py \
    "D:\Huawei\Backup\HUAWEI MatePad Pro__xxx__yyy" \
    "D:\Huawei\Decrypted" \
    "your-password" \
    -x --verify --apk -v
```

如果只需要解密后的文件，不需要解压 TAR：

``` bash
python huawei_kobackup_decrypt.py \
    "D:\Huawei\Backup\HUAWEI MatePad Pro__xxx__yyy" \
    "D:\Huawei\Decrypted" \
    "your-password"
```

------------------------------------------------------------------------

# 输出结构

典型的输出目录如下：

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

具体的模块名称取决于备份本身。

### `databases/`

存放解密后的备份文件。

尽管目录沿用了历史名称，其中可能包含 TAR、ZIP、数据库以及其他模块
文件。

### `extracted/`

仅在使用 `-x` / `--extract` 时创建/填充。

### `app/`

仅在使用 `--apk` 时填充。

### `_meta/`

存放原样复制的小型备份元数据文件。

------------------------------------------------------------------------

# 提取 Minecraft 基岩版世界

本工具的一个实用场景是从加密的华为备份中恢复 Minecraft 基岩版世界。

当 Minecraft 模块被成功解密并解压后，世界数据通常出现在类似如下的
路径下：

``` text
games/
└── com.mojang/
    └── minecraftWorlds/
        └── <world-id>/
```

例如：

``` text
extracted/
└── com.mojang.minecraftpe/
    └── games/
        └── com.mojang/
            └── minecraftWorlds/
                ├── <world-id-1>/
                └── <world-id-2>/
```

一个 Minecraft 世界目录通常包含如下文件：

``` text
level.dat
levelname.txt
db/
```

确切的目录结构取决于 Minecraft 版本和备份格式。

如果你的目标就是恢复 Minecraft 世界，使用：

``` bash
python huawei_kobackup_decrypt.py <backup> <output> <password> -x
```

通常是最简单的做法。

------------------------------------------------------------------------

# 密码校验

密码并非以明文形式直接存储。

对于 KoBackup v4，`info.xml` 中包含加密的密钥材料，其中有：

-   `e_perbackupkey`
-   `pwkey_salt`

`e_perbackupkey` 上的认证标签提供了一种可靠的方式来判断候选密码
是否正确。

独立校验工具可以测试一个或多个显式给出的密码：

``` bash
python kobackup_password_check.py <backup_dir> \
    -p "123456" "August11" "11111111Aaa"
```

示例输出：

``` text
FAIL  '123456'
FAIL  'August11'
OK    '11111111Aaa'
```

此校验只需要 `info.xml`。

------------------------------------------------------------------------

# 字典检查

测试一个字典文件：

``` bash
python kobackup_password_check.py <backup_dir> -w wordlist.txt
```

字典文件中每行一个候选密码。

例如：

``` text
123456
password
Huawei123
August11
11111111Aaa
```

校验器使用 GCM 认证标签而非解密整个备份文件，这比为每个候选密码
尝试完整解密备份要快得多。

请只对你有权访问的备份使用密码找回功能。

------------------------------------------------------------------------

# 日期形态的密码候选

如果密码符合可预测的日期模式，校验器可以自动生成候选。

示例：

``` bash
python kobackup_password_check.py \
    <backup_dir> \
    --dates 1970:2027 \
    --suffix Aaa
```

也可以添加前缀：

``` bash
python kobackup_password_check.py \
    <backup_dir> \
    --dates 1970:2027 \
    --prefix Huawei \
    --suffix Aaa
```

生成器覆盖多种常见形式，包括：

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

例如，候选可以包括类似如下的模式：

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

指定的后缀/前缀会附加到每个生成的候选上。

------------------------------------------------------------------------

# 密钥派生的工作原理

加密格式由若干阶段组成。

最重要的区分是：

1.  用于解密"每备份密钥"的、由密码派生的密钥。
2.  由该备份密钥派生的模块/文件密钥。
3.  用于解密每个存储文件的加密算法。

------------------------------------------------------------------------

## 第 1 步 —— 派生备份密钥

以下数值来自 `info.xml`：

``` text
pwkey_salt
e_perbackupkey
```

对于现行的 KoBackup 14.x 格式：

``` text
K = PBKDF2-HMAC-SHA256(
        password,
        pwkey_salt[:16],
        10000,
        32 bytes
    )
```

然后：

``` text
bkey = AES-256-GCM(
           key = K,
           nonce = pwkey_salt[16:]
       ).decrypt(
           e_perbackupkey[:32]
       )
```

剩余的字节是 GCM 认证标签：

``` text
tag = e_perbackupkey[32:]
```

标签必须验证成功。

如果验证失败，则密码错误。

得到的 `bkey` 是一个 32 字节的 ASCII 十六进制字符串。

------------------------------------------------------------------------

# 第 2 步 —— 派生文件 / 模块密钥

每个模块在 `info.xml` 中有一个 `encMsgV3` 值。

对于已知格式：

``` text
encMsgV3 = seed || nonce/IV
```

其中：

``` text
seed       = encMsgV3[:32]
nonce / IV = encMsgV3[32:]
```

文件密钥的派生方式：

``` text
file_key = PBKDF2-HMAC-SHA256(
               bkey.encode("utf-8"),
               seed,
               iterations,
               32 bytes
           )
```

迭代次数取决于 KoBackup 的世代：

``` text
KoBackup 12.x:
    iterations = 5000

KoBackup 14.x:
    iterations = 10000
```

------------------------------------------------------------------------

# 第 3A 步 —— KoBackup 14.x 的文件解密

对于 `backupVersion = 31` / KoBackup 14.7，加密文件使用：

``` text
AES-256-GCM
```

GCM nonce 为：

``` text
nonce = encMsgV3[32:]
```

加密文件的布局为：

``` text
ciphertext || 16-byte GCM tag
```

因此：

``` text
ciphertext = encrypted_file[:-16]
tag        = encrypted_file[-16:]
```

解密在概念上是：

``` text
plaintext =
    AES-256-GCM(
        key=file_key,
        nonce=encMsgV3[32:]
    ).decrypt(ciphertext)
```

随后：

``` text
verify(tag)
```

GCM 标签不是可选项。认证成功即可确认派生的密钥和加密参数正确。

------------------------------------------------------------------------

# 第 3B 步 —— KoBackup 12.x 的文件解密

较旧的已测试格式使用：

``` text
AES-256-CTR
```

计数器的起始值是以下字节按大端序表示的整数：

``` text
encMsgV3[32:]
```

概念上：

``` text
counter = int.from_bytes(encMsgV3[32:], "big")
```

并且：

``` text
plaintext =
    AES-256-CTR(
        key=file_key,
        initial_counter=counter
    ).decrypt(encrypted_file)
```

与 GCM 不同，CTR 不提供认证标签。

因此，解密器使用明文特征来判断候选 CTR 密钥是否产生了合理的
数据。

------------------------------------------------------------------------

# 自动变体检测

主解密器已知若干组合：

``` text
PBKDF2 × 10000 + AES-GCM
PBKDF2 × 5000  + AES-CTR
PBKDF2 × 10000 + AES-CTR
PBKDF2 × 5000  + AES-GCM
```

预期的组合优先尝试：

``` text
10000 + GCM
5000  + CTR
```

其余组合保留作为兼容性回退。

对每个候选，脚本会检查解密数据的开头并匹配常见的文件特征。

已知的特征包括：

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

对于 GCM，标签验证成功即是权威的确认。

对于 CTR，使用明文评分来避免写出明显无效的输出。

------------------------------------------------------------------------

# `checkMsgV3` 完整性校验

某些模块包含 `checkMsgV3` 元数据。

其格式可以包含多个条目：

``` text
<hmac-hex><seed-hex>_<hmac-hex><seed-hex>_...
```

对每个条目，校验器派生：

``` text
derived =
    PBKDF2-HMAC-SHA256(
        bkey.encode("utf-8"),
        seed,
        5000,
        32 bytes
    )
```

派生的字节随后转换为十六进制 ASCII：

``` text
hmac_key = hex(derived).encode("utf-8")
```

然后：

``` text
HMAC-SHA256(
    key=hmac_key,
    message=encrypted_file_bytes
)
```

与存储的 HMAC 进行比较。

这就是 `--verify` 需要再次读取加密源文件的原因。

GCM 认证已经保护了较新的文件格式，但 `checkMsgV3`
作为额外的一致性检查仍然有用，同时也可兼容旧格式生成的元数据。

------------------------------------------------------------------------

# 为什么旧解密器可能失败

旧项目通常假设：

``` text
file key:
    PBKDF2-SHA256 × 5000

file cipher:
    AES-256-CTR
```

这对已测试的 KoBackup 12 / `backupVersion = 29` 格式有效。

但不能正确描述已测试的 KoBackup 14.7 / `backupVersion = 31` 格式。

对于 KoBackup 14.7：

``` text
file key:
    PBKDF2-SHA256 × 10000

file cipher:
    AES-256-GCM

authentication:
    16-byte tag appended to the encrypted file
```

因此，一个工具即使成功派生出了 `bkey`，如果继续沿用旧的 CTR
参数，仍然会无法解密实际的备份文件。

------------------------------------------------------------------------

# 流式处理与大文件

解密器以如下大小的分块处理文件：

``` text
8 MiB
```

这对大型媒体文件和 TAR 归档非常重要。

基本工作流程：

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

对于 GCM，最后的 16 字节会被预留出来用作认证标签。

临时输出使用 `.part` 后缀写入。只有在解密成功后才替换为最终
目标文件。

这样可以避免把无效的 GCM 解密结果当作有效的完整文件呈现。

------------------------------------------------------------------------

# 媒体文件

华为备份可能会把媒体文件存储在常规的
`backupFiles1/<session>/` 目录树之外。

解密器会搜索与备份根目录关联的 `media/` 目录，并处理已知的媒体
模块目录。

已知映射包括：

``` text
photo -> photo / pictures
video -> video / movies
audio -> audio / audios
```

因此，要恢复媒体文件，请保持原始备份目录结构完整。

如果需要对应的 `media/` 目录，请勿只把 `backupFiles1/`
单独移动到别处。

------------------------------------------------------------------------

# 局限性

## 备份版本

本项目面向：

``` text
KoBackup v4
```

其识别标志是存在加密的每备份密钥材料，例如：

``` text
e_perbackupkey
pwkey_salt
```

它**不**声称兼容使用不同密钥存储和加密方案的旧版 HiSuite /
KoBackup 备份世代。

旧版 v1/v2/v3 格式可能需要专门为这些格式设计的工具。

## 密码要求

主解密器仍然需要正确的密码。

密码校验器可以测试候选，但无法凭空恢复任意强密码。

## 媒体目录布局

媒体恢复依赖原始 `media/` 目录位于预期的位置。

## CTR 认证

AES-CTR 本身不认证密文。

对于旧版 CTR 文件，解密器依赖明文特征和其他结构性检查，而非
密码学认证标签。

------------------------------------------------------------------------

# 故障排查

## `password check failed`

示例：

``` text
ERROR: password check failed (GCM tag on e_perbackupkey)
```

这通常意味着以下之一：

-   密码错误。
-   备份不是预期的受密码保护的 KoBackup v4 格式。
-   `info.xml` 已损坏。
-   备份被修改过或不完整。

首先用以下命令验证密码：

``` bash
python kobackup_password_check.py <backup_dir> -p "your-password"
```

------------------------------------------------------------------------

## `no backupFiles1/ or info.xml`

提供给程序的路径不是可识别的备份根目录或会话目录。

请确保目录中包含以下之一：

``` text
info.xml
```

或：

``` text
backupFiles1/
```

------------------------------------------------------------------------

## `no session folder`

所提供的备份根目录包含 `backupFiles1/`，但没有找到会话目录。

请检查备份是否完整复制。

------------------------------------------------------------------------

## 文件状态为 `FAILED`

对于较新的 KoBackup 14.x 备份，请确认：

-   `info.xml` 属于同一个备份。
-   加密文件未经修改地复制。
-   备份是完整的。
-   你使用了正确的密码。
-   这些文件确实与 `encMsgV3` 所描述的模块相关联。

运行时加上：

``` bash
-v
```

可以查看候选重试和失败详情。

------------------------------------------------------------------------

## 解密成功但解压出的数据看起来无效

如果使用的是旧版 CTR 备份，错误的候选偶尔会产生看起来部分合理的
数据。

尝试：

``` bash
--verify
```

（在 `checkMsgV3` 可用时）。

对于 KoBackup 14.x，GCM 标签验证提供了强得多的真实性检查。

------------------------------------------------------------------------

# 安全须知

本项目仅用于恢复和分析你**有权访问**的备份。

备份密码由脚本在本地处理。解密代码不需要任何网络服务。

解密后的输出可能包含高度敏感的信息，包括：

-   应用数据库
-   认证/会话数据
-   消息
-   照片和视频
-   Minecraft 世界
-   其他应用私有数据

请像对待原始设备一样谨慎对待解密后的输出。

请勿将解密后的备份内容上传到不受信任的服务。

------------------------------------------------------------------------

# 端到端示例工作流

## 1. 安装依赖

``` bash
python -m pip install pycryptodome
```

## 2. 校验密码

``` bash
python kobackup_password_check.py \
    "D:\Huawei\Backup\HUAWEI MatePad Pro__xxx__yyy" \
    -p "your-password"
```

预期输出：

``` text
OK    'your-password'
```

## 3. 解密并解压

``` bash
python huawei_kobackup_decrypt.py \
    "D:\Huawei\Backup\HUAWEI MatePad Pro__xxx__yyy" \
    "D:\Huawei\Decrypted" \
    "your-password" \
    -x
```

## 4. 可选：校验完整性并复制 APK

``` bash
python huawei_kobackup_decrypt.py \
    "D:\Huawei\Backup\HUAWEI MatePad Pro__xxx__yyy" \
    "D:\Huawei\Decrypted" \
    "your-password" \
    -x --verify --apk
```

------------------------------------------------------------------------

# 技术摘要

对于已验证的 KoBackup 14.7 / `backupVersion = 31` 格式：

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

对于 KoBackup 12 / `backupVersion = 29`，第二个 KDF 改为 5000 次
迭代，文件加密改为 AES-256-CTR。

------------------------------------------------------------------------

# 兼容性矩阵

  组件                               KoBackup 12 / v29    KoBackup 14.7 / v31
  --------------------------------- ------------------- ---------------------
  密码 KDF                                PBKDF2-SHA256         PBKDF2-SHA256
  密码 KDF 迭代次数                              10000                 10000
  密码 KDF 输出长度                            32 bytes              32 bytes
  `e_perbackupkey` 认证                         GCM tag               GCM tag
  文件密钥 KDF                            PBKDF2-SHA256         PBKDF2-SHA256
  文件密钥迭代次数                            **5000**             **10000**
  文件加密                               **AES-256-CTR**       **AES-256-GCM**
  文件标签                                          无             **16 字节**
  流式解密                                           是                     是
  `checkMsgV3` 校验                                 是                     是
  TAR 解压                                          是                     是
  APK 复制                                          是                     是

------------------------------------------------------------------------

# 致谢与背景

感谢 mauronofrio/Huawei-Backup-V4-Decrypt 项目，它是本项目的基础。
本项目基于对华为 KoBackup v4 备份元数据和加密行为的逆向工程与实际
验证。

本项目由 Zhipu GLM-5.3 制作。

本文档记载的 KoBackup 14.7 算法并非简单地从旧实现推断而来：以下
特性均已经过实验验证：

-   密码派生密钥使用 `PBKDF2-SHA256 × 10000`。
-   `e_perbackupkey` 使用 AES-256-GCM 认证。
-   成功恢复有效的 32 字节 ASCII 十六进制 `bkey`。
-   KoBackup 14.x 文件密钥使用 `PBKDF2-SHA256 × 10000`。
-   文件加密使用 AES-256-GCM。
-   加密文件末尾附加 16 字节认证标签。
-   解密结果成功通过 GCM 标签验证。
