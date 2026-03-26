import curses
from unittest.mock import MagicMock, patch
import pytest
from rcli.components import choicecomponent
from rcli.enums import CHOICE
from rcli.brect import brect


SAMPLE_ENTRIES = [
    {"Name": "photos", "Size": 0, "ModTime": "2024-06-01T10:00:00Z", "IsDir": True},
    {"Name": "notes.txt", "Size": 2048, "ModTime": "2024-07-15T14:30:00Z", "IsDir": False},
    {"Name": "backup.tar.gz", "Size": 1073741824, "ModTime": "2024-01-20T08:00:00Z", "IsDir": False},
]


def make_stdscr(rows=40, cols=120):
    stdscr = MagicMock()
    stdscr.getmaxyx.return_value = (rows, cols)
    return stdscr


@pytest.fixture(autouse=True)
def patch_color_pair():
    with patch("curses.color_pair", return_value=1):
        yield


class TestChoiceComponentMetadata:
    def test_upload_keybinding(self):
        comp = choicecomponent(SAMPLE_ENTRIES, rect=brect(0, 0, 80, 20))
        comp.handleinput(ord("p"))
        assert comp.getChoice().choice == CHOICE.UPLOAD

    def test_download_keybinding(self):
        comp = choicecomponent(SAMPLE_ENTRIES, rect=brect(0, 0, 80, 20))
        comp.handleinput(ord("d"))
        assert comp.getChoice().choice == CHOICE.DOWNLOAD
        assert comp.getChoice().data == SAMPLE_ENTRIES[0]

    def test_draw_no_crash(self):
        stdscr = make_stdscr()
        comp = choicecomponent(SAMPLE_ENTRIES, back=True, rect=brect(1, 1, 80, 20))
        comp.draw(stdscr)
        assert stdscr.addstr.called

    def test_draw_dir_has_slash_suffix(self):
        stdscr = make_stdscr()
        comp = choicecomponent(SAMPLE_ENTRIES, rect=brect(0, 0, 80, 20))
        comp.draw(stdscr)
        # First entry is photos/ (dir, selected by default so has "> " prefix)
        first_call_content = stdscr.addstr.call_args_list[0][0][2]
        assert "photos/" in first_call_content

    def test_draw_dir_shows_dash_for_size(self):
        stdscr = make_stdscr()
        comp = choicecomponent(SAMPLE_ENTRIES, rect=brect(0, 0, 80, 20))
        comp.draw(stdscr)
        first_call_content = stdscr.addstr.call_args_list[0][0][2]
        # Dir should show "-" for size, not "0 B"
        assert "  -  " in first_call_content

    def test_draw_file_shows_formatted_size(self):
        stdscr = make_stdscr()
        comp = choicecomponent(SAMPLE_ENTRIES, rect=brect(0, 0, 80, 20))
        comp.draw(stdscr)
        # Second entry is notes.txt (2048 bytes = 2.0 KB)
        second_call_content = stdscr.addstr.call_args_list[1][0][2]
        assert "2.0 KB" in second_call_content

    def test_draw_shows_date(self):
        stdscr = make_stdscr()
        comp = choicecomponent(SAMPLE_ENTRIES, rect=brect(0, 0, 80, 20))
        comp.draw(stdscr)
        second_call_content = stdscr.addstr.call_args_list[1][0][2]
        assert "2024-07-15" in second_call_content

    def test_selected_returns_dict(self):
        comp = choicecomponent(SAMPLE_ENTRIES, rect=brect(0, 0, 80, 20))
        comp.handleinput(10)  # Enter
        result = comp.getChoice()
        assert result.choice == CHOICE.SELECTED
        assert result.data == SAMPLE_ENTRIES[0]

    def test_dir_colored_with_color_pair(self):
        stdscr = make_stdscr()
        comp = choicecomponent(SAMPLE_ENTRIES, rect=brect(0, 0, 80, 20))
        comp.draw(stdscr)
        # First entry is a dir - should use color_pair(1) = patched to 1
        first_call = stdscr.addstr.call_args_list[0]
        assert first_call[0][3] == 1

    def test_file_not_colored(self):
        stdscr = make_stdscr()
        comp = choicecomponent(SAMPLE_ENTRIES, rect=brect(0, 0, 80, 20))
        comp.elementIndex = 1  # Move to file entry
        comp.draw(stdscr)
        # Find the notes.txt call - it's a file, should not have color_pair
        for call in stdscr.addstr.call_args_list:
            content = call[0][2]
            if "notes.txt" in content:
                assert len(call[0]) == 3
                break


class TestChoiceComponentResize:
    def test_key_resize_sets_flag(self):
        comp = choicecomponent(SAMPLE_ENTRIES, rect=brect(0, 0, 80, 20))
        assert comp._needs_resize is False
        comp.handleinput(curses.KEY_RESIZE)
        assert comp._needs_resize is True

    def test_key_resize_does_not_change_selection(self):
        comp = choicecomponent(SAMPLE_ENTRIES, rect=brect(0, 0, 80, 20))
        comp.handleinput(curses.KEY_RESIZE)
        assert comp.getChoice().choice == CHOICE.NONE
        assert comp.elementIndex == 0

    def test_draw_after_resize_no_crash(self):
        stdscr = make_stdscr(30, 80)
        comp = choicecomponent(SAMPLE_ENTRIES, back=True, rect=brect(1, 1, 80, 20))
        comp.handleinput(curses.KEY_RESIZE)
        comp.draw(stdscr)
        assert stdscr.addstr.called
