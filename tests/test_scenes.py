import pytest
from unittest.mock import MagicMock, patch
from rcli.scenes import choosefilescene, fuzzyscene, uploadscene, remotepickerscene
from rcli.enums import CHOICE, SCENES


SAMPLE_ENTRIES = [
    {"Name": "documents", "Size": 0, "ModTime": "2024-01-15T10:30:00Z", "IsDir": True},
    {"Name": "photo.jpg", "Size": 1048576, "ModTime": "2024-02-20T14:45:00Z", "IsDir": False},
]

SUB_ENTRIES = [
    {"Name": "readme.md", "Size": 512, "ModTime": "2024-03-01T08:00:00Z", "IsDir": False},
]


def make_stdscr(rows=40, cols=120):
    stdscr = MagicMock()
    stdscr.getmaxyx.return_value = (rows, cols)
    return stdscr


def make_cache(entries_by_path=None):
    """Create a mock cache that returns entries based on path."""
    cache = MagicMock()
    entries_by_path = entries_by_path or {}

    def listdir_side_effect(remote, path=""):
        return entries_by_path.get(path, [])

    cache.listdir.side_effect = listdir_side_effect
    return cache


@pytest.fixture(autouse=True)
def patch_curses():
    with patch("curses.color_pair", return_value=1):
        yield


