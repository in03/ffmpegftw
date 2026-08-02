import json

from wtffmpeg import transcript as transcript_mod
from wtffmpeg.transcript import Transcript, build_pane_lines, format_exchange


def test_add_exchange_persists_jsonl(tmp_path):
    p = tmp_path / "t.jsonl"
    t = Transcript(path=p)
    t.add_exchange("make a gif", "```\nffmpeg -i a b\n```", ["ffmpeg -i a b"])
    rec = json.loads(p.read_text().splitlines()[0])
    assert rec["t"] == "exchange"
    assert rec["prompt"] == "make a gif"
    assert rec["commands"] == ["ffmpeg -i a b"]


def test_persist_false_writes_nothing(tmp_path):
    p = tmp_path / "t.jsonl"
    t = Transcript(path=p)
    t.add_exchange("x", "y", [], persist=False)
    t.log_exec("ls", 0, persist=False)
    assert not p.exists()
    assert len(t.entries) == 1  # in-memory record still kept


def test_log_exec_marks_matching_exchange(tmp_path):
    p = tmp_path / "t.jsonl"
    t = Transcript(path=p)
    ex = t.add_exchange("q", "r", ["ffmpeg -i a b", "ffmpeg -i a c"])
    t.log_exec("ffmpeg -i a b", 0)
    assert ex.executed and ex.exit_code == 0

    ex2 = t.add_exchange("q2", "r2", ["ffmpeg -i x y"])
    t.log_exec("ls -la", 1)  # unrelated command doesn't mark the exchange
    assert not ex2.executed
    recs = [json.loads(l) for l in p.read_text().splitlines()]
    assert [r["t"] for r in recs] == ["exchange", "exec", "exchange", "exec"]


def test_rotation_keeps_tail(tmp_path, monkeypatch):
    p = tmp_path / "t.jsonl"
    monkeypatch.setattr(transcript_mod, "MAX_BYTES", 100)
    monkeypatch.setattr(transcript_mod, "KEEP_LINES", 2)
    p.write_text("\n".join(f'{{"t":"exec","command":"c{i}","exit_code":0}}' for i in range(20)) + "\n")
    Transcript(path=p)
    lines = p.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[-1])["command"] == "c19"


def test_build_pane_lines_wraps_and_labels(tmp_path):
    t = Transcript(path=None)
    ex = t.add_exchange("make a gif please", "word " * 30 + "\n\nffmpeg -i a b", ["ffmpeg -i a b"])
    lines = build_pane_lines(t.entries, 40)
    assert all(len(ln) <= 40 for ln in lines)
    assert lines[0].startswith("#1 [not run]")
    ex.executed, ex.exit_code = True, 0
    assert build_pane_lines(t.entries, 40)[0].startswith("#1 [ran, exit 0]")


def test_format_exchange_includes_everything():
    t = Transcript(path=None)
    ex = t.add_exchange("q", "full response", ["ffmpeg -i a b"])
    out = format_exchange(ex, 1)
    assert "Prompt: q" in out
    assert "full response" in out
    assert "1. ffmpeg -i a b" in out
    assert "Executed: no" in out
