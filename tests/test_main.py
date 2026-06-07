import os
import src.gui  # import must not error (imports tkinter, which is fine without a display)
from src.main import _dict_path


def test_dict_path_dev_mode_resolves_existing_file():
    p = _dict_path()
    assert p.endswith("cerimal_zstd.dict")
    assert os.path.isfile(p)
