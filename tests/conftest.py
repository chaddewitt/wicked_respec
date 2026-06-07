import os, glob, pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
FIXTURES = os.path.join(HERE, "fixtures")
DICT_PATH = os.path.join(PROJ, "assets", "cerimal_zstd.dict")


@pytest.fixture
def dict_bytes():
    with open(DICT_PATH, "rb") as f:
        return f.read()


@pytest.fixture
def main_save():
    hits = [p for p in glob.glob(os.path.join(FIXTURES, "*.cerimal*"))
            if p.endswith(".cerimal")]
    assert hits, "no .cerimal fixture found"
    with open(hits[0], "rb") as f:
        return f.read()


@pytest.fixture
def all_saves():
    out = []
    for p in glob.glob(os.path.join(FIXTURES, "*.cerimal*")):
        with open(p, "rb") as f:
            out.append((os.path.basename(p), f.read()))
    return out
