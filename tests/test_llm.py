from types import SimpleNamespace

import httpx
import openai
import pytest

from wtffmpeg.llm import build_client, generate_ffmpeg_command, list_models, print_models


class FakeModels:
    def __init__(self, ids=None, exc=None):
        self.ids, self.exc = ids, exc

    def list(self):
        if self.exc:
            raise self.exc
        return [SimpleNamespace(id=i) for i in self.ids]


class FakeCompletions:
    def __init__(self, exc):
        self.exc = exc

    def create(self, **kwargs):
        raise self.exc


class FakeClient:
    def __init__(self, ids=None, exc=None):
        self.models = FakeModels(ids=ids, exc=exc)
        self.chat = SimpleNamespace(completions=FakeCompletions(exc))


def _status_error(cls, code):
    resp = httpx.Response(code, request=httpx.Request("GET", "http://x"))
    return cls("err", response=resp, body=None)


CFG_COMPAT = SimpleNamespace(model="b-model", provider="compat", base_url="http://h:1/v1")
CFG_OPENAI = SimpleNamespace(model="gpt-5-mini", provider="openai", base_url=None)


def test_build_client_openai_requires_key():
    cfg = SimpleNamespace(provider="openai", openai_api_key=None, bearer_token=None, base_url=None)
    with pytest.raises(RuntimeError, match="API key"):
        build_client(cfg)


def test_list_models_sorted():
    assert list_models(FakeClient(ids=["z", "a", "b-model"])) == ["a", "b-model", "z"]


def test_print_models_marks_current(capsys):
    rc = print_models(FakeClient(ids=["a", "b-model"]), CFG_COMPAT)
    out, err = capsys.readouterr()
    assert rc == 0
    assert "* b-model" in out and "  a" in out
    assert "Warning" not in err


def test_print_models_warns_when_absent(capsys):
    cfg = SimpleNamespace(model="missing", provider="openai", base_url=None)
    rc = print_models(FakeClient(ids=["a"]), cfg)
    out, err = capsys.readouterr()
    assert rc == 0
    assert "api.openai.com" in out
    assert "'missing' was not returned" in err


@pytest.mark.parametrize(
    "exc,needle",
    [
        (_status_error(openai.NotFoundError, 404), "does not appear to support model listing"),
        (_status_error(openai.AuthenticationError, 401), "Authentication failed"),
        (openai.APIConnectionError(request=httpx.Request("GET", "http://x")), "Could not reach"),
        (ValueError("boom"), "Failed to list models"),
    ],
)
def test_print_models_failures(capsys, exc, needle):
    rc = print_models(FakeClient(exc=exc), CFG_COMPAT)
    _, err = capsys.readouterr()
    assert rc == 1
    assert needle in err


@pytest.mark.parametrize(
    "cfg,exc,needle",
    [
        (CFG_OPENAI, _status_error(openai.NotFoundError, 404), "/models"),
        (CFG_OPENAI, _status_error(openai.AuthenticationError, 401), "WTFFMPEG_OPENAI_API_KEY"),
        (CFG_COMPAT, _status_error(openai.AuthenticationError, 401), "WTFFMPEG_BEARER_TOKEN"),
        (CFG_COMPAT, openai.APIConnectionError(request=httpx.Request("GET", "http://x")), "http://h:1/v1"),
        (CFG_OPENAI, ValueError("boom"), "ValueError: boom"),
    ],
)
def test_generate_ffmpeg_command_error_paths(capsys, cfg, exc, needle):
    messages = [{"role": "user", "content": "x"}]
    raw, cmd = generate_ffmpeg_command(messages, FakeClient(exc=exc), cfg)
    _, err = capsys.readouterr()
    assert (raw, cmd) == ("", "")
    assert needle in err
