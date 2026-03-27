import curses
import pytest
from unittest.mock import patch, MagicMock, PropertyMock, call
from rcli.enums import SCENES


class TestConnectionTesting:
    @patch("rcli.cursedcli.time.sleep")
    @patch("rcli.cursedcli.rclonecache")
    @patch("rcli.cursedcli.rclone")
    @patch("rcli.cursedcli.curses")
    def test_connection_failure_exits_early(
        self, mock_curses, mock_rclone_cls, mock_cache_cls, mock_sleep
    ):
        """If test_connection returns False, main() exits without entering the browse loop."""
        # Setup mock rclone instance with failing connection
        mock_rc = MagicMock()
        mock_rc.test_connection.return_value = False
        mock_rclone_cls.return_value = mock_rc

        # Setup mock stdscr
        mock_stdscr = MagicMock()
        mock_stdscr.getmaxyx.return_value = (40, 120)
        mock_curses.initscr.return_value = mock_stdscr
        mock_curses.color_pair.return_value = 1

        from rcli.cursedcli import cursedcli

        cli = cursedcli("b2:", no_index=True)
        cli.main()

        # Connection was tested
        mock_rc.test_connection.assert_called_once_with("b2:", timeout=10)

        # rclonecache was never created (never got past connection test)
        mock_cache_cls.assert_not_called()

        # Error message was shown
        mock_stdscr.refresh.assert_called()

    @patch("rcli.cursedcli.time.sleep")
    @patch("rcli.cursedcli.rclonecache")
    @patch("rcli.cursedcli.rclone")
    @patch("rcli.cursedcli.curses")
    def test_connection_success_proceeds_to_browse(
        self, mock_curses, mock_rclone_cls, mock_cache_cls, mock_sleep
    ):
        """If test_connection returns True, main() creates cache and enters browse loop."""
        # Setup mock rclone instance with passing connection
        mock_rc = MagicMock()
        mock_rc.test_connection.return_value = True
        mock_rclone_cls.return_value = mock_rc

        # Setup mock stdscr — return 'q' to exit the browse loop immediately
        mock_stdscr = MagicMock()
        mock_stdscr.getmaxyx.return_value = (40, 120)
        mock_stdscr.getch.return_value = ord("q")
        mock_curses.initscr.return_value = mock_stdscr
        mock_curses.color_pair.return_value = 1

        mock_cache = MagicMock()
        mock_cache.listdir.return_value = [
            {"Name": "file.txt", "Size": 100, "ModTime": "2024-01-01T00:00:00Z", "IsDir": False}
        ]
        mock_cache_cls.return_value = mock_cache

        from rcli.cursedcli import cursedcli

        cli = cursedcli("b2:", no_index=True)
        cli.main()

        # Connection was tested
        mock_rc.test_connection.assert_called_once_with("b2:", timeout=10)

        # Cache was created (got past connection test)
        mock_cache_cls.assert_called_once()


