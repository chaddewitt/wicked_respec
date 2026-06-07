# tests/test_backup.py
import os, hashlib
from src.backup import make_backup

def test_backup_copies_and_verifies(tmp_path):
    save = tmp_path / "char.cerimal"
    save.write_bytes(b"hello-save")
    (tmp_path / "char.cerimal.bak1").write_bytes(b"older")
    dest = make_backup(str(save), timestamp="20260606_120000")
    assert os.path.isdir(dest)
    copied = os.path.join(dest, "char.cerimal")
    assert open(copied, "rb").read() == b"hello-save"
    assert os.path.exists(os.path.join(dest, "char.cerimal.bak1"))

def test_backup_raises_on_unwritable(tmp_path):
    import pytest
    with pytest.raises(Exception):
        make_backup(str(tmp_path / "does-not-exist.cerimal"))
