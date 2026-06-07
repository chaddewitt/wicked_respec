from src.respec import compute_respec, ATTRS

class FakeRef:
    def __init__(self, wk, off): self.wk_id = wk; self.offset = off; self.width = 4

def test_reset_only_changes_above_base():
    refs = {a: FakeRef(5, i * 8) for i, a in enumerate(ATTRS)}
    vals = {a: 10 for a in ATTRS}; vals["Strength"] = 19; vals["Dexterity"] = 13
    plan = compute_respec(refs, vals, base=10)
    assert plan.refunded == 12
    assert set(plan.attributes_reset) == {"Strength", "Dexterity"}
    assert {w.name for w in plan.writes} == {"Strength", "Dexterity"}
    for w in plan.writes:
        assert w.new_value == 10
        assert w.bytes == (10).to_bytes(4, "little", signed=True)

def test_noop_when_all_base():
    refs = {a: FakeRef(5, i * 8) for i, a in enumerate(ATTRS)}
    plan = compute_respec(refs, {a: 10 for a in ATTRS})
    assert plan.writes == [] and plan.refunded == 0 and plan.attributes_reset == []

def test_missing_attr_skipped():
    plan = compute_respec({"Strength": FakeRef(5, 0)}, {"Strength": 15})
    assert plan.refunded == 5 and len(plan.writes) == 1

def test_refunded_never_negative_for_below_base_value():
    # A corrupt/modded save could hold a value below base; refund must not go negative.
    plan = compute_respec({"Strength": FakeRef(5, 0)}, {"Strength": 7}, base=10)
    assert plan.refunded == 0
    assert plan.attributes_reset == ["Strength"]
    assert plan.writes[0].new_value == 10