class TestRemotePicker:
    @patch("rcli.cursedcli.time.sleep")
    @patch("rcli.cursedcli.rclonecache")
    @patch("rcli.cursedcli.remotepickerscene")
    @patch("rcli.cursedcli.choosefilescene")
    @patch("rcli.cursedcli.rclone")
    @patch("rcli.cursedcli.curses")
    def test_no_remote_starts_with_remote_picker(
        self, mock_curses, mock_rclone_cls, mock_choosefile_cls,
        mock_picker_cls, mock_cache_cls, mock_sleep
    ):
        """When remote=None, main() starts with remotepickerscene."""
        mock_stdscr = MagicMock()
        mock_stdscr.getmaxyx.return_value = (40, 120)
        mock_curses.initscr.return_value = mock_stdscr

        mock_rc = MagicMock()
        mock_rc.test_connection.return_value = True
        mock_rclone_cls.return_value = mock_rc

        mock_cache = MagicMock()
        mock_cache_cls.return_value = mock_cache

        # Remote picker selects "b2:" then transitions to CHOOSE_FILE
        mock_picker = MagicMock()
        mock_picker.getNextScene.return_value = SCENES.CHOOSE_FILE
        mock_picker.getdata.return_value = "b2:"
        mock_picker_cls.return_value = mock_picker

        # Browse scene immediately exits
        mock_browse = MagicMock()
        mock_browse.getNextScene.return_value = SCENES.EXIT
        mock_choosefile_cls.return_value = mock_browse

        from rcli.cursedcli import cursedcli

        cli = cursedcli(None, no_index=True)
        cli.main()

        # Remote picker was created with an rclone instance
        mock_picker_cls.assert_called_once_with(mock_rc)

        # After picker selects b2:, connection test runs and browse starts
        mock_rc.test_connection.assert_called_once_with("b2:", timeout=10)
        mock_choosefile_cls.assert_called_once_with("b2:", mock_cache)

    @patch("rcli.cursedcli.time.sleep")
    @patch("rcli.cursedcli.rclonecache")
    @patch("rcli.cursedcli.remotepickerscene")
    @patch("rcli.cursedcli.rclone")
    @patch("rcli.cursedcli.curses")
    def test_no_remote_picker_quit_exits(
        self, mock_curses, mock_rclone_cls, mock_picker_cls,
        mock_cache_cls, mock_sleep
    ):
        """When remote=None and user quits the picker, main() returns without browsing."""
        mock_stdscr = MagicMock()
        mock_stdscr.getmaxyx.return_value = (40, 120)
        mock_curses.initscr.return_value = mock_stdscr

        mock_rc = MagicMock()
        mock_rclone_cls.return_value = mock_rc

        mock_picker = MagicMock()
        mock_picker.getNextScene.return_value = SCENES.EXIT
        mock_picker_cls.return_value = mock_picker

        from rcli.cursedcli import cursedcli

        cli = cursedcli(None, no_index=True)
        cli.main()

        mock_picker_cls.assert_called_once_with(mock_rc)
        # Connection test never runs
        mock_rc.test_connection.assert_not_called()
        # Cache never created
        mock_cache_cls.assert_not_called()