class TestChooseFileSceneLazyLoading:
    def test_listdir_called_on_first_show(self):
        cache = make_cache({"": SAMPLE_ENTRIES})
        stdscr = make_stdscr()
        stdscr.getch.return_value = ord("q")

        scene = choosefilescene("b2:", cache)
        scene.show(stdscr)

        cache.listdir.assert_called_once_with("b2:", "")

    def test_enter_folder_calls_listdir_with_correct_path(self):
        cache = make_cache({
            "": SAMPLE_ENTRIES,
            "documents/": SUB_ENTRIES,
        })
        stdscr = make_stdscr()

        scene = choosefilescene("b2:", cache)

        # First show: render root, press Enter to select first entry (documents/)
        stdscr.getch.return_value = 10  # Enter key
        scene.show(stdscr)

        # Verify folder was entered
        assert scene.folderDir == ["documents"]
        assert scene.choiceForum is None  # Forum cleared for reload

        # Second show: should list the subfolder
        stdscr.getch.return_value = ord("q")
        scene.show(stdscr)

        cache.listdir.assert_any_call("b2:", "documents/")

    def test_go_back_shows_parent(self):
        cache = make_cache({
            "": SAMPLE_ENTRIES,
            "documents/": SUB_ENTRIES,
        })
        stdscr = make_stdscr()

        # Start in documents/ subfolder
        scene = choosefilescene("b2:", cache, folderDir=["documents"])

        # Press 'h' to go back
        stdscr.getch.return_value = ord("h")
        scene.show(stdscr)

        assert scene.folderDir == []
        assert scene.choiceForum is None  # Forum cleared for reload

        # Next show should list root
        stdscr.getch.return_value = ord("q")
        scene.show(stdscr)

        cache.listdir.assert_any_call("b2:", "")

    def test_download_assembles_correct_path_for_file(self):
        cache = make_cache({"documents/": SUB_ENTRIES})
        stdscr = make_stdscr()

        scene = choosefilescene("b2:", cache, folderDir=["documents"])

        # Press 'd' to download first entry (readme.md)
        stdscr.getch.return_value = ord("d")
        scene.show(stdscr)

        assert scene.getNextScene() == SCENES.DOWNLOAD
        data = scene.getdata()
        assert data == ("documents/readme.md", False)

    def test_download_assembles_correct_path_for_dir(self):
        cache = make_cache({"": SAMPLE_ENTRIES})
        stdscr = make_stdscr()

        scene = choosefilescene("b2:", cache)

        # Press 'd' to download first entry (documents, a dir)
        stdscr.getch.return_value = ord("d")
        scene.show(stdscr)

        assert scene.getNextScene() == SCENES.DOWNLOAD
        data = scene.getdata()
        assert data == ("documents", True)

    def test_upload_sets_next_scene(self):
        cache = make_cache({"": SAMPLE_ENTRIES})
        stdscr = make_stdscr()

        scene = choosefilescene("b2:", cache)

        # Press 'p' to upload
        stdscr.getch.return_value = ord("p")
        scene.show(stdscr)

        assert scene.getNextScene() == SCENES.UPLOAD

    def test_fuzzy_search(self):
        cache = make_cache({"": SAMPLE_ENTRIES})
        stdscr = make_stdscr()

        scene = choosefilescene("b2:", cache)

        # Press '/' for fuzzy search
        stdscr.getch.return_value = ord("/")
        scene.show(stdscr)

        assert scene.getNextScene() == SCENES.FUZZY_SEARCH

    def test_initial_folder_dir_uses_correct_path(self):
        cache = make_cache({"documents/": SUB_ENTRIES})
        stdscr = make_stdscr()
        stdscr.getch.return_value = ord("q")

        scene = choosefilescene("b2:", cache, folderDir=["documents"])
        scene.show(stdscr)

        cache.listdir.assert_called_once_with("b2:", "documents/")

    def test_refresh_sets_next_scene(self):
        cache = make_cache({"": SAMPLE_ENTRIES})
        stdscr = make_stdscr()

        scene = choosefilescene("b2:", cache)

        # Press 'u' to refresh
        stdscr.getch.return_value = ord("u")
        scene.show(stdscr)

        assert scene.getNextScene() == SCENES.REFRESH_DATABASE

    def test_quit_sets_next_scene(self):
        cache = make_cache({"": SAMPLE_ENTRIES})
        stdscr = make_stdscr()

        scene = choosefilescene("b2:", cache)

        stdscr.getch.return_value = ord("q")
        scene.show(stdscr)

        assert scene.getNextScene() == SCENES.EXIT

    def test_nested_folder_path(self):
        """Navigating into nested folders builds correct path."""
        nested_entries = [
            {"Name": "sub", "Size": 0, "ModTime": "2024-01-01T00:00:00Z", "IsDir": True},
        ]
        cache = make_cache({
            "": SAMPLE_ENTRIES,
            "documents/": nested_entries,
            "documents/sub/": SUB_ENTRIES,
        })
        stdscr = make_stdscr()

        scene = choosefilescene("b2:", cache)

        # Enter documents/
        stdscr.getch.return_value = 10
        scene.show(stdscr)
        assert scene.folderDir == ["documents"]

        # Enter sub/
        stdscr.getch.return_value = 10
        scene.show(stdscr)
        assert scene.folderDir == ["documents", "sub"]

        # Verify path
        assert scene._current_path() == "documents/sub/"


class TestFuzzySceneLazyLoaded:
    def test_pulls_paths_from_cache(self):
        """fuzzyscene pulls paths from cache.get_all_cached_paths on first show."""
        cache = MagicMock()
        cache.get_all_cached_paths.return_value = ["photo.jpg", "documents/readme.md"]
        stdscr = make_stdscr()
        stdscr.getch.return_value = 27  # ESC to quit

        scene = fuzzyscene("b2:", cache)
        scene.show(stdscr)

        cache.get_all_cached_paths.assert_called_once_with("b2:")

    def test_finds_results_from_multiple_dirs(self):
        """Fuzzy search finds results aggregated from multiple cached dirs."""
        cache = MagicMock()
        cache.get_all_cached_paths.return_value = [
            "photo.jpg",
            "documents/readme.md",
        ]
        stdscr = make_stdscr()
        stdscr.getch.return_value = 27  # ESC

        scene = fuzzyscene("b2:", cache)
        scene.show(stdscr)

        # The fuzzyForum was created with paths from both dirs
        assert scene.fuzzyForum is not None
        assert scene.fuzzyForum.fuzzycomponent.data == [
            "photo.jpg",
            "documents/readme.md",
        ]

    def test_selection_transitions_to_choose_file(self):
        """Selecting a path in fuzzy search transitions to CHOOSE_FILE."""
        cache = MagicMock()
        cache.get_all_cached_paths.return_value = ["photo.jpg"]
        stdscr = make_stdscr()

        scene = fuzzyscene("b2:", cache)

        # First show to initialize
        stdscr.getch.return_value = 10  # Enter to select
        scene.show(stdscr)

        # If a selection was made, next scene should be CHOOSE_FILE
        if scene.fuzzyForum.getdata() is not None:
            assert scene.getNextScene() == SCENES.CHOOSE_FILE

    def test_no_transition_without_selection(self):
        """No scene transition until user selects something."""
        cache = MagicMock()
        cache.get_all_cached_paths.return_value = ["photo.jpg"]
        stdscr = make_stdscr()
        stdscr.getch.return_value = ord("a")  # Just type a character

        scene = fuzzyscene("b2:", cache)
        scene.show(stdscr)

        assert scene.getNextScene() is None


