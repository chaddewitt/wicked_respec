# src/backup.py
"""Verified timestamped backup of a save and its rolling .bak siblings."""
import os, glob, shutil, hashlib, datetime

def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()

def make_backup(save_path, timestamp=None):
    if not os.path.isfile(save_path):
        raise FileNotFoundError(save_path)
    ts = timestamp or datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    save_dir = os.path.dirname(os.path.abspath(save_path))
    dest = os.path.join(save_dir, "_wicked_respec_backups", ts)
    os.makedirs(dest, exist_ok=False)
    base = os.path.basename(save_path)
    sources = [save_path] + sorted(glob.glob(save_path + ".bak*"))
    for src in sources:
        dst = os.path.join(dest, os.path.basename(src))
        shutil.copy2(src, dst)
        if _sha256(src) != _sha256(dst):
            raise RuntimeError(f"backup verification failed for {src}")
    return dest