class TestMainLoopTransitions:
    """Test scene transition sequence in the main loop."""

    def _setup_connection(self, mock_curses, mock_rclone_cls, mock_cache_cls):
        """Helper to set up successful connection and return cache/stdscr mocks."""
        mock_rc = MagicMock()
        mock_rc.test_connection.return_value = True
        mock_rclone_cls.return_value = mock_rc

        mock_cache = MagicMock()
        mock_cache_cls.return_value = mock_cache

        mock_stdscr = MagicMock()
        mock_stdscr.getmaxyx.return_value = (40, 120)
        mock_curses.initscr.return_value = mock_stdscr

        return mock_cache, mock_stdscr

    @patch("rcli.cursedcli.time.sleep")
    @patch("rcli.cursedcli.uploadscene")
    @patch("rcli.cursedcli.downloadscene")
    @patch("rcli.cursedcli.fuzzyscene")
    @patch("rcli.cursedcli.choosefilescene")
    @patch("rcli.cursedcli.rclonecache")
    @patch("rcli.cursedcli.rclone")
    @patch("rcli.cursedcli.curses")
    def test_browse_download_fuzzy_exit(
        self, mock_curses, mock_rclone_cls, mock_cache_cls,
        mock_choosefile_cls, mock_fuzzy_cls, mock_download_cls,
        mock_upload_cls, mock_sleep,
    ):
        """Simulate: browse → download → back → fuzzy → back → exit."""
        mock_cache, _ = self._setup_connection(
            mock_curses, mock_rclone_cls, mock_cache_cls
        )

        # Scene 1: Browse root → download a file in docs/
        scene1 = MagicMock()
        scene1.getNextScene.return_value = SCENES.DOWNLOAD
        scene1.getdata.return_value = ("docs/readme.txt", False)
        scene1.folderDir = ["docs"]

        # Scene 2: Download completes → back to CHOOSE_FILE
        scene2 = MagicMock()
        scene2.getNextScene.return_value = SCENES.CHOOSE_FILE
        scene2.getdata.return_value = "docs/_"

        # Scene 3: Browse docs/ → fuzzy search
        scene3 = MagicMock()
        scene3.getNextScene.return_value = SCENES.FUZZY_SEARCH
        scene3.folderDir = ["docs"]

        # Scene 4: Fuzzy → select path → CHOOSE_FILE
        scene4 = MagicMock()
        scene4.getNextScene.return_value = SCENES.CHOOSE_FILE
        scene4.getdata.return_value = "photos/vacation/img.jpg"

        # Scene 5: Browse → EXIT
        scene5 = MagicMock()
        scene5.getNextScene.return_value = SCENES.EXIT

        mock_choosefile_cls.side_effect = [scene1, scene3, scene5]
        mock_download_cls.return_value = scene2
        mock_fuzzy_cls.return_value = scene4

        from rcli.cursedcli import cursedcli

        cli = cursedcli("b2:", no_index=True)
        cli.main()

        # Verify choosefilescene construction params
        cf_calls = mock_choosefile_cls.call_args_list
        assert cf_calls[0] == call("b2:", mock_cache)  # initial: root
        assert cf_calls[1] == call("b2:", mock_cache, ["docs"])  # after download
        assert cf_calls[2] == call(
            "b2:", mock_cache, ["photos", "vacation"]
        )  # after fuzzy

        # Download scene: file (not dir), so destination is "."
        mock_download_cls.assert_called_once_with(
            "b2:docs/readme.txt", ".", ["docs"]
        )

        # Fuzzy scene: receives remote, cache, folderDir, and search_index (None when no_index=True)
        mock_fuzzy_cls.assert_called_once_with("b2:", mock_cache, ["docs"], None)

    @patch("rcli.cursedcli.time.sleep")
    @patch("rcli.cursedcli.uploadscene")
    @patch("rcli.cursedcli.downloadscene")
    @patch("rcli.cursedcli.fuzzyscene")
    @patch("rcli.cursedcli.choosefilescene")
    @patch("rcli.cursedcli.rclonecache")
    @patch("rcli.cursedcli.rclone")
    @patch("rcli.cursedcli.curses")
    def test_upload_transition(
        self, mock_curses, mock_rclone_cls, mock_cache_cls,
        mock_choosefile_cls, mock_fuzzy_cls, mock_download_cls,
        mock_upload_cls, mock_sleep,
    ):
        """Simulate: browse → upload → back → exit."""
        mock_cache, _ = self._setup_connection(
            mock_curses, mock_rclone_cls, mock_cache_cls
        )

        # Scene 1: Browse in photos/ → UPLOAD
        scene1 = MagicMock()
        scene1.getNextScene.return_value = SCENES.UPLOAD
        scene1.folderDir = ["photos"]

        # Scene 2: Upload completes → CHOOSE_FILE
        scene2 = MagicMock()
        scene2.getNextScene.return_value = SCENES.CHOOSE_FILE
        scene2.getdata.return_value = "photos/_"

        # Scene 3: Browse → EXIT
        scene3 = MagicMock()
        scene3.getNextScene.return_value = SCENES.EXIT

        mock_choosefile_cls.side_effect = [scene1, scene3]
        mock_upload_cls.return_value = scene2

        from rcli.cursedcli import cursedcli

        cli = cursedcli("b2:", no_index=True)
        cli.main()

        # Upload scene got correct params: remote, cache, folderDir
        mock_upload_cls.assert_called_once_with("b2:", mock_cache, ["photos"])

    @patch("rcli.cursedcli.time.sleep")
    @patch("rcli.cursedcli.uploadscene")
    @patch("rcli.cursedcli.downloadscene")
    @patch("rcli.cursedcli.fuzzyscene")
    @patch("rcli.cursedcli.choosefilescene")
    @patch("rcli.cursedcli.rclonecache")
    @patch("rcli.cursedcli.rclone")
    @patch("rcli.cursedcli.curses")
    def test_refresh_invalidates_current_dir_only(
        self, mock_curses, mock_rclone_cls, mock_cache_cls,
        mock_choosefile_cls, mock_fuzzy_cls, mock_download_cls,
        mock_upload_cls, mock_sleep,
    ):
        """Refresh invalidates only the current directory's cache."""
        mock_cache, _ = self._setup_connection(
            mock_curses, mock_rclone_cls, mock_cache_cls
        )

        # Scene 1: Browse in docs/archive/ → REFRESH
        scene1 = MagicMock()
        scene1.getNextScene.return_value = SCENES.REFRESH_DATABASE
        scene1.folderDir = ["docs", "archive"]

        # Scene 2: After refresh → EXIT
        scene2 = MagicMock()
        scene2.getNextScene.return_value = SCENES.EXIT

        mock_choosefile_cls.side_effect = [scene1, scene2]

        from rcli.cursedcli import cursedcli

        cli = cursedcli("b2:", no_index=True)
        cli.main()

        # Cache invalidated for current dir only
        mock_cache.invalidate.assert_called_once_with("b2:", "docs/archive/")

        # Scene recreated with same folder
        assert mock_choosefile_cls.call_args_list[1] == call(
            "b2:", mock_cache, ["docs", "archive"]
        )

    @patch("rcli.cursedcli.time.sleep")
    @patch("rcli.cursedcli.uploadscene")
    @patch("rcli.cursedcli.downloadscene")
    @patch("rcli.cursedcli.fuzzyscene")
    @patch("rcli.cursedcli.choosefilescene")
    @patch("rcli.cursedcli.rclonecache")
    @patch("rcli.cursedcli.rclone")
    @patch("rcli.cursedcli.curses")
    def test_refresh_root_passes_empty_path(
        self, mock_curses, mock_rclone_cls, mock_cache_cls,
        mock_choosefile_cls, mock_fuzzy_cls, mock_download_cls,
        mock_upload_cls, mock_sleep,
    ):
        """Refreshing at root passes empty string to cache.invalidate."""
        mock_cache, _ = self._setup_connection(
            mock_curses, mock_rclone_cls, mock_cache_cls
        )

        scene1 = MagicMock()
        scene1.getNextScene.return_value = SCENES.REFRESH_DATABASE
        scene1.folderDir = []

        scene2 = MagicMock()
        scene2.getNextScene.return_value = SCENES.EXIT

        mock_choosefile_cls.side_effect = [scene1, scene2]

        from rcli.cursedcli import cursedcli

        cli = cursedcli("b2:", no_index=True)
        cli.main()

        mock_cache.invalidate.assert_called_once_with("b2:", "")

    @patch("rcli.cursedcli.time.sleep")
    @patch("rcli.cursedcli.uploadscene")
    @patch("rcli.cursedcli.downloadscene")
    @patch("rcli.cursedcli.fuzzyscene")
    @patch("rcli.cursedcli.choosefilescene")
    @patch("rcli.cursedcli.rclonecache")
    @patch("rcli.cursedcli.rclone")
    @patch("rcli.cursedcli.curses")
    def test_download_directory_uses_folder_path(
        self, mock_curses, mock_rclone_cls, mock_cache_cls,
        mock_choosefile_cls, mock_fuzzy_cls, mock_download_cls,
        mock_upload_cls, mock_sleep,
    ):
        """Downloading a directory passes the folder path as destination."""
        mock_cache, _ = self._setup_connection(
            mock_curses, mock_rclone_cls, mock_cache_cls
        )

        # Browse root, download a directory
        scene1 = MagicMock()
        scene1.getNextScene.return_value = SCENES.DOWNLOAD
        scene1.getdata.return_value = ("photos/", True)  # IsDir=True
        scene1.folderDir = []

        # Download scene → EXIT
        scene2 = MagicMock()
        scene2.getNextScene.return_value = SCENES.EXIT
        mock_download_cls.return_value = scene2

        mock_choosefile_cls.side_effect = [scene1]

        from rcli.cursedcli import cursedcli

        cli = cursedcli("b2:", no_index=True)
        cli.main()

        # For directory download, destination is the folder path, not "."
        mock_download_cls.assert_called_once_with("b2:photos/", "photos/", [])


