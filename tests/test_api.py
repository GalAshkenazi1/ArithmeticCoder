"""Tests for the encoder showcase API (FastAPI TestClient; the frontend is served from a temp folder)."""
from fractions import Fraction

import pytest
from fastapi.testclient import TestClient

from arithmetic_coder.api.app import create_app
from arithmetic_coder.models.registry import get_spec

TO_BE = "To be, or not to be, that is the question:"
UNICODE = "Grüße aus Zürich! שלום 👋"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    static = tmp_path_factory.mktemp("frontend")
    (static / "index.html").write_text("<!doctype html><title>demo</title>")
    return TestClient(create_app(static_dir=static))


def test_models(client):
    body = client.get("/api/models").json()
    models = {m["id"]: m for m in body["models"]}
    assert body["default"] == "shakespeare_char"
    assert models["shakespeare_char"]["name"] == "Shakespeare-GPT"
    assert len(models["shakespeare_char"]["vocab"]) == 65  # char models list what they accept
    assert models["uniform_bytes"]["tokenizer"] == "bytes" and models["uniform_bytes"]["vocab"] is None


def test_encode_then_decode(client):
    body = client.post("/api/encode", json={"model_id": "shakespeare_char", "text": TO_BE}).json()
    assert body["symbols"] == len(TO_BE) == len(body["trace"])
    assert body["bits"] == body["trace"][-1]["running_bits"]
    assert body["stats"]["payload_bits"] == len(body["bits"])
    assert body["stats"]["utf8_bits"] == 8 * len(TO_BE)
    # each row's decimal labels bracket the next window, and the best fraction sits inside its segment
    for step in body["trace"]:
        assert Fraction(step["l_dec_after"]) <= Fraction(step["r_dec"]) <= Fraction(step["h_dec_after"])
        assert step["sub_l_rel"] - 1e-9 <= step["r_rel_before"] <= step["sub_h_rel"] + 1e-9
        # the decoder's view: the received number falls in the chosen slice of every row
        assert step["sub_l_rel"] - 1e-9 <= step["received_rel_before"] <= step["sub_h_rel"] + 1e-9
    decoded = client.post("/api/decode", json={"model_id": "shakespeare_char", "bits": body["bits"],
                                               "symbols": body["symbols"]}).json()
    assert decoded["text"] == TO_BE


def test_unicode_with_bytes(client):
    body = client.post("/api/encode", json={"model_id": "uniform_bytes", "text": UNICODE}).json()
    assert body["symbols"] == len(UNICODE.encode("utf-8")) > body["stats"]["chars"]
    assert body["trace"][-1]["char_end"] == len(UNICODE)
    decoded = client.post("/api/decode", json={"model_id": "uniform_bytes", "bits": body["bits"],
                                               "symbols": body["symbols"]}).json()
    assert decoded["text"] == UNICODE


def test_empty_text(client):
    body = client.post("/api/encode", json={"model_id": "shakespeare_char", "text": ""}).json()
    assert body["bits"] == "" and body["trace"] == []


def test_errors(client):
    r = client.post("/api/encode", json={"model_id": "shakespeare_char", "text": "café (hi)"})
    assert r.status_code == 422 and set(r.json()["detail"]["unknown_chars"]) == {"é", "(", ")"}
    assert client.post("/api/encode", json={"model_id": "shakespeare_char", "text": "a" * 281}).status_code == 422
    assert client.post("/api/encode", json={"model_id": "nope", "text": "hi"}).status_code == 400
    assert client.post("/api/decode", json={"model_id": "shakespeare_char", "bits": "012", "symbols": 1}).status_code == 422


def test_gpt2_encode(client):
    if not get_spec("gpt2").available:
        pytest.skip("GPT-2 not fetched")
    body = client.post("/api/encode", json={"model_id": "gpt2", "text": UNICODE}).json()
    assert body["tokenizer"] == "gpt2" and body["precision_bits"] == 26
    assert body["symbols"] < len(UNICODE.encode("utf-8"))  # BPE merges bytes


