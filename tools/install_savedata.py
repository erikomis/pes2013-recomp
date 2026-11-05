#!/usr/bin/env python3
"""Install a save tree made on a real PS3 (an Option File) for cellSaveData.

    install_savedata.py SRC DST --keys FILE

SRC holds one directory per save (BLUS31029EEDIT, BLUS31029EFACE001, ...). DST is
the savedata directory cellSaveData reads: $PS3_GAMEDATA_ROOT/dev_hdd0/home/00000001/savedata.
SRC is not changed, and a save already in DST is replaced.

On a console the files PARAM.PFD lists as protected are encrypted. The runtime keeps
them in the clear and uses PARAM.PFD only to name its secure files, one per line
(libs/system/cellSaveData.c), so they are decrypted here and that list replaces it.
PES 2013 protects DATA.BIN only in BLUS31029EEDIT; the other saves are copied as they are.

FILE is key=value lines, kept out of the repository, mode 600 (AGENTS.md):

    syscon_manager_key=<32 hex>   public, the key pfdtool uses for this format
    secure_file_id=<32 hex>       what the title passes to cellSaveData; print it
                                  with tools/run.sh SAVEDATA_SECUREID_LOG=1
"""
import argparse
import os
import shutil
import struct
import sys

from Crypto.Cipher import AES

ENTRY_SIZE = 272
SKIP = {"PARAM.PFD"}
# cellSaveData looks for these names in upper case.
RENAME = {"icon0.png": "ICON0.PNG"}


def read_keys(path):
    keys = {}
    with open(path, encoding="ascii") as f:
        for line in f:
            name, sep, value = line.strip().partition("=")
            if sep:
                keys[name] = bytes.fromhex(value)
    for name in ("syscon_manager_key", "secure_file_id"):
        if len(keys.get(name, b"")) != 16:
            sys.exit(f"{path}: no 16-byte {name}")
    return keys


def protected_files(pfd):
    """{name: (encrypted entry key, plain size)}, PARAM.SFO left out: it is in the clear."""
    capacity, _, used = struct.unpack(">QQQ", pfd[0x60:0x78])
    table = 0x78 + 8 * capacity
    files = {}
    for i in range(used):
        entry = pfd[table + i * ENTRY_SIZE:table + (i + 1) * ENTRY_SIZE]
        name = entry[8:73].split(b"\0")[0].decode("ascii")
        if name != "PARAM.SFO":
            files[name] = (entry[80:144], struct.unpack(">Q", entry[264:272])[0])
    return files


def entry_key(encrypted, keys):
    # pfdtool's pfd_get_entry_hash_key: the id with four constants woven in.
    iv, rest = bytearray(), iter(keys["secure_file_id"])
    for i in range(16):
        iv.append({1: 11, 2: 15, 5: 14, 8: 10}[i] if i in (1, 2, 5, 8) else next(rest))
    return AES.new(keys["syscon_manager_key"], AES.MODE_CBC, bytes(iv)).decrypt(encrypted)[:16]


def decrypt(data, key, size):
    if len(data) % 16:
        sys.exit("a protected file is not a whole number of AES blocks")
    aes = AES.new(key, AES.MODE_ECB)
    counters = aes.encrypt(b"".join(struct.pack(">QQ", i, 0) for i in range(len(data) // 16)))
    plain = aes.decrypt(data)
    return bytes(a ^ b for a, b in zip(plain, counters))[:size]


def install(src, dst, keys):
    """One save. Returns how many of its files were decrypted."""
    tmp = dst + ".tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    with open(os.path.join(src, "PARAM.PFD"), "rb") as f:
        protected = protected_files(f.read())
    for name in os.listdir(src):
        if name in SKIP or name.startswith("."):
            continue
        out = os.path.join(tmp, RENAME.get(name.lower(), name))
        if name in protected:
            with open(os.path.join(src, name), "rb") as f:
                data = f.read()
            encrypted, size = protected[name]
            with open(out, "wb") as f:
                f.write(decrypt(data, entry_key(encrypted, keys), size))
        else:
            shutil.copyfile(os.path.join(src, name), out)
    if protected:
        with open(os.path.join(tmp, "PARAM.PFD"), "w", encoding="ascii") as f:
            f.write("".join(name + "\n" for name in protected))
    shutil.rmtree(dst, ignore_errors=True)
    os.rename(tmp, dst)
    return len(protected)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--keys", required=True)
    a = ap.parse_args()
    keys = read_keys(a.keys)
    os.makedirs(a.dst, exist_ok=True)
    saves = sorted(n for n in os.listdir(a.src) if os.path.isfile(os.path.join(a.src, n, "PARAM.SFO")))
    if not saves:
        sys.exit(f"no saves under {a.src}")
    decrypted = sum(install(os.path.join(a.src, n), os.path.join(a.dst, n), keys) for n in saves)
    print(f"{len(saves)} saves installed in {a.dst}, {decrypted} protected files decrypted")


if __name__ == "__main__":
    main()
