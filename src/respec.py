# src/respec.py
"""Pure respec computation. No I/O. Reset attributes to base; the game re-derives points."""
from src.cerimal.codec import encode_primitive

ATTRS = ("Health", "Stamina", "Strength", "Dexterity",
         "Intelligence", "Faith", "Focus", "ItemLoad")

class Write:
    __slots__ = ("name", "offset", "wk_id", "new_value", "bytes")
    def __init__(self, name, ref, new_value):
        self.name = name
        self.offset = ref.offset
        self.wk_id = ref.wk_id
        self.new_value = new_value
        self.bytes = encode_primitive(ref.wk_id, new_value)

class RespecPlan:
    def __init__(self):
        self.attributes_reset = []   # names whose value will change (current > base)
        self.refunded = 0            # sum of points removed (display only)
        self.writes = []             # list[Write], only for changed attributes
        self.backup_path = None

def compute_respec(refs, current_values, base=10):
    """refs: {attr_name: PrimitiveRef} from the Attributes map (locate_attribute_values).
       current_values: {attr_name: int}. Resets each attribute to base; only entries
       currently above base actually produce a write."""
    plan = RespecPlan()
    for a in ATTRS:
        if a not in refs:
            continue
        cur = current_values[a]
        if cur != base:
            plan.attributes_reset.append(a)
            plan.refunded += max(0, cur - base)  # never negative if a value is below base
            plan.writes.append(Write(a, refs[a], base))
    return plan