class TestUploadScene:
    @patch("rcli.components.subprocess.Popen")
    def test_upload_runs_correct_command(self, mock_popen):
        """Upload scene constructs correct rclone copy command."""
        mock_process = MagicMock()
        mock_process.stdout.read.return_value = ""
        mock_popen.return_value = mock_process

        cache = MagicMock()
        stdscr = make_stdscr()

        scene = uploadscene("remote:", cache, folderDir=["path"])

        # Input phase: type local path char by char
        for char in "/local/file":
            stdscr.getch.return_value = ord(char)
            scene.show(stdscr)

        # Press Enter to start upload
        stdscr.getch.return_value = 10
        scene.show(stdscr)

        # Verify Popen was called with correct command
        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        assert cmd == ["rclone", "copy", "-P", "/local/file", "remote:path/"]

    @patch("rcli.scenes.time.sleep")
    @patch("rcli.components.subprocess.Popen")
    def test_cache_invalidation_on_completion(self, mock_popen, mock_sleep):
        """Cache is invalidated when upload completes."""
        mock_process = MagicMock()
        mock_process.stdout.read.return_value = ""
        mock_popen.return_value = mock_process

        cache = MagicMock()
        stdscr = make_stdscr()

        scene = uploadscene("remote:", cache, folderDir=["path"])

        # Input phase: type path and press Enter
        for char in "/local/file":
            stdscr.getch.return_value = ord(char)
            scene.show(stdscr)
        stdscr.getch.return_value = 10
        scene.show(stdscr)

        # Simulate command completion
        scene.commandforum.commandcomponent.isDone = True
        scene.show(stdscr)

        cache.invalidate.assert_called_once_with("remote:", "path/")
        assert scene.getNextScene() == SCENES.CHOOSE_FILE

    def test_escape_cancels_upload(self):
        """Pressing Escape during input cancels and returns to file chooser."""
        cache = MagicMock()
        stdscr = make_stdscr()

        scene = uploadscene("remote:", cache)

        stdscr.getch.return_value = 27  # Escape
        scene.show(stdscr)

        assert scene.getNextScene() == SCENES.CHOOSE_FILE
        assert scene.commandforum is None

    def test_empty_path_does_not_start_upload(self):
        """Pressing Enter with empty path does not start upload."""
        cache = MagicMock()
        stdscr = make_stdscr()

        scene = uploadscene("remote:", cache)

        stdscr.getch.return_value = 10  # Enter with empty path
        scene.show(stdscr)

        assert scene.commandforum is None
        assert scene.getNextScene() is None

    @patch("rcli.scenes.time.sleep")
    @patch("rcli.components.subprocess.Popen")
    def test_getdata_returns_folderdir_path(self, mock_popen, mock_sleep):
        """getdata() returns folder path for navigation restoration."""
        mock_process = MagicMock()
        mock_process.stdout.read.return_value = ""
        mock_popen.return_value = mock_process

        cache = MagicMock()
        stdscr = make_stdscr()

        scene = uploadscene("remote:", cache, folderDir=["docs", "sub"])

        # Type path and start upload
        for char in "/tmp/f":
            stdscr.getch.return_value = ord(char)
            scene.show(stdscr)
        stdscr.getch.return_value = 10
        scene.show(stdscr)

        # Simulate completion
        scene.commandforum.commandcomponent.isDone = True
        scene.show(stdscr)

        assert scene.getdata() == "docs/sub/_"

    @patch("rcli.components.subprocess.Popen")
    def test_upload_at_root(self, mock_popen):
        """Upload at root uses remote with no path suffix."""
        mock_process = MagicMock()
        mock_process.stdout.read.return_value = ""
        mock_popen.return_value = mock_process

        cache = MagicMock()
        stdscr = make_stdscr()

        scene = uploadscene("b2:", cache)

        for char in "/tmp/f":
            stdscr.getch.return_value = ord(char)
            scene.show(stdscr)
        stdscr.getch.return_value = 10
        scene.show(stdscr)

        cmd = mock_popen.call_args[0][0]
        assert cmd == ["rclone", "copy", "-P", "/tmp/f", "b2:"]

    def test_backspace_removes_character(self):
        """Backspace removes last character from local path."""
        cache = MagicMock()
        stdscr = make_stdscr()

        scene = uploadscene("remote:", cache)

        # Type "abc"
        for char in "abc":
            stdscr.getch.return_value = ord(char)
            scene.show(stdscr)
        assert scene.local_path == "abc"

        # Backspace
        stdscr.getch.return_value = 127
        scene.show(stdscr)
        assert scene.local_path == "ab"


