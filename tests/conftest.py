import json
import os

import pytest


@pytest.fixture
def fake_lsjson_output():
    """Sample lsjson output matching rclone lsjson format."""
    return [
        {
            "Path": "documents",
            "Name": "documents",
            "Size": -1,
            "MimeType": "inode/directory",
            "ModTime": "2024-01-15T10:30:00.000000000Z",
            "IsDir": True,
        },
        {
            "Path": "photo.jpg",
            "Name": "photo.jpg",
            "Size": 1048576,
            "MimeType": "image/jpeg",
            "ModTime": "2024-02-20T14:45:00.000000000Z",
            "IsDir": False,
        },
        {
            "Path": "notes.txt",
            "Name": "notes.txt",
            "Size": 256,
            "MimeType": "text/plain",
            "ModTime": "2024-03-10T08:00:00.000000000Z",
            "IsDir": False,
        },
    ]


@pytest.fixture
def tmp_cache_dir(tmp_path):
    """Provide a temporary cache directory with a cache.json path."""
    cache_dir = tmp_path / "rcli"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def tmp_cache_file(tmp_cache_dir):
    """Provide a path to a temporary cache.json file."""
    return str(tmp_cache_dir / "cache.json")


@pytest.fixture
def mock_subprocess(monkeypatch):
    """Mock subprocess.run to capture calls without executing rclone."""
    calls = []

    class FakeCompletedProcess:
        def __init__(self, args, stdout="", stderr="", returncode=0):
            self.args = args
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode

    def fake_run(args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return FakeCompletedProcess(args)

    monkeypatch.setattr("subprocess.run", fake_run)
    return calls
