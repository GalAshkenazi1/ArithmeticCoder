"""Tests for the model registry (discovery by folder, readable names, loading by id)."""
import json
import shutil

import pytest

from arithmetic_coder.models import registry
from arithmetic_coder.models.registry import ASCII_VOCAB, ModelBankError, get_spec, list_models, load_model_uncached


def test_bank_models_have_readable_names():
    specs = {s.id: s for s in list_models()}
    assert specs["shakespeare_char"].name == "Shakespeare-GPT"
    assert specs["english_char"].name == "English-GPT"
    assert specs["uniform"].name == "Uniform Baseline"
    assert specs["uniform_ascii"].name == "Uniform ASCII"
    assert all(s.available for s in specs.values())
    assert len({s.name for s in specs.values()}) == len(specs)  # names are unique
    for model_id in ("shakespeare_char", "english_char", "uniform"):
        assert specs[model_id].vocab_size == 65
    assert specs["uniform_ascii"].vocab_size == len(ASCII_VOCAB) == 96


def test_uniform_ascii_encodes_everyday_text():
    from arithmetic_coder import ArithmeticCoder, load_model

    coder = ArithmeticCoder(load_model("uniform_ascii"))
    msg = 'Price: $12.50 (incl. tax) - "great deal" #1 {ok} <3'
    assert coder.decode(coder.encode(msg)) == msg


def test_unknown_model_raises():
    with pytest.raises(ModelBankError, match="unknown model"):
        get_spec("no_such_model")


def test_new_folder_is_discovered(tmp_path, monkeypatch):
    bank = tmp_path / "bank"
    shutil.copytree(registry.DEFAULT_BANK / "shakespeare_char", bank / "bard_copy")
    (bank / "bard_copy" / "model.json").write_text(json.dumps({"name": "Bard Copy", "description": "test"}))
    (bank / "half_model").mkdir()
    (bank / "half_model" / "model.json").write_text(json.dumps({"name": "Half", "description": "no files"}))
    monkeypatch.setenv("ARITH_MODEL_BANK", str(bank))

    specs = {s.id: s for s in list_models()}
    assert specs["bard_copy"].name == "Bard Copy" and specs["bard_copy"].available
    assert not specs["half_model"].available
    assert specs["uniform"].available is False  # uniform borrows shakespeare_char's vocab, absent here
    assert specs["uniform_ascii"].available  # needs no files
    assert len(load_model_uncached("bard_copy").get_vocab()) == 65
    with pytest.raises(ModelBankError, match="files are missing"):
        load_model_uncached("half_model")


def test_import_model(tmp_path, monkeypatch):
    from arithmetic_coder.models.importer import import_model

    monkeypatch.setenv("ARITH_MODEL_BANK", str(tmp_path / "bank"))
    source = registry.DEFAULT_BANK / "shakespeare_char"
    folder = import_model(source / "ckpt.pt", "bard_import", "Bard Import", "re-imported", meta_path=source / "meta.pkl")
    assert get_spec("bard_import").name == "Bard Import"
    assert (folder / "ckpt.pt").stat().st_size < (source / "ckpt.pt").stat().st_size  # optimizer state dropped
    with pytest.raises(ModelBankError, match="already exists"):
        import_model(source / "ckpt.pt", "bard_import", "x", "", meta_path=source / "meta.pkl")
    with pytest.raises(ModelBankError, match="model id"):
        import_model(source / "ckpt.pt", "Bad Id!", "x", "", meta_path=source / "meta.pkl")