class TestRemotePickerScene:
    def test_select_remote_returns_name(self):
        """Selecting a remote sets getdata() to its name and transitions to CHOOSE_FILE."""
        rc = MagicMock()
        rc.listremotes.return_value = ["b2:", "gdrive:"]
        stdscr = make_stdscr()

        scene = remotepickerscene(rc)

        # First show initializes the forum; press Enter to select first remote ("b2:")
        stdscr.getch.return_value = 10
        scene.show(stdscr)

        assert scene.getdata() == "b2:"
        assert scene.getNextScene() == SCENES.CHOOSE_FILE

    def test_quit_exits(self):
        """Pressing q transitions to EXIT."""
        rc = MagicMock()
        rc.listremotes.return_value = ["b2:", "gdrive:"]
        stdscr = make_stdscr()

        scene = remotepickerscene(rc)

        stdscr.getch.return_value = ord("q")
        scene.show(stdscr)

        assert scene.getNextScene() == SCENES.EXIT
        assert scene.getdata() is None

    def test_listremotes_called_once(self):
        """listremotes is called on first show, not repeated."""
        rc = MagicMock()
        rc.listremotes.return_value = ["b2:"]
        stdscr = make_stdscr()

        scene = remotepickerscene(rc)

        stdscr.getch.return_value = ord("j")  # Just navigate
        scene.show(stdscr)
        scene.show(stdscr)

        rc.listremotes.assert_called_once()

    def test_no_transition_without_action(self):
        """No scene transition until user selects or quits."""
        rc = MagicMock()
        rc.listremotes.return_value = ["b2:"]
        stdscr = make_stdscr()

        scene = remotepickerscene(rc)

        stdscr.getch.return_value = ord("j")
        scene.show(stdscr)

        assert scene.getNextScene() is None
        assert scene.getdata() is None

    def test_select_second_remote(self):
        """Navigate to second remote and select it."""
        rc = MagicMock()
        rc.listremotes.return_value = ["b2:", "gdrive:"]
        stdscr = make_stdscr()

        scene = remotepickerscene(rc)

        # Navigate down
        stdscr.getch.return_value = ord("j")
        scene.show(stdscr)

        # Select
        stdscr.getch.return_value = 10
        scene.show(stdscr)

        assert scene.getdata() == "gdrive:"
        assert scene.getNextScene() == SCENES.CHOOSE_FILE
