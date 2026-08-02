# Config / runtime-client notes — read before resuming this branch

_Written 2026-08-02, reconstructing the state of two divergent laptop checkouts
(`wtf.1`, `wtf.2`) before deleting them. This branch (`carry/wtf2-lazy-client-config`)
carries the unfinished-but-preferred work rescued from the `wtf.2` working tree._

## The problem all this code was solving

The REPL lets the user change transport settings live via `/config set`
(`provider`, `base_url`, `openai_api_key`, `bearer_token`). When one of those
changes, the already-constructed LLM `client` is stale and must be rebuilt.
Nothing is kept alive between prompts, so the *only* client-invalidating event
is a `/config` edit. Every variant below is a different way to answer one
question: **"did this `/config` change invalidate the live client — rebuild it?"**

## Why the code looked divergent

Three overlapping mechanisms existed across the checkouts:

1. **Inline (older):** `_transport_changed(old, new)` compares a hardcoded key
   list inside `handle_config_command` and rebuilds the client inline.
2. **Fingerprint/reconcile (newer):** `RuntimeState` + `client_fingerprint` +
   `reconcile_runtime` rebuild the client only when a fingerprint tuple changes.
3. **Abandoned (`wtf.1` commit `40a209a`):** rewrote `apply_overrides` to *mutate*
   cfg in place and return the `set` of changed field names, so the caller could
   check whether a transport field changed. **Dead end** — `AppConfig` is
   `@dataclass(frozen=True)`, so `setattr` raises `FrozenInstanceError`; it would
   require unfreezing the config, and it dropped base_url/provider normalization.
   Only its repl UI TODO was worth keeping → see branch `carry/wtf1-ui-todo`.

`main` is stuck **half-migrated between #1 and #2**: its `/config` handler runs
*both* every time and then throws one away —

```python
cfg, client = handle_config_command(...)   # rebuilds client INLINE (#1)
reconcile_runtime(cfg, rt)                  # rebuilds rt.client AGAIN (#2)
generate_ffmpeg_command(messages, client, cfg.model)   # uses `client`, NOT rt.client
```

So `rt.client` is computed and never used for generation. That redundancy is the
divergence you were feeling.

## Chosen direction (this branch)

Finish the migration to the **immutable-config + fingerprint/reconcile** model:

- Keep `AppConfig` frozen; `apply_overrides` returns a *new* config via `replace()`.
- Make `reconcile_runtime` (using `rt.client`) the **single** rebuild path.
- **Delete the dead `_transport_changed` / inline `build_client` path** from
  `handle_config_command` so there is exactly one mechanism.

## client_fingerprint — decide deliberately (and note: fixes two real bugs)

```python
# main (buggy)
(provider, base_url, model, bool(openai_api_key), timeout_s, max_retries)
# wtf.2 (this branch — preferred)
(provider, base_url, openai_api_key, bearer_token)
```

The wtf.2 fingerprint is more correct for "rebuild client on transport change":

- **Adds `bearer_token`** — main omits it, so on the `compat` provider, changing
  the bearer token via `/config` would NOT rebuild the client. Bug.
- **Uses the actual `openai_api_key` value, not `bool(...)`** — main only rebuilds
  when the key flips set/unset, so swapping to a *different* key mid-session
  silently keeps the old client. Bug.
- **Drops `model`** — the OpenAI SDK takes `model` per-request
  (`generate_ffmpeg_command(..., cfg.model)`), so it was never part of client
  construction; rebuilding on model change was wasted work.

## Status of this branch

Unfinished — rescued from uncommitted work, not reviewed or tested end-to-end.
It imports and `--help` works; the runtime `/config` flows need exercising before
merge to `main`.
