from __future__ import annotations
import openai
from openai import OpenAI
from typing import Tuple
from pathlib import Path
import sys

from .config import AppConfig, resolve_config

def verify_connection(client: OpenAI, base_url: str | None) -> None:
    """
    Raises a RuntimeError with a helpful message on failure.
    """
    try:
        # Cheap request; no tokens.
        client.models.list()
    except Exception as e:
        target = base_url or "https://api.openai.com/v1"
        parts = [f"Unable to reach LLM endpoint: {target}",
                 f"Underlying error: {type(e).__name__}: {e!r}"]

        # Walk __cause__ chain (httpx usually lives here)
        c = getattr(e, "__cause__", None)
        depth = 0
        while c is not None and depth < 6:
            parts.append(f"Caused by: {type(c).__name__}: {c!r}")
            c = getattr(c, "__cause__", None)
            depth += 1

        raise RuntimeError("\n".join(parts)) from e

def list_models(client: OpenAI) -> list[str]:
    """Return sorted model IDs from the provider. Raises openai errors on failure."""
    # Iterating the SyncPage walks pagination transparently.
    return sorted(m.id for m in client.models.list())


def print_models(client: OpenAI, cfg: AppConfig) -> int:
    """List provider models to stdout, marking cfg.model. Returns an exit code."""
    target = cfg.base_url or "https://api.openai.com/v1"
    try:
        ids = list_models(client)
    except openai.AuthenticationError as e:
        print(
            f"Authentication failed listing models at {target}. Check --api-key / "
            f"WTFFMPEG_OPENAI_API_KEY (openai) or --bearer-token / WTFFMPEG_BEARER_TOKEN (compat).\n"
            f"  Detail: {e}",
            file=sys.stderr,
        )
        return 1
    except openai.APIConnectionError as e:
        print(
            f"Could not reach {target} to list models. Is the server running? (try /ping)\n  Detail: {e}",
            file=sys.stderr,
        )
        return 1
    except openai.APIStatusError as e:
        print(
            f"This server does not appear to support model listing (GET /v1/models) at {target}: {e}\n"
            f"Your configured model may still work.",
            file=sys.stderr,
        )
        return 1
    except Exception as e:
        print(f"Failed to list models: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    print(f"Models available at {target}:")
    for mid in ids:
        marker = "* " if mid == cfg.model else "  "
        print(f"  {marker}{mid}")
    if cfg.model not in ids:
        print(
            f"Warning: configured model '{cfg.model}' was not returned by the server "
            f"(compat model lists can be incomplete).",
            file=sys.stderr,
        )
    return 0


_FENCE_LANGS = ("bash", "sh", "shell", "zsh", "console")


def extract_commands(raw: str) -> list[str]:
    """Extract every ffmpeg command candidate from a model response, in order.

    Handles fenced code blocks, inline backticks, '$ ' prompt markers,
    backslash line continuations, and (inside fences) commands wrapped
    across lines without backslashes. Deduplicates preserving order.
    """
    if not raw:
        return []
    text = raw.strip()
    if text.lower().startswith("assistant:"):
        text = text[len("assistant:"):].strip()

    candidates: list[str] = []

    def scan(chunk: str, fenced: bool) -> None:
        # join backslash continuations first
        joined: list[str] = []
        pending = ""
        for ln in chunk.splitlines():
            ln = ln.strip()
            if ln.endswith("\\"):
                pending += ln[:-1].rstrip() + " "
                continue
            joined.append(pending + ln)
            pending = ""
        if pending:
            joined.append(pending.strip())

        for ln in joined:
            ln = ln.strip().strip("`").strip()
            if ln.startswith("$ "):
                ln = ln[2:]
            if ln.lower().startswith("ffmpeg"):
                candidates.append(ln)
            elif fenced and candidates and ln.startswith("-") and not ln.startswith("- "):
                # option line continuing a wrapped command inside a code block
                candidates[-1] += " " + ln

    for idx, chunk in enumerate(text.split("```")):
        if idx % 2 == 1:  # fenced block: drop a leading language tag
            first, _, rest = chunk.strip().partition("\n")
            if first.strip().lower() in _FENCE_LANGS:
                chunk = rest
        scan(chunk, fenced=(idx % 2 == 1))

    seen: set[str] = set()
    out: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def generate_ffmpeg_command(messages: list[dict], client: OpenAI, cfg: AppConfig) -> Tuple[str, str]:
    """Generate a single ffmpeg command from the LLM, and try to strip markdown/commentary."""
    try:
        # OpenAI's gpt-5 family rejects any temperature other than the default,
        # so only pin temperature for compat (local/self-hosted) endpoints.
        kwargs = {} if cfg.provider == "openai" else {"temperature": 0.0}
        resp = client.chat.completions.create(
            model=cfg.model,
            messages=messages,
            **kwargs,
        )
        raw = (resp.choices[0].message.content or "").strip()
        commands = extract_commands(raw)
        return raw, (commands[0] if commands else "")
    except openai.NotFoundError as e:
        print(
            f"Model or endpoint not found (404) for model '{cfg.model}'.\n"
            f"  - The model may not exist on this server: run /models (REPL) or wtff --list-models to see what's available.\n"
            f"  - Some compat servers also 404 on wrong paths; check --url / WTFFMPEG_LLM_API_URL.\n"
            f"  Detail: {e}",
            file=sys.stderr,
        )
        return "", ""
    except openai.AuthenticationError as e:
        who = (
            "--api-key / WTFFMPEG_OPENAI_API_KEY"
            if cfg.provider == "openai"
            else "--bearer-token / WTFFMPEG_BEARER_TOKEN"
        )
        print(f"Authentication failed. Check {who}.\n  Detail: {e}", file=sys.stderr)
        return "", ""
    except openai.APIConnectionError as e:
        target = cfg.base_url or "https://api.openai.com/v1"
        print(
            f"Could not connect to {target}. Is the server running? Try /ping, or check --url / WTFFMPEG_LLM_API_URL.\n"
            f"  Detail: {e}",
            file=sys.stderr,
        )
        return "", ""
    except Exception as e:
        print(f"Error during model inference: {type(e).__name__}: {e}", file=sys.stderr)
        return "", ""


def build_client(cfg: AppConfig) -> OpenAI:
    if cfg.provider == "openai":
        if not cfg.openai_api_key:
            raise RuntimeError(
                "Provider is 'openai' but no API key is set. "
                "Pass --api-key, set WTFFMPEG_OPENAI_API_KEY, or switch providers "
                "with --provider compat / --url."
            )
        return OpenAI(api_key=cfg.openai_api_key)
    
    api_key = cfg.bearer_token or "ollama"
    return OpenAI(base_url=cfg.base_url, api_key=api_key)