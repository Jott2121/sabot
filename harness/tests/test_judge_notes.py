import pathlib, pytest
from sabot.judge.notes import _SECTION, ground_truth_note

TASKS = pathlib.Path.home() / "sabot" / "tasks"


def test_t1_o1_note_extracted_verbatim_content():
    note = ground_truth_note("T1", "O1", TASKS)
    assert "47.1" in note and "74.1" in note
    assert "\n" not in note                      # normalized to one line


def test_multiline_bullet_continuation_is_joined():
    note = ground_truth_note("T1", "O4", TASKS)
    assert "cross-reference resolution" in note  # lives on a continuation line


def test_every_registered_spec_pair_has_a_note():
    from sabot.adapters.operator_specs import SPECS
    for task_id, operator_id in SPECS:
        assert ground_truth_note(task_id, operator_id, TASKS)


def test_unknown_task_or_operator_raises_keyerror():
    with pytest.raises(KeyError):
        ground_truth_note("T9", "O1", TASKS)
    with pytest.raises(KeyError):
        ground_truth_note("T1", "O7", TASKS)


def test_unknown_task_error_message_names_the_task_and_dir(tmp_path):
    with pytest.raises(KeyError) as exc:
        ground_truth_note("T9", "O1", tmp_path)
    assert exc.value.args[0] == f"no task file for 'T9' in {tmp_path}"


def test_unknown_operator_error_message_names_task_and_operator():
    with pytest.raises(KeyError) as exc:
        ground_truth_note("T1", "O7", TASKS)
    assert exc.value.args[0] == "T1: no ground-truth bullet for 'O7'"


def test_missing_ground_truth_section_error_names_the_matched_file(tmp_path):
    (tmp_path / "T9-only.md").write_text("no such section here\n")
    with pytest.raises(KeyError) as exc:
        ground_truth_note("T9", "O1", tmp_path)
    assert exc.value.args[0] == f"T9-only.md has no {_SECTION!r} section"


def test_missing_section_error_names_first_sorted_match_when_multiple_files_share_prefix(tmp_path):
    (tmp_path / "T9-aaa-first.md").write_text("no section in this one\n")
    (tmp_path / "T9-zzz-second.md").write_text("no section in this one either\n")
    with pytest.raises(KeyError) as exc:
        ground_truth_note("T9", "O1", tmp_path)
    # sorted() picks the alphabetically-first match; the error must name THAT file.
    assert exc.value.args[0] == f"T9-aaa-first.md has no {_SECTION!r} section"


def test_split_uses_maxsplit_one_not_greedy_or_reverse(tmp_path):
    # A second literal occurrence of the section marker embedded INLINE (not at the
    # start of a line) after the real one. split(_SECTION, 1) must keep everything
    # after the FIRST occurrence, including that embedded literal text verbatim --
    # split() with no maxsplit (over-greedy) or rsplit (from the wrong end) both
    # truncate or drop the O1 bullet.
    text = ("preamble\n" + _SECTION + "\n"
            "- O1 alpha " + _SECTION + " beta\n"
            "- O2 unrelated\n")
    (tmp_path / "T9-dup.md").write_text(text)
    note = ground_truth_note("T9", "O1", tmp_path)
    assert note == f"O1 alpha {_SECTION} beta"


def test_truncates_at_next_heading_line_after_the_section(tmp_path):
    text = ("preamble\n" + _SECTION + "\n"
            "- O1 keep this content\n"
            "## Next Heading\n"
            "- O1 should not appear DROPPED\n")
    (tmp_path / "T9-trunc.md").write_text(text)
    note = ground_truth_note("T9", "O1", tmp_path)
    assert note == "O1 keep this content"
    assert "DROPPED" not in note
