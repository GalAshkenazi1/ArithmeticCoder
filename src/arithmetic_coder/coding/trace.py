"""Step-by-step encoding trace for visualisation (the web demo's interval-zoom animation).

Everything comes from ArithmeticCoder.iter_encode, the same steps encode() uses, so the trace
shows the real encoder rather than a re-implementation. All values are JSON-friendly:
no Fractions; positions inside the current window are exact floats (cdf / total).
"""
from __future__ import annotations

import math
from fractions import Fraction

from arithmetic_coder.coding.encdec import ArithmeticCoder, EncodeStep, MessagePack, shortest_binary_in_range

AXIS_EXTRA_BITS = 8  # digits shown after the shared binary prefix of l and h


def _binary_digits(num: int, s: int) -> str:
    """The s binary digits after the point of num / 2^s (requires 0 <= num < 2^s)."""
    return format(num, f"0{s}b") if s else ""


def _axis_labels(L: int, R: int, s: int) -> tuple[str, str, int]:
    """Binary labels for the window [L/2^s, (L+R)/2^s): (l_bits, h_bits, shared prefix length).

    l_bits / h_bits are the digits after "0." up to the shared prefix plus AXIS_EXTRA_BITS.
    An upper bound of exactly 1 is returned as "1" (it has no "0." expansion).
    """
    H = L + R
    if H == 1 << s:  # h == 1
        common = len(_binary_digits(L, s)) - len(_binary_digits(L, s).lstrip("1"))
        n = min(s, common + AXIS_EXTRA_BITS)
        return _binary_digits(L, s)[:n], "1", common
    common = s - (L ^ H).bit_length()
    n = min(s, common + AXIS_EXTRA_BITS)
    return _binary_digits(L, s)[:n], _binary_digits(H, s)[:n], common


def _segments(coder: ArithmeticCoder, cdf: list[int], selected: int, top_n: int) -> list[dict]:
    """The window's partition in coding order: the top_n likeliest chars (+ the selected one), others merged."""
    total = coder.total
    freqs = [cdf[j + 1] - cdf[j] for j in range(len(cdf) - 1)]
    keep = set(sorted(range(len(freqs)), key=lambda j: (-freqs[j], j))[:top_n]) | {selected}
    segments: list[dict] = []
    for j, f in enumerate(freqs):
        if j in keep:
            segments.append({"char": coder.vocab[j], "rel_start": cdf[j] / total, "rel_end": cdf[j + 1] / total,
                             "prob": f / total, "is_selected": j == selected})
        elif segments and segments[-1]["char"] is None:  # extend the current "other" run
            segments[-1]["rel_end"] = cdf[j + 1] / total
            segments[-1]["prob"] += f / total
            segments[-1]["count"] += 1
        else:
            segments.append({"char": None, "rel_start": cdf[j] / total, "rel_end": cdf[j + 1] / total,
                             "prob": f / total, "is_selected": False, "count": 1})
    return segments


def _step_record(coder: ArithmeticCoder, msg: str, step: EncodeStep, prev_k: int, top_n: int) -> dict:
    """Turn one EncodeStep into the JSON record the frontend animates."""
    c, cdf, total = step.c_index, step.cdf, coder.total
    L, R, s = step.after
    running = shortest_binary_in_range(Fraction(L, 1 << s), Fraction(L + R, 1 << s))
    running_bits = MessagePack(running, 0).to_bits()
    l_bits, h_bits, shared = _axis_labels(L, R, s)
    return {
        "step_index": step.index,
        "char": msg[step.index],
        "prefix": msg[: step.index],
        "prob": (cdf[c + 1] - cdf[c]) / total,
        "sub_l_rel": cdf[c] / total,
        "sub_h_rel": cdf[c + 1] / total,
        "top_segments": _segments(coder, cdf, c, top_n),
        "log2_width_after": math.log2(R) - s,
        "l_bits_after": l_bits,
        "h_bits_after": h_bits,
        "shared_prefix_bits": shared,
        "running_bits": running_bits,
        "bits_added": len(running_bits) - prev_k,
    }


def encode_with_trace(coder: ArithmeticCoder, msg: str, top_n: int = 12) -> tuple[MessagePack, list[dict]]:
    """Encode msg exactly like coder.encode, and also return one trace record per character."""
    trace: list[dict] = []
    L, R, s = 0, 1, 0
    prev_k = 0
    for step in coder.iter_encode(msg):
        record = _step_record(coder, msg, step, prev_k, top_n)
        trace.append(record)
        prev_k = len(record["running_bits"])
        L, R, s = step.after
    r = shortest_binary_in_range(Fraction(L, 1 << s), Fraction(L + R, 1 << s))
    return MessagePack(r, len(msg)), trace
