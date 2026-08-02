from __future__ import annotations

import json
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_TRANSCRIPT_PATH = Path.home() / ".wtffmpeg" / "transcript.jsonl"

# Rotate the on-disk log when it grows past this, keeping the newest lines.
MAX_BYTES = 512_000
KEEP_LINES = 200


@dataclass
class Exchange:
    prompt: str
    raw: str
    commands: list[str] = field(default_factory=list)
    executed: bool = False
    exit_code: int | None = None


class Transcript:
    """Session record of prompt/response exchanges, optionally logged to JSONL."""

    def __init__(self, path: Path | None = DEFAULT_TRANSCRIPT_PATH):
        self.entries: list[Exchange] = []
        self.path = path
        if path is not None:
            self._rotate()

    def _rotate(self) -> None:
        try:
            if self.path.exists() and self.path.stat().st_size > MAX_BYTES:
                lines = self.path.read_text(encoding="utf-8").splitlines()
                self.path.write_text(
                    "\n".join(lines[-KEEP_LINES:]) + "\n", encoding="utf-8"
                )
        except OSError:
            pass

    def _write(self, obj: dict, persist: bool) -> None:
        if not persist or self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def add_exchange(
        self, prompt: str, raw: str, commands: list[str], *, persist: bool = True
    ) -> Exchange:
        ex = Exchange(prompt=prompt, raw=raw, commands=list(commands))
        self.entries.append(ex)
        self._write(
            {"t": "exchange", "prompt": prompt, "raw": raw, "commands": ex.commands},
            persist,
        )
        return ex

    def log_exec(self, command: str, exit_code: int, *, persist: bool = True) -> None:
        """Record a !command execution; marks the latest exchange it came from."""
        cmd = command.strip()
        if self.entries:
            last = self.entries[-1]
            if not last.executed and cmd in (c.strip() for c in last.commands):
                last.executed = True
                last.exit_code = exit_code
        self._write({"t": "exec", "command": cmd, "exit_code": exit_code}, persist)


def build_pane_lines(entries: list[Exchange], width: int) -> list[str]:
    """Flatten exchanges into display lines hard-wrapped to `width`.

    The pane viewport slices this list; wrapping here keeps the toolbar height
    fixed (soft-wrap would grow it).
    """
    width = max(20, width)
    lines: list[str] = []
    for i, ex in enumerate(entries, 1):
        if ex.executed:
            status = "ran" if ex.exit_code is None else f"ran, exit {ex.exit_code}"
        else:
            status = "not run"
        opts = f", {len(ex.commands)} commands" if len(ex.commands) > 1 else ""
        lines.extend(textwrap.wrap(f"#{i} [{status}{opts}] {ex.prompt}", width) or [""])
        body = ex.raw.strip() or "(no response)"
        for ln in body.splitlines():
            if ln.strip():
                lines.extend(
                    textwrap.wrap(ln, width, initial_indent="  ", subsequent_indent="  ")
                )
    return lines


def format_exchange(ex: Exchange, n: int) -> str:
    """Full-text rendering of one exchange for the /raw pager."""
    if ex.executed:
        status = "yes" if ex.exit_code is None else f"yes (exit {ex.exit_code})"
    else:
        status = "no"
    parts = [
        f"Exchange #{n}",
        f"Prompt: {ex.prompt}",
        "",
        "Response:",
        ex.raw or "(empty)",
        "",
    ]
    if ex.commands:
        parts.append("Extracted commands:")
        parts.extend(f"  {i}. {c}" for i, c in enumerate(ex.commands, 1))
    else:
        parts.append("Extracted commands: (none)")
    parts.append(f"Executed: {status}")
    return "\n".join(parts) + "\n"
