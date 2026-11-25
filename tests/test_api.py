"""Tests for the demo API (FastAPI TestClient; the frontend is served from a temp folder)."""
import pytest
from fastapi.testclient import TestClient

from arithmetic_coder.api.app import create_app
from arithmetic_coder.api.demo_state import DemoState
from arithmetic_coder.coding.encdec import MessagePack

TO_BE = "To be, or not to be, that is the question:"


@pytest.fixture
def client(tmp_path, shakespeare):
    (tmp_path / "index.html").write_text("<!doctype html><title>demo</title>")
    return TestClient(create_app(DemoState("shakespeare_char"), static_dir=tmp_path))


def test_models_and_state(client):
    models = client.get("/api/models").json()
    assert models["current"] == "shakespeare_char"
    names = {m["id"]: m["name"] for m in models["models"]}
    assert names["shakespeare_char"] == "Shakespeare-GPT" and names["uniform"] == "Uniform Baseline"
    state = client.get("/api/state").json()
    assert state["model_name"] == "Shakespeare-GPT" and len(state["fingerprint_hex"]) == 8
    assert state["vocab_size"] == 65 and len(state["vocab"]) == 65


def test_send_roundtrip_both_ways(client):
    for sender, text in [("alice", TO_BE), ("bob", "Ay, my lord.\nWhat else?"), ("alice", "")]:
        r = client.post("/api/send", json={"sender": sender, "text": text})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["decoded_text"] == text and body["receiver"] == ("bob" if sender == "alice" else "alice")
        frame = bytes.fromhex(body["wire_hex"])
        layout = body["wire_layout"]
        assert [s["name"] for s in layout] == ["fingerprint", "length", "payload"]
        assert layout[0]["start"] == 0 and layout[-1]["end"] == len(frame) == body["stats"]["wire_bytes"]
        assert frame[:4].hex() == body["fingerprint_hex"]
        _, pack = MessagePack.from_bytes(frame)
        assert pack.length == len(text)
        assert body["stats"]["compressed_bits"] == len(pack.to_bits())
        assert len(body["trace"]) == len(text)
        assert body["wire_bits"] == "".join(format(b, "08b") for b in frame)


def test_switch_model_changes_fingerprint_and_rate(client):
    before = client.get("/api/state").json()["fingerprint_hex"]
    bpc_shakespeare = client.post("/api/send", json={"sender": "alice", "text": TO_BE}).json()["stats"]["bpc"]
    state = client.post("/api/switch_model", json={"model_id": "uniform"}).json()
    assert state["model_id"] == "uniform" and state["fingerprint_hex"] != before
    bpc_uniform = client.post("/api/send", json={"sender": "alice", "text": TO_BE}).json()["stats"]["bpc"]
    assert 5.5 < bpc_uniform < 6.2 and bpc_shakespeare < 0.6 * bpc_uniform
    # a new key changes the fingerprint but not the message size
    keyed = client.post("/api/switch_model", json={"model_id": "uniform", "key": "other-key"}).json()
    assert keyed["fingerprint_hex"] != state["fingerprint_hex"]


def test_errors(client):
    r = client.post("/api/send", json={"sender": "alice", "text": "café (hi)"})
    assert r.status_code == 422 and set(r.json()["detail"]["unknown_chars"]) == {"é", "(", ")"}
    assert client.post("/api/send", json={"sender": "alice", "text": "a" * 281}).status_code == 422
    assert client.post("/api/send", json={"sender": "eve", "text": "hi"}).status_code == 422
    assert client.post("/api/switch_model", json={"model_id": "nope"}).status_code == 400


def test_frontend_served_at_root(client):
    r = client.get("/")
    assert r.status_code == 200 and "<title>demo</title>" in r.text


UNICODE = "Grüße aus Zürich! שלום 👋"


def test_byte_model_sends_any_text(client):
    state = client.post("/api/switch_model", json={"model_id": "uniform_bytes"}).json()
    assert state["tokenizer"] == "bytes" and state["vocab"] is None and state["precision_bits"] == 16
    body = client.post("/api/send", json={"sender": "alice", "text": UNICODE}).json()
    assert body["decoded_text"] == UNICODE
    assert body["stats"]["symbols"] == len(UNICODE.encode("utf-8")) > body["stats"]["chars"]
    spans = [(t["char_start"], t["char_end"]) for t in body["trace"]]
    assert spans[-1][1] == len(UNICODE) and all(a <= b for a, b in spans)


def test_gpt2_send(client):
    from arithmetic_coder.models.registry import get_spec

    if not get_spec("gpt2").available:
        pytest.skip("GPT-2 not fetched")
    state = client.post("/api/switch_model", json={"model_id": "gpt2"}).json()
    assert state["tokenizer"] == "gpt2" and state["precision_bits"] == 26
    body = client.post("/api/send", json={"sender": "bob", "text": UNICODE}).json()
    assert body["decoded_text"] == UNICODE
    assert body["stats"]["symbols"] < len(UNICODE.encode("utf-8"))  # BPE merges bytes
