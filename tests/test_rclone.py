import json
import os
import time
from unittest.mock import patch, MagicMock

import pytest

from rcli.rclone import check_rclone_available, rclone, rclonecache


class TestCheckRcloneAvailable:
    """Verify check_rclone_available raises when rclone is missing."""

    def test_raises_when_rclone_not_found(self):
        with patch("rcli.rclone.shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="rclone is not installed"):
                check_rclone_available()

    def test_passes_when_rclone_found(self):
        with patch("rcli.rclone.shutil.which", return_value="/usr/bin/rclone"):
            check_rclone_available()  # should not raise

    def test_rclonecache_init_raises_when_rclone_missing(self):
        with patch("rcli.rclone.shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="rclone is not installed"):
                rclonecache()


class TestRcloneSubprocessRun:
    """Verify rclone() uses subprocess.run, not os.system."""

    def test_rclone_calls_subprocess_run(self, mock_subprocess):
        r = rclone()
        r.rclone(["copy", "-P", "/local", "remote:path"])
        assert len(mock_subprocess) == 1
        assert mock_subprocess[0]["args"] == [
            "rclone", "copy", "-P", "/local", "remote:path"
        ]

    def test_rclone_never_calls_os_system(self, mock_subprocess):
        r = rclone()
        with patch("os.system") as mock_os_system:
            r.rclone(["ls", "remote:"])
            mock_os_system.assert_not_called()

    def test_rclone_capture_still_uses_popen(self):
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value.communicate.return_value = ("output", "")
            r = rclone()
            result = r.rclone(["ls", "remote:"], capture=True)
            assert result == "output"
            mock_popen.assert_called_once()


class TestListdir:
    """Verify listdir parses rclone lsjson output correctly."""

    def test_listdir_empty_dir(self):
        """Empty directory returns empty list."""
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value.communicate.return_value = ("[]", "")
            r = rclone()
            result = r.listdir("b2:", "")
            assert result == []

    def test_listdir_mixed_files_and_folders(self, fake_lsjson_output):
        """Mixed files and folders are parsed correctly."""
        json_output = json.dumps(fake_lsjson_output)
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value.communicate.return_value = (json_output, "")
            r = rclone()
            result = r.listdir("b2:", "")

        assert len(result) == 3
        dirs = [e for e in result if e["IsDir"]]
        files = [e for e in result if not e["IsDir"]]
        assert len(dirs) == 1
        assert dirs[0]["Name"] == "documents"
        assert len(files) == 2
        assert {f["Name"] for f in files} == {"photo.jpg", "notes.txt"}

    def test_listdir_malformed_output(self):
        """Malformed JSON output returns empty list."""
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value.communicate.return_value = ("not json", "")
            r = rclone()
            result = r.listdir("b2:", "somepath")
            assert result == []

    def test_listdir_empty_output(self):
        """Empty string output returns empty list."""
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value.communicate.return_value = ("", "")
            r = rclone()
            result = r.listdir("b2:", "")
            assert result == []

    def test_listdir_passes_correct_args(self):
        """Verify the correct rclone command is constructed."""
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value.communicate.return_value = ("[]", "")
            r = rclone()
            r.listdir("b2:", "docs/")
            call_args = mock_popen.call_args[0][0]
            assert call_args == ["rclone", "lsjson", "b2:docs/", "--max-depth", "1"]

    def test_listdir_non_list_json(self):
        """If rclone returns a JSON object instead of array, return empty."""
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value.communicate.return_value = ('{"error": "bad"}', "")
            r = rclone()
            result = r.listdir("b2:", "")
            assert result == []


class TestListremotes:
    """Verify listremotes parses rclone listremotes output."""

    def test_listremotes_returns_remotes(self):
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value.communicate.return_value = ("b2:\ngdrive:\n", "")
            r = rclone()
            result = r.listremotes()
            assert result == ["b2:", "gdrive:"]

    def test_listremotes_empty(self):
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value.communicate.return_value = ("", "")
            r = rclone()
            result = r.listremotes()
            assert result == []

    def test_listremotes_single(self):
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value.communicate.return_value = ("b2:\n", "")
            r = rclone()
            result = r.listremotes()
            assert result == ["b2:"]


class TestTestConnection:
    """Verify test_connection uses rclone lsd and returns bool."""

    def test_connection_success(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            r = rclone()
            assert r.test_connection("b2:") is True
            call_args = mock_run.call_args
            assert call_args[0][0] == ["rclone", "lsd", "b2:", "--max-depth", "1"]

    def test_connection_failure(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            r = rclone()
            assert r.test_connection("b2:") is False

    def test_connection_timeout(self):
        import subprocess as sp
        with patch("subprocess.run", side_effect=sp.TimeoutExpired(cmd="rclone", timeout=10)):
            r = rclone()
            assert r.test_connection("b2:", timeout=10) is False

    def test_connection_os_error(self):
        with patch("subprocess.run", side_effect=OSError("no such file")):
            r = rclone()
            assert r.test_connection("b2:") is False


class TestCacheCorruptionRecovery:
    """Verify rclonecache recovers from corrupt cache files."""

    def _make_cache(self, tmp_cache_file):
        """Create an rclonecache pointing at the tmp cache file."""
        with patch.object(rclonecache, "__init__", lambda self: None):
            cache = rclonecache()
        cache.cachePath = tmp_cache_file
        cache.rclone = rclone()
        return cache

    def test_listdir_recovers_from_corrupt_cache(self, tmp_cache_file):
        """Write corrupt JSON, call listdir(), verify recovery."""
        with open(tmp_cache_file, "w") as f:
            f.write("{invalid json!!! [[")

        rc = self._make_cache(tmp_cache_file)
        fake_entries = [{"Name": "file1.txt", "IsDir": False}]

        with patch.object(rc.rclone, "listdir", return_value=fake_entries):
            result = rc.listdir("b2:")

        assert result == fake_entries
        with open(tmp_cache_file, "r") as f:
            data = json.load(f)
        assert "b2:" in data

    def test_listdir_corrupt_cache_does_not_crash(self, tmp_cache_file):
        """Ensure no unhandled exception on completely garbled cache."""
        with open(tmp_cache_file, "w") as f:
            f.write("\x00\x01\x02\x03")

        rc = self._make_cache(tmp_cache_file)

        with patch.object(rc.rclone, "listdir", return_value=[]):
            result = rc.listdir("remote:")

        assert result == []


class TestAtomicCacheWrites:
    """Verify cache uses atomic write (tmp + os.replace)."""

    def _make_cache(self, tmp_cache_file):
        with patch.object(rclonecache, "__init__", lambda self: None):
            cache = rclonecache()
        cache.cachePath = tmp_cache_file
        cache.rclone = rclone()
        return cache

    def test_original_cache_unchanged_on_write_failure(self, tmp_cache_file):
        """If json.dump raises mid-write, the original cache file is unchanged."""
        original_data = {"b2:": {"timestamp": time.time(), "entries": [{"Name": "old.txt"}]}}
        with open(tmp_cache_file, "w") as f:
            json.dump(original_data, f)

        rc = self._make_cache(tmp_cache_file)

        with patch.object(rc.rclone, "listdir", return_value=[{"Name": "new.txt"}]):
            with patch("json.dump", side_effect=IOError("disk full")):
                try:
                    rc.listdir("b2:")
                except IOError:
                    pass

        # Original cache must be intact
        with open(tmp_cache_file, "r") as f:
            data = json.load(f)
        assert data["b2:"]["entries"] == [{"Name": "old.txt"}]

        # Temp file should not linger
        assert not os.path.exists(tmp_cache_file + ".tmp")

    def test_successful_write_replaces_cache(self, tmp_cache_file):
        """Normal listdir writes atomically and produces valid cache."""
        rc = self._make_cache(tmp_cache_file)
        fake_entries = [{"Name": "file.txt", "IsDir": False}]

        with patch.object(rc.rclone, "listdir", return_value=fake_entries):
            rc.listdir("b2:")

        with open(tmp_cache_file, "r") as f:
            data = json.load(f)
        assert data["b2:"]["entries"] == fake_entries
        # No leftover tmp file
        assert not os.path.exists(tmp_cache_file + ".tmp")


class TestPerDirectoryCaching:
    """Verify rclonecache per-directory caching behavior."""

    def _make_cache(self, tmp_cache_file):
        with patch.object(rclonecache, "__init__", lambda self: None):
            cache = rclonecache()
        cache.cachePath = tmp_cache_file
        cache.rclone = rclone()
        return cache

    def test_listdir_twice_fetches_once(self, tmp_cache_file):
        """Second listdir call uses cache, subprocess called only once."""
        rc = self._make_cache(tmp_cache_file)
        fake_entries = [{"Name": "a.txt", "IsDir": False}]

        with patch.object(rc.rclone, "listdir", return_value=fake_entries) as mock_ld:
            result1 = rc.listdir("b2:", "docs/")
            result2 = rc.listdir("b2:", "docs/")

        assert result1 == fake_entries
        assert result2 == fake_entries
        assert mock_ld.call_count == 1

    def test_invalidate_then_listdir_fetches_again(self, tmp_cache_file):
        """After invalidate, listdir fetches fresh data."""
        rc = self._make_cache(tmp_cache_file)
        entries_v1 = [{"Name": "old.txt", "IsDir": False}]
        entries_v2 = [{"Name": "new.txt", "IsDir": False}]

        with patch.object(rc.rclone, "listdir", return_value=entries_v1):
            rc.listdir("b2:", "docs/")

        rc.invalidate("b2:", "docs/")

        with patch.object(rc.rclone, "listdir", return_value=entries_v2) as mock_ld:
            result = rc.listdir("b2:", "docs/")

        assert result == entries_v2
        assert mock_ld.call_count == 1

    def test_different_paths_cached_independently(self, tmp_cache_file):
        """Each directory path gets its own cache entry."""
        rc = self._make_cache(tmp_cache_file)
        entries_a = [{"Name": "a.txt", "IsDir": False}]
        entries_b = [{"Name": "b.txt", "IsDir": False}]

        with patch.object(rc.rclone, "listdir", return_value=entries_a):
            rc.listdir("b2:", "dir_a/")
        with patch.object(rc.rclone, "listdir", return_value=entries_b):
            rc.listdir("b2:", "dir_b/")

        with open(tmp_cache_file, "r") as f:
            data = json.load(f)
        assert "b2:dir_a/" in data
        assert "b2:dir_b/" in data
        assert data["b2:dir_a/"]["entries"] == entries_a
        assert data["b2:dir_b/"]["entries"] == entries_b

    def test_stale_cache_refetches(self, tmp_cache_file):
        """Entries older than CACHE_TTL are refetched."""
        rc = self._make_cache(tmp_cache_file)
        old_data = {
            "b2:": {"timestamp": time.time() - 7200, "entries": [{"Name": "stale.txt"}]}
        }
        with open(tmp_cache_file, "w") as f:
            json.dump(old_data, f)

        fresh = [{"Name": "fresh.txt", "IsDir": False}]
        with patch.object(rc.rclone, "listdir", return_value=fresh) as mock_ld:
            result = rc.listdir("b2:")

        assert result == fresh
        assert mock_ld.call_count == 1

    def test_get_all_cached_paths(self, tmp_cache_file):
        """Aggregates file paths from multiple cached directories."""
        rc = self._make_cache(tmp_cache_file)
        cache_data = {
            "b2:": {
                "timestamp": time.time(),
                "entries": [
                    {"Name": "root.txt", "IsDir": False},
                    {"Name": "docs", "IsDir": True},
                ],
            },
            "b2:docs/": {
                "timestamp": time.time(),
                "entries": [
                    {"Name": "readme.md", "IsDir": False},
                ],
            },
        }
        with open(tmp_cache_file, "w") as f:
            json.dump(cache_data, f)

        paths = rc.get_all_cached_paths("b2:")
        assert sorted(paths) == ["docs", "docs/readme.md", "root.txt"]

    def test_get_all_cached_paths_ignores_other_remotes(self, tmp_cache_file):
        """Only returns paths for the specified remote."""
        rc = self._make_cache(tmp_cache_file)
        cache_data = {
            "b2:": {
                "timestamp": time.time(),
                "entries": [{"Name": "b2file.txt", "IsDir": False}],
            },
            "gdrive:": {
                "timestamp": time.time(),
                "entries": [{"Name": "gfile.txt", "IsDir": False}],
            },
        }
        with open(tmp_cache_file, "w") as f:
            json.dump(cache_data, f)

        paths = rc.get_all_cached_paths("b2:")
        assert paths == ["b2file.txt"]

    def test_old_format_cache_discarded(self, tmp_cache_file):
        """Old-format cache entries (with 'data' instead of 'entries') are discarded."""
        rc = self._make_cache(tmp_cache_file)
        old_format = {
            "b2:": {"timestamp": time.time(), "data": ["old.txt"]},
        }
        with open(tmp_cache_file, "w") as f:
            json.dump(old_format, f)

        fresh = [{"Name": "new.txt", "IsDir": False}]
        with patch.object(rc.rclone, "listdir", return_value=fresh) as mock_ld:
            result = rc.listdir("b2:")

        assert result == fresh
        assert mock_ld.call_count == 1

    def test_invalidate_nonexistent_key_no_error(self, tmp_cache_file):
        """Invalidating a key that doesn't exist should not raise."""
        rc = self._make_cache(tmp_cache_file)
        rc.invalidate("b2:", "nonexistent/")  # should not raise
