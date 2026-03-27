"""End-to-end integration smoke test for rcli.

Mocks subprocess at the boundary and drives the full UI via a programmed
getch sequence, letting real scenes/forms/components/cache run.
"""

import json
import os
import pytest
from unittest.mock import patch, MagicMock
from rcli.cursedcli import cursedcli


ROOT_ENTRIES = [
    {
        "Path": "documents",
        "Name": "documents",
        "Size": -1,
        "MimeType": "inode/directory",
        "ModTime": "2024-01-15T10:30:00Z",
        "IsDir": True,
    },
    {
        "Path": "photo.jpg",
        "Name": "photo.jpg",
        "Size": 1048576,
        "MimeType": "image/jpeg",
        "ModTime": "2024-02-20T14:45:00Z",
        "IsDir": False,
    },
]

SUB_ENTRIES = [
    {
        "Path": "readme.md",
        "Name": "readme.md",
        "Size": 512,
        "MimeType": "text/plain",
        "ModTime": "2024-03-01T08:00:00Z",
        "IsDir": False,
    },
]


def _make_fake_popen(popen_commands):
    """Fake Popen: records commands, returns appropriate mock processes."""

    def fake_popen(args, **kwargs):
        popen_commands.append(list(args))
        process = MagicMock()
        process.stdout = MagicMock()
        process.stdout.read.return_value = ""  # commandcomponent reads this
        process.communicate.return_value = ("", "")  # rclone class reads this

        if "lsjson" in args:
            idx = args.index("lsjson")
            target = args[idx + 1]
            if target == "b2:":
                output = json.dumps(ROOT_ENTRIES)
            elif target == "b2:documents/":
                output = json.dumps(SUB_ENTRIES)
            else:
                output = "[]"
            process.communicate.return_value = (output, "")

        return process

    return fake_popen


def _make_fake_run(run_commands):
    """Fake subprocess.run: records calls, returns success."""

    def fake_run(args, **kwargs):
        run_commands.append(list(args))
        result = MagicMock()
        result.returncode = 0
        return result

    return fake_run


def _make_mock_stdscr(getch_sequence):
    """Mock stdscr with programmed getch sequence; falls back to 'q'."""
    index = [0]
    mock = MagicMock()
    mock.getmaxyx.return_value = (40, 120)

    def _getch():
        if index[0] < len(getch_sequence):
            key = getch_sequence[index[0]]
            index[0] += 1
            return key
        return ord("q")

    mock.getch.side_effect = _getch
    return mock


class TestEndToEndSmoke:
    """Full-session integration test."""

    def test_full_session(self, tmp_path):
        """
        Simulate: startup → connection test → browse root → enter folder →
        back → fuzzy search → download → upload → exit.

        Verify: correct rclone commands in order, no exceptions, cache correct.
        """
        popen_commands = []
        run_commands = []

        cache_dir = tmp_path / "rcli"
        cache_dir.mkdir()
        cache_file = str(cache_dir / "cache.json")

        # getch keys consumed by scenes in order:
        #   1. Enter      — select documents/ (enter folder)
        #   2. h          — go back to root
        #   3. /          — open fuzzy search
        #   4. Esc        — exit fuzzy (return to root)
        #   5. d          — download first entry (documents/ dir)
        #      (download command phase — no getch consumed)
        #   6. p          — start upload
        #   7. f          — type local path character
        #   8. Enter      — confirm upload
        #      (upload command phase — no getch consumed)
        #   9. q          — quit
        getch_keys = [
            10, ord("h"), ord("/"), 27, ord("d"),
            ord("p"), ord("f"), 10, ord("q"),
        ]
        mock_stdscr = _make_mock_stdscr(getch_keys)

        _orig_expanduser = os.path.expanduser

        def fake_expanduser(path):
            if "~/.cache/rcli" in path:
                return path.replace("~/.cache/rcli", str(cache_dir))
            return _orig_expanduser(path)

        with patch("rcli.cursedcli.curses") as mock_curses, \
             patch("subprocess.Popen", side_effect=_make_fake_popen(popen_commands)), \
             patch("subprocess.run", side_effect=_make_fake_run(run_commands)), \
             patch("shutil.which", return_value="/usr/bin/rclone"), \
             patch("time.sleep"), \
             patch("os.path.expanduser", side_effect=fake_expanduser), \
             patch("curses.color_pair", return_value=1):

            mock_curses.initscr.return_value = mock_stdscr
            mock_curses.color_pair.return_value = 1
            mock_curses.A_NORMAL = 0
            mock_curses.A_REVERSE = 1 << 18
            mock_curses.error = Exception

            cli = cursedcli("b2:", no_index=True)
            cli.main()

        # --- Verify connection test (subprocess.run) ---
        assert run_commands[0] == ["rclone", "lsd", "b2:", "--max-depth", "1"]

        # --- Verify Popen commands in order ---
        # 1. browse root
        assert popen_commands[0] == ["rclone", "lsjson", "b2:", "--max-depth", "1"]
        # 2. enter documents/
        assert popen_commands[1] == ["rclone", "lsjson", "b2:documents/", "--max-depth", "1"]
        # 3. download documents/ directory
        assert popen_commands[2] == ["rclone", "copy", "-P", "b2:documents", "documents"]
        # 4. upload local file "f" to root
        assert popen_commands[3] == ["rclone", "copy", "-P", "f", "b2:"]
        # 5. root re-fetched after upload cache invalidation
        assert popen_commands[4] == ["rclone", "lsjson", "b2:", "--max-depth", "1"]
        assert len(popen_commands) == 5

        # --- No unhandled exceptions (reaching this point is the proof) ---

        # --- Verify cache populated correctly ---
        assert os.path.exists(cache_file)
        with open(cache_file) as f:
            cache_data = json.load(f)

        assert "b2:" in cache_data
        assert "b2:documents/" in cache_data
        assert cache_data["b2:"]["entries"] == ROOT_ENTRIES
        assert cache_data["b2:documents/"]["entries"] == SUB_ENTRIES
