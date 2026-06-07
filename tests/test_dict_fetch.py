from src.dict_fetch import (
    is_valid_dict, ensure_dict, ZSTD_DICT_MAGIC, manual_instructions,
    default_dict_path, DICT_URL,
)


def test_is_valid_dict_rejects_bogus(tmp_path):
    f = tmp_path / "bad.dict"; f.write_bytes(b"not a dictionary")
    assert is_valid_dict(str(f)) is False


def test_is_valid_dict_missing(tmp_path):
    assert is_valid_dict(str(tmp_path / "nope.dict")) is False


def test_is_valid_dict_accepts_magic(tmp_path):
    f = tmp_path / "ok.dict"; f.write_bytes(ZSTD_DICT_MAGIC + b"\x00" * 64)
    assert is_valid_dict(str(f)) is True


def test_ensure_dict_true_when_present_no_network(tmp_path):
    # A valid-magic file already present -> ensure_dict returns True without downloading.
    f = tmp_path / "cerimal_zstd.dict"; f.write_bytes(ZSTD_DICT_MAGIC + b"\x00" * 100)
    assert ensure_dict(str(f)) is True


def test_manual_instructions_has_url_and_path(tmp_path):
    p = str(tmp_path / "cerimal_zstd.dict")
    msg = manual_instructions(p)
    assert DICT_URL in msg and p in msg


def test_default_dict_path_points_to_assets():
    assert default_dict_path().replace("\\", "/").endswith("assets/cerimal_zstd.dict")
