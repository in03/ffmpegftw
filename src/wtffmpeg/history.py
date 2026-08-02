from __future__ import annotations

from prompt_toolkit.history import FileHistory

# History navigation modes: what plain up/down arrows scroll through.
#   prompt  - things you typed that weren't executed shell commands
#   command - executed / generated !commands only
#   all     - everything (default)
HISTORY_MODES = ("prompt", "command", "all")


def classify(line: str) -> str:
    """Classify a history line by its prefix: '!' lines are commands, the rest prompts."""
    return "command" if line.lstrip().startswith("!") else "prompt"


def matches(line: str, mode: str) -> bool:
    return mode == "all" or classify(line) == mode


def target_index(lines: list[str], index: int, delta: int, pred) -> int | None:
    """Next working-lines index in `delta` direction whose text satisfies `pred`.

    The last working line is the in-progress edit line and is always reachable
    when moving down, so the user can get back to what they were typing.
    Entries identical to the current line are skipped (bash ignoredups-style).
    Returns None when there is nothing to move to.
    """
    n = len(lines)
    i = index + delta
    while 0 <= i < n:
        if i == n - 1 and delta > 0:
            return i
        if pred(lines[i]) and lines[i] != lines[index]:
            return i
        i += delta
    return None


def history_move(buffer, delta: int, pred) -> None:
    """Move the buffer through history, visiting only entries matching `pred`."""
    lines = getattr(buffer, "_working_lines", None)
    if not lines:
        return
    tgt = target_index(list(lines), buffer.working_index, delta, pred)
    if tgt is not None:
        buffer.go_to_history(tgt)
        buffer.cursor_position = len(buffer.text)


class DedupFileHistory(FileHistory):
    """FileHistory that collapses adjacent duplicate entries on load."""

    def load_history_strings(self):
        prev = object()
        for s in super().load_history_strings():
            if s != prev:
                yield s
            prev = s
