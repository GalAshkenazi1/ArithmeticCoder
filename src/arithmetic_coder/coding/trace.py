"""Step-by-step encoding trace for visualisation (the web demo's interval-zoom animation).

Everything comes from ArithmeticCoder.iter_encode, the same steps encode() uses, so the trace
shows the real encoder rather than a re-implementation. All values are JSON-friendly:
no Fractions; positions inside the current window are exact floats (cdf / total).
"""
from __future__ import annotations

import math
from fractions import Fraction

from arithmetic_coder.coding.encdec import ArithmeticCoder, EncodeStep, MessagePack, shortest_binary_in_range
from arithmetic_coder.tokenizers import char_spans

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


DECIMAL_EXTRA_DIGITS = 2  # decimal digits shown after the prefix l and h share


def _decimal_digits(num: int, s: int, d: int) -> str:
    """The first d decimal digits after the point of num / 2^s (0 <= num < 2^s), truncated."""
    return str((num * 10**d) >> s).zfill(d) if d else ""


def decimal_labels(L: int, R: int, s: int) -> tuple[str, str, int]:
    """Decimal labels for the window [L/2^s, (L+R)/2^s): (l, h, digits shared after "0.").

    Each label has just enough digits to tell l and h apart, plus DECIMAL_EXTRA_DIGITS, e.g.
    ("0.771", "0.775", 2). An upper bound of exactly 1 is returned as "1".
    """
    if s == 0:
        return "0", "1", 0
    H = L + R
    # enough digits to separate l from h: the width is R / 2^s, so about log10(2^s / R) of them
    d = max(1, math.ceil((s - R.bit_length() + 1) * math.log10(2))) + DECIMAL_EXTRA_DIGITS + 1
    l_digits = _decimal_digits(L, s, d)
    if H == 1 << s:
        shared = len(l_digits) - len(l_digits.lstrip("9"))
        return "0." + l_digits[: shared + DECIMAL_EXTRA_DIGITS], "1", shared
    h_digits = _decimal_digits(H, s, d)
    shared = next((i for i, (a, b) in enumerate(zip(l_digits, h_digits)) if a != b), d)
    n = min(d, shared + DECIMAL_EXTRA_DIGITS)
    return "0." + l_digits[:n], "0." + h_digits[:n], shared


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


def _step_record(coder: ArithmeticCoder, msg: str, step: EncodeStep, span: tuple[int, int],
                 prev_k: int, top_n: int) -> dict:
    """Turn one EncodeStep into the JSON record the frontend animates."""
    c, cdf, total = step.c_index, step.cdf, coder.total
    L, R, s = step.after
    running = shortest_binary_in_range(Fraction(L, 1 << s), Fraction(L + R, 1 << s))
    running_bits = MessagePack(running, 0).to_bits()
    l_bits, h_bits, shared = _axis_labels(L, R, s)
    l_dec, h_dec, dec_shared = decimal_labels(L, R, s)
    # where the best binary fraction sits inside the window *before* this step (the row it is drawn on)
    Lb, Rb, sb = step.before
    r_rel_before = float((running - Fraction(Lb, 1 << sb)) / Fraction(Rb, 1 << sb))
    k = len(running_bits)
    r_dec = "0." + _decimal_digits(running.numerator if k else 0, k, max(1, len(l_dec) - 2)) if k else "0"
    start, end = span
    return {
        "step_index": step.index,
        "symbol_id": step.symbol_id,
        "symbol": coder.tokenizer.vocab[step.symbol_id],  # display label, e.g. "e", " the", "\xd7"
        "char_start": start,
        "char_end": end,
        "char": msg[start:end],  # the text this symbol belongs to (one character for char models)
        "prefix": msg[:start],
        "prob": (cdf[c + 1] - cdf[c]) / total,
        "sub_l_rel": cdf[c] / total,
        "sub_h_rel": cdf[c + 1] / total,
        "top_segments": _segments(coder, cdf, c, top_n),
        "log2_width_after": math.log2(R) - s,
        "l_bits_after": l_bits,
        "h_bits_after": h_bits,
        "shared_prefix_bits": shared,
        "l_dec_after": l_dec,        # decimal window bounds after the step, e.g. "0.771"
        "h_dec_after": h_dec,
        "dec_shared_after": dec_shared,  # decimal digits l and h share after "0."
        "running_bits": running_bits,
        "bits_added": len(running_bits) - prev_k,
        "r_rel_before": r_rel_before,  # best binary fraction's position in this step's row, 0..1
        "r_dec": r_dec,                # its decimal value, truncated to the labels' length
    }


def encode_with_trace(coder: ArithmeticCoder, msg: str, top_n: int = 12) -> tuple[MessagePack, list[dict]]:
    """Encode msg exactly like coder.encode, and also return one trace record per symbol."""
    spans = char_spans(msg, coder.tokenizer, coder.tokenizer.encode(msg))
    trace: list[dict] = []
    windows: list[tuple[int, int, int]] = []
    L, R, s = 0, 1, 0
    prev_k = 0
    for step in coder.iter_encode(msg):
        record = _step_record(coder, msg, step, spans[step.index], prev_k, top_n)
        trace.append(record)
        windows.append(step.before)
        prev_k = len(record["running_bits"])
        L, R, s = step.after
    r = shortest_binary_in_range(Fraction(L, 1 << s), Fraction(L + R, 1 << s))
    # what a decoder sees: the final received number's position in each row's window (it always lies
    # inside that row's chosen slice, which is how the decoder knows the symbol)
    for record, (Lb, Rb, sb) in zip(trace, windows):
        record["received_rel_before"] = float((r - Fraction(Lb, 1 << sb)) / Fraction(Rb, 1 << sb))
    return MessagePack(r, len(trace)), trace