def test_frontend_served_at_root(client):
    r = client.get("/")
    assert r.status_code == 200 and "<title>demo</title>" in r.text


def test_models_describe_their_training(client):
    models = {m["id"]: m for m in client.get("/api/models").json()["models"]}
    shakespeare = models["shakespeare_char"]
    assert shakespeare["dataset"]["name"] == "Tiny Shakespeare" and shakespeare["dataset"]["chars"] > 1_000_000
    assert len(shakespeare["examples"]) == 2 and shakespeare["training"]["params"] > 0
    assert models["uniform_bytes"]["kind"] == "uniform" and models["uniform_bytes"]["dataset"] is None
    # every typical sentence can be encoded by its own model
    for m in models.values():
        for text in m["examples"] if m["available"] else []:
            r = client.post("/api/tokenize", json={"model_id": m["id"], "text": text})
            assert r.status_code == 200, (m["id"], text)


def test_symbols(client):
    chars = client.get("/api/models/shakespeare_char/symbols").json()
    assert chars["count"] == 65 == len(chars["symbols"]) and not chars["sampled"]
    data = client.get("/api/models/uniform_bytes/symbols").json()
    assert data["count"] == 256 and data["symbols"][0xC3]["label"] == r"\xc3"
    words = client.get("/api/models/web_words/symbols").json()
    assert words["sampled"] and words["symbols"][0]["id"] == 256 and words["count"] > 4000
    assert client.get("/api/models/nope/symbols").status_code == 404


def test_tokenize(client):
    body = client.post("/api/tokenize", json={"model_id": "uniform_bytes", "text": "aé"}).json()
    assert [(s["char_start"], s["char_end"]) for s in body["symbols"]] == [(0, 1), (1, 2), (1, 2)]  # é is 2 bytes
    words = client.post("/api/tokenize", json={"model_id": "web_words", "text": "the cat"}).json()["symbols"]
    assert "".join(s["label"] for s in words) == "the cat" and len(words) < 7
    r = client.post("/api/tokenize", json={"model_id": "shakespeare_char", "text": "café"})
    assert r.status_code == 422 and r.json()["detail"]["unknown_chars"] == ["é"]


def test_redundant_models_are_unlisted_but_still_usable(client):
    listed = {m["id"] for m in client.get("/api/models").json()["models"]}
    assert listed.isdisjoint({"web_small", "wiki_bytes", "uniform"})  # "showcase": false
    assert {"shakespeare_char", "web_bytes", "uniform_bytes"} <= listed
    assert client.post("/api/encode", json={"model_id": "uniform", "text": "hi"}).status_code == 200  # studies use them


def test_health_and_cache(client):
    assert client.get("/api/health").json()["ok"] is True
    first = client.post("/api/encode", json={"model_id": "uniform_bytes", "text": "cached?"}).json()
    again = client.post("/api/encode", json={"model_id": "uniform_bytes", "text": "cached?"}).json()
    assert first == again


def test_rate_limit(tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><title>demo</title>")
    limited = TestClient(create_app(static_dir=tmp_path, rate_limit=2))
    codes = [limited.post("/api/tokenize", json={"model_id": "uniform_bytes", "text": "a"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    assert limited.get("/api/models").status_code == 200  # only POSTs to the API count


def test_a_busy_model_gives_503_but_doesnt_block_the_others(tmp_path):
    from arithmetic_coder.api.encoder_service import EncoderService

    service = EncoderService(wait_seconds=0.05)
    busy = TestClient(create_app(service=service, static_dir=tmp_path))
    lock = service.lock_for("uniform_bytes")
    lock.acquire()  # someone else's long request is running on this model
    try:
        r = busy.post("/api/encode", json={"model_id": "uniform_bytes", "text": "hi"})
        assert r.status_code == 503 and "busy" in r.json()["detail"]
        # another model answers right away (a slow GPT-2 request never stalls the small models)
        assert busy.post("/api/encode", json={"model_id": "uniform_ascii", "text": "hi"}).status_code == 200
    finally:
        lock.release()
    assert busy.post("/api/encode", json={"model_id": "uniform_bytes", "text": "hi"}).status_code == 200
