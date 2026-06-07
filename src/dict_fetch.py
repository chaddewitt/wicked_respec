"""Obtain the game's Zstd dictionary needed to read .cerimal content.

The dictionary is game-derived and is NOT committed to this repo. When running from
source it is downloaded on demand from the public reference editor; in a packaged
build it is bundled into the app instead, so this module isn't used there.
"""
import os

DICT_URL = ("https://raw.githubusercontent.com/suidpit/nrftw-save-editor/"
            "HEAD/public/cerimal_zstd.dict")
ZSTD_DICT_MAGIC = b"\x37\xa4\x30\xec"   # zstd dictionary magic, 0xEC30A437 little-endian


def default_dict_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "assets", "cerimal_zstd.dict")


def is_valid_dict(path):
    """True iff `path` exists and begins with the zstd-dictionary magic."""
    try:
        with open(path, "rb") as f:
            return f.read(4) == ZSTD_DICT_MAGIC
    except OSError:
        return False


def manual_instructions(path):
    return (
        "Wicked Respec needs the game's Zstd dictionary and couldn't download it "
        "automatically (no internet connection?).\n\n"
        f"Please download this file:\n  {DICT_URL}\n\n"
        f"and save it as:\n  {path}\n\n"
        "(It's about 110 KB. Or, with the source checked out, run:  python scripts/fetch_dict.py)"
    )


def download_dict(path, url=DICT_URL, timeout=30):
    """Download the dictionary to `path`, validating the magic. Raises on any failure."""
    import urllib.request
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        data = resp.read()
    if data[:4] != ZSTD_DICT_MAGIC:
        raise RuntimeError("downloaded file is not a valid Zstd dictionary")
    tmp = path + ".part"
    try:
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)            # atomic; never leaves a half-written dict
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def ensure_dict(path=None):
    """Ensure a valid dictionary is present at `path` (default: assets/). Downloads it
    if missing. Returns True if it's present/valid afterward, False if unobtainable."""
    if path is None:
        path = default_dict_path()
    if is_valid_dict(path):
        return True
    try:
        download_dict(path)
    except Exception:
        return False
    return is_valid_dict(path)
