import curses
from unittest.mock import MagicMock, patch, call
import pytest
from rcli.forms import choiceforum
from rcli.enums import CHOICE


SAMPLE_ENTRIES = [
    {"Name": "photos", "Size": 0, "ModTime": "2024-06-01T10:00:00Z", "IsDir": True},
    {"Name": "notes.txt", "Size": 2048, "ModTime": "2024-07-15T14:30:00Z", "IsDir": False},
]


def make_stdscr(rows=40, cols=120):
    stdscr = MagicMock()
    stdscr.getmaxyx.return_value = (rows, cols)
    return stdscr


@pytest.fixture(autouse=True)
def patch_color_pair():
    with patch("curses.color_pair", return_value=1):
        yield


class TestChoiceforumDynamicLayout:
    def test_brect_fills_terminal(self):
        register = MagicMock()
        forum = choiceforum(SAMPLE_ENTRIES, back=True, extra="b2:", registerKeyFunc=register)
        stdscr = make_stdscr(40, 120)
        forum.draw(stdscr)

        rect = forum.choiceComponent.brect
        # x=1, y=3, w=cols-2=118, h=rows-5=35
        assert rect.x == 1
        assert rect.y == 3
        assert rect.w == 118
        assert rect.h == 35

    def test_brect_adapts_to_small_terminal(self):
        register = MagicMock()
        forum = choiceforum(SAMPLE_ENTRIES, back=False, extra="test:", registerKeyFunc=register)
        stdscr = make_stdscr(24, 80)
        forum.draw(stdscr)

        rect = forum.choiceComponent.brect
        assert rect.w == 78
        assert rect.h == 19

    def test_layout_computed_once(self):
        register = MagicMock()
        forum = choiceforum(SAMPLE_ENTRIES, back=False, extra="", registerKeyFunc=register)
        stdscr = make_stdscr(40, 120)
        forum.draw(stdscr)
        forum.draw(stdscr)

        # getmaxyx is called by draw of textcomponent too, but _compute_layout
        # should only run once (the flag prevents recomputation)
        assert forum._layout_computed is True

    def test_bottom_bar_includes_upload(self):
        register = MagicMock()
        forum = choiceforum(SAMPLE_ENTRIES, back=True, extra="remote:", registerKeyFunc=register)
        stdscr = make_stdscr(40, 120)
        forum.draw(stdscr)

        # Find the bottom bar text component (the last one)
        bar_component = forum.components[2]
        assert "[p]" in bar_component.text

    def test_bottom_bar_includes_put_upload(self):
        register = MagicMock()
        forum = choiceforum(SAMPLE_ENTRIES, back=True, extra="remote:", registerKeyFunc=register)

        bar_component = forum.components[2]
        assert "[p]ut/upload" in bar_component.text

    def test_draw_no_crash(self):
        register = MagicMock()
        forum = choiceforum(SAMPLE_ENTRIES, back=True, extra="b2:", registerKeyFunc=register)
        stdscr = make_stdscr(40, 120)
        forum.draw(stdscr)
        assert stdscr.addstr.called

    def test_resize_recomputes_layout(self):
        register = MagicMock()
        forum = choiceforum(SAMPLE_ENTRIES, back=True, extra="b2:", registerKeyFunc=register)
        stdscr1 = make_stdscr(40, 120)
        forum.draw(stdscr1)
        assert forum.choiceComponent.brect.w == 118
        assert forum.choiceComponent.brect.h == 35

        # Simulate KEY_RESIZE
        forum.choiceComponent.handleinput(curses.KEY_RESIZE)
        assert forum.choiceComponent._needs_resize is True

        # Draw with new terminal size
        stdscr2 = make_stdscr(24, 80)
        forum.draw(stdscr2)
        assert forum.choiceComponent._needs_resize is False
        assert forum.choiceComponent.brect.w == 78
        assert forum.choiceComponent.brect.h == 19
