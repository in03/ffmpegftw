from wtffmpeg.history import DedupFileHistory, classify, matches, target_index


def test_classify():
    assert classify("!ffmpeg -i a b") == "command"
    assert classify("  !ls") == "command"
    assert classify("convert a to b") == "prompt"
    assert classify("/config show") == "prompt"


def test_matches_modes():
    assert matches("!x", "all") and matches("hi", "all")
    assert matches("!x", "command") and not matches("hi", "command")
    assert matches("hi", "prompt") and not matches("!x", "prompt")


# working lines: history entries oldest-first, then the in-progress edit line
LINES = ["make a gif", "!ffmpeg -i a.mp4 a.gif", "shrink it", "!ffmpeg -i a.gif -vf scale=320:-1 b.gif", ""]
LAST = len(LINES) - 1
is_prompt = lambda s: matches(s, "prompt")
is_command = lambda s: matches(s, "command")


def test_target_index_skips_nonmatching_up():
    # from the edit line, moving up through prompts only
    assert target_index(LINES, LAST, -1, is_prompt) == 2
    assert target_index(LINES, 2, -1, is_prompt) == 0
    assert target_index(LINES, 0, -1, is_prompt) is None


def test_target_index_commands_only():
    assert target_index(LINES, LAST, -1, is_command) == 3
    assert target_index(LINES, 3, -1, is_command) == 1


def test_target_index_down_reaches_edit_line():
    # moving down from a command entry in prompt mode still reaches the edit line
    assert target_index(LINES, 3, 1, is_prompt) == LAST
    assert target_index(LINES, 0, 1, is_prompt) == 2


def test_target_index_skips_duplicates_of_current():
    lines = ["!a", "!a", ""]
    assert target_index(lines, 1, -1, is_command) is None


def test_dedup_file_history_collapses_adjacent(tmp_path):
    p = tmp_path / "hist"
    h = DedupFileHistory(str(p))
    for s in ["a", "a", "b", "a"]:
        h.store_string(s)
    # fresh instance so we exercise the load path
    got = list(DedupFileHistory(str(p)).load_history_strings())
    assert got == ["a", "b", "a"]  # newest first, adjacent dupes collapsed
