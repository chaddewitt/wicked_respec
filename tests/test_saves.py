# tests/test_saves.py
import os
from src.saves import find_saves

def test_find_saves_excludes_baks(tmp_path):
    realm = tmp_path / "DataStore" / "29466"
    realm.mkdir(parents=True)
    (realm / "111_Character_a.cerimal").write_bytes(b"x")
    (realm / "111_Character_a.cerimal.bak1").write_bytes(b"x")
    hits = find_saves(str(tmp_path))
    assert len(hits) == 1
    assert hits[0].endswith("a.cerimal")