class TestKeyResize:
    @patch("rcli.cursedcli.time.sleep")
    @patch("rcli.cursedcli.rclonecache")
    @patch("rcli.cursedcli.rclone")
    @patch("rcli.cursedcli.curses")
    def test_key_resize_no_crash(
        self, mock_curses, mock_rclone_cls, mock_cache_cls, mock_sleep
    ):
        """KEY_RESIZE followed by quit does not crash."""
        mock_rc = MagicMock()
        mock_rc.test_connection.return_value = True
        mock_rclone_cls.return_value = mock_rc

        mock_stdscr = MagicMock()
        mock_stdscr.getmaxyx.return_value = (40, 120)
        mock_curses.initscr.return_value = mock_stdscr
        mock_curses.color_pair.return_value = 1
        mock_curses.KEY_RESIZE = curses.KEY_RESIZE

        mock_cache = MagicMock()
        mock_cache.listdir.return_value = [
            {"Name": "file.txt", "Size": 100, "ModTime": "2024-01-01T00:00:00Z", "IsDir": False}
        ]
        mock_cache_cls.return_value = mock_cache

        # getch returns KEY_RESIZE first, then 'q' to quit
        mock_stdscr.getch.side_effect = [curses.KEY_RESIZE, ord("q")]

        from rcli.cursedcli import cursedcli

        cli = cursedcli("b2:", no_index=True)
        cli.main()

        # resizeterm was called (at least once per loop iteration)
        mock_curses.resizeterm.assert_called()
        # It was called with the terminal dimensions
        mock_curses.resizeterm.assert_any_call(40, 120)
