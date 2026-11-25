"""Tests for the encoding trace that drives the web demo's animation."""
import hashlib
import json

import pytest

from arithmetic_coder import ArithmeticCoder
from arithmetic_coder.coding.permutation import keyed_coder
from arithmetic_coder.coding.trace import encode_with_trace

TO_BE = "To be, or not to be, that is the question:"
ROMEO = "O Romeo, Romeo! wherefore art thou Romeo?"

# encode() outputs recorded before encode() was refactored onto iter_encode(): (bit count, sha256 prefix)
REFERENCE = {
    ("shakespeare", TO_BE): (90, "845191af3b2142c9"),
    ("shakespeare", ROMEO): (108, "62ba33d2fc3a102d"),
    ("uniform", TO_BE): (250, "22352f7b5cea61ad"),
    ("uniform", ROMEO): (244, "6e4c61ce19ce9818"),
}


@pytest.mark.parametrize("model_name, msg", list(REFERENCE))
def test_encode_unchanged_by_refactor(model_name, msg, request):
    coder = ArithmeticCoder(request.getfixturevalue(model_name))
    bits = coder.encode(msg).to_bits()
    assert (len(bits), hashlib.sha256(bits.encode()).hexdigest()[:16]) == REFERENCE[(model_name, msg)]


@pytest.mark.parametrize("msg", ["", "a", TO_BE, "Hark!\nWho goes there?"])
def test_trace_matches_encode(msg, shakespeare):
    coder = keyed_coder(shakespeare, "trace-key")
    pack, trace = encode_with_trace(coder, msg)
    assert pack == coder.encode(msg)
    assert len(trace) == len(msg)
    if msg:
        assert trace[-1]["running_bits"] == pack.to_bits()
        assert sum(t["bits_added"] for t in trace) == len(pack.to_bits())
    json.dumps(trace)  # everything is JSON-serialisable


def test_trace_step_invariants(shakespeare):
    coder = ArithmeticCoder(shakespeare)
    _, trace = encode_with_trace(coder, TO_BE)
    for i, t in enumerate(trace):
        assert t["char"] == TO_BE[i] and t["prefix"] == TO_BE[:i]
        assert t["bits_added"] >= 0
        segs = t["top_segments"]
        assert segs[0]["rel_start"] == 0 and segs[-1]["rel_end"] == 1
        assert all(a["rel_end"] == b["rel_start"] for a, b in zip(segs, segs[1:]))  # tiles [0, 1)
        selected = [s for s in segs if s["is_selected"]]
        assert len(selected) == 1 and selected[0]["char"] == t["char"]
        assert (selected[0]["rel_start"], selected[0]["rel_end"]) == (t["sub_l_rel"], t["sub_h_rel"])
        assert abs(sum(s["prob"] for s in segs) - 1) < 1e-9
        assert t["running_bits"].startswith(t["l_bits_after"][: t["shared_prefix_bits"]])


def test_predictable_text_has_zero_bit_steps(shakespeare):
    _, trace = encode_with_trace(ArithmeticCoder(shakespeare), TO_BE)
    assert any(t["bits_added"] == 0 for t in trace)
