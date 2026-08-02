from pathlib import Path
from types import SimpleNamespace

import pytest

from wtffmpeg import config as config_mod
from wtffmpeg import repl as repl_mod
from wtffmpeg.cli import build_parser
from wtffmpeg.config import (
    _coerce_value,
    normalize_base_url,
    resolve_config,
    save_config,
    load_config,
)
from wtffmpeg.repl import trim_messages

NOPATH = Path("/nonexistent-wtffmpeg-config")


def make_args(**kw):
    base = dict(
        profile_dir=None,
        profile=None,
        api_key=None,
        bearer_token=None,
        url=None,
        provider=None,
        model=None,
        context_turns=None,
        nag=None,
        copy=None,
        prompt=None,
        prompt_once=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


# --- provider inference -----------------------------------------------------

def test_defaults_are_compat_localhost():
    cfg = resolve_config(make_args(), config_path=NOPATH)
    assert cfg.provider == "compat"
    assert cfg.base_url == "http://localhost:11434/v1"
    assert cfg.model == "gpt-oss:20b"


def test_api_key_alone_infers_openai():
    cfg = resolve_config(make_args(api_key="sk-x"), config_path=NOPATH)
    assert cfg.provider == "openai"
    assert cfg.base_url is None
    assert cfg.model == "gpt-5-mini"


def test_env_url_beats_key_inference(monkeypatch):
    monkeypatch.setenv("WTFFMPEG_LLM_API_URL", "http://localhost:11434")
    cfg = resolve_config(make_args(api_key="sk-x"), config_path=NOPATH)
    assert cfg.provider == "compat"
    assert cfg.base_url == "http://localhost:11434/v1"


def test_file_base_url_beats_key_inference(tmp_path):
    cf = tmp_path / "config.env"
    cf.write_text("base_url=http://myhost:8080\n")
    cfg = resolve_config(make_args(api_key="sk-x"), config_path=cf)
    assert cfg.provider == "compat"
    assert cfg.base_url == "http://myhost:8080/v1"


def test_explicit_provider_beats_inference(monkeypatch):
    monkeypatch.setenv("WTFFMPEG_LLM_API_URL", "http://localhost:11434")
    cfg = resolve_config(make_args(api_key="sk-x", provider="openai"), config_path=NOPATH)
    assert cfg.provider == "openai"
    assert cfg.base_url is None

    monkeypatch.setenv("WTFFMPEG_PROVIDER", "compat")
    cfg = resolve_config(make_args(api_key="sk-x", provider=None), config_path=NOPATH)
    assert cfg.provider == "compat"


# --- precedence -------------------------------------------------------------

def test_model_precedence(monkeypatch, tmp_path):
    cf = tmp_path / "config.env"
    cf.write_text("model=from-file\n")

    cfg = resolve_config(make_args(), config_path=cf)
    assert cfg.model == "from-file"

    monkeypatch.setenv("WTFFMPEG_MODEL", "from-env")
    cfg = resolve_config(make_args(), config_path=cf)
    assert cfg.model == "from-env"

    cfg = resolve_config(make_args(model="from-args"), config_path=cf)
    assert cfg.model == "from-args"


def test_profile_dir_env_and_cli(monkeypatch):
    monkeypatch.setenv("WTFFMPEG_PROFILE_DIR", "/tmp/px")
    cfg = resolve_config(make_args(), config_path=NOPATH)
    assert cfg.profile_dir == Path("/tmp/px")

    cfg = resolve_config(make_args(profile_dir=Path("/tmp/cli")), config_path=NOPATH)
    assert cfg.profile_dir == Path("/tmp/cli")


# --- tri-state booleans -----------------------------------------------------

def test_parser_bool_flags_are_tristate():
    pa = build_parser().parse_args
    ns = pa([])
    assert ns.copy is None and ns.nag is None
    assert pa(["-c"]).copy is True
    assert pa(["--copy"]).copy is True
    assert pa(["--no-copy"]).copy is False
    assert pa(["--nag"]).nag is True
    assert pa(["--no-nag"]).nag is False


def test_cli_overrides_file_persisted_bools(tmp_path):
    cf = tmp_path / "config.env"
    cf.write_text("no_nag=true\ncopy=true\n")

    cfg = resolve_config(make_args(), config_path=cf)
    assert cfg.no_nag is True and cfg.copy is True

    cfg = resolve_config(make_args(nag=True, copy=False), config_path=cf)
    assert cfg.no_nag is False and cfg.copy is False

    cfg = resolve_config(make_args(), config_path=NOPATH)
    assert cfg.no_nag is False and cfg.copy is False


# --- helpers ----------------------------------------------------------------

def test_coerce_value():
    assert _coerce_value("model", "none") is None
    assert _coerce_value("context_turns", "5") == 5
    assert _coerce_value("copy", "yes") is True
    assert _coerce_value("no_nag", "off") is False
    with pytest.raises(ValueError):
        _coerce_value("copy", "maybe")
    assert _coerce_value("model", "llama3") == "llama3"


def test_coerce_value_not_duplicated():
    assert repl_mod._coerce_value is config_mod._coerce_value


def test_normalize_base_url():
    assert normalize_base_url("localhost:11434") == "http://localhost:11434/v1"
    assert normalize_base_url("http://h:1/") == "http://h:1/v1"
    assert normalize_base_url("https://h/v1") == "https://h/v1"


def test_trim_messages():
    system = [{"role": "system", "content": "s"}]
    turns = []
    for i in range(5):
        turns += [
            {"role": "user", "content": f"u{i}"},
            {"role": "assistant", "content": f"a{i}"},
        ]
    msgs = system + turns

    assert trim_messages(list(msgs), keep_last_turns=0) == system
    assert trim_messages(list(msgs), keep_last_turns=12) == msgs
    trimmed = trim_messages(list(msgs), keep_last_turns=2)
    assert trimmed[0] == system[0]
    assert trimmed[1:] == turns[-4:]


def test_save_load_roundtrip_excludes_secrets(tmp_path):
    cfg = resolve_config(make_args(api_key="sk-secret", model="m1"), config_path=NOPATH)
    out = tmp_path / "saved.env"
    save_config(cfg, path=out)
    text = out.read_text()
    assert "sk-secret" not in text
    data = load_config(out)
    assert data["model"] == "m1"
    assert data["provider"] == "openai"
    assert "openai_api_key" not in data
