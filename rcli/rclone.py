import os
import time
import subprocess
import logging
import json
import shutil


def check_rclone_available():
    """Raise RuntimeError if the rclone binary is not on PATH."""
    if shutil.which("rclone") is None:
        raise RuntimeError(
            "rclone is not installed or not on PATH. "
            "Install it from https://rclone.org/install/"
        )


class rclone:
    def rclone(self, args: list[str], capture=False, timeout=60):
        args = ["rclone"] + args

        if not capture:
            subprocess.run(args)
        else:
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            try:
                output, error = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                logging.warning("rclone command timed out: %s", " ".join(args))
                return ""

            if error:
                logging.warning("rclone stderr: %s", error.strip())

            return output

    def listdir(self, remote: str, path: str = "") -> list[dict]:
        """List directory contents using rclone lsjson."""
        target = remote + path
        output = self.rclone(
            ["lsjson", target, "--max-depth", "1"], capture=True
        )
        if not output or not output.strip():
            return []
        try:
            entries = json.loads(output)
        except (json.JSONDecodeError, ValueError):
            return []
        if not isinstance(entries, list):
            return []
        return entries

    def listremotes(self) -> list[str]:
        """List configured remotes using rclone listremotes."""
        output = self.rclone(["listremotes"], capture=True)
        if not output or not output.strip():
            return []
        return [line.strip() for line in output.strip().split("\n") if line.strip()]

    def test_connection(self, remote: str, timeout: int = 10) -> bool:
        """Test if a remote is reachable using rclone lsd."""
        try:
            result = subprocess.run(
                ["rclone", "lsd", remote, "--max-depth", "0"],
                capture_output=True,
                timeout=timeout,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False


class rclonecache:
    CACHE_TTL = 60 * 60  # 1 hour

    def __init__(self):
        check_rclone_available()
        self.cachePath = os.path.expanduser("~/.cache/rcli/cache.json")
        self.rclone = rclone()
        os.makedirs(os.path.expanduser("~/.cache/rcli/"), exist_ok=True)

    def _cache_key(self, remote: str, path: str) -> str:
        return remote + path

    def _load_cache(self) -> dict:
        """Load and validate cache from disk. Returns empty dict on failure."""
        if not os.path.exists(self.cachePath):
            return {}
        try:
            with open(self.cachePath, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, ValueError):
            os.remove(self.cachePath)
            return {}
        if not isinstance(data, dict):
            os.remove(self.cachePath)
            return {}
        # Discard old-format cache (keys missing "entries" field)
        for key, val in list(data.items()):
            if not isinstance(val, dict) or "entries" not in val:
                del data[key]
        return data

    def _save_cache(self, cache: dict):
        """Atomically write cache to disk."""
        tmp_path = self.cachePath + ".tmp"
        try:
            with open(tmp_path, "w") as f:
                json.dump(cache, f, indent=2)
            os.replace(tmp_path, self.cachePath)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    def listdir(self, remote: str, path: str = "") -> list[dict]:
        """List directory contents, using cache when fresh."""
        key = self._cache_key(remote, path)
        cache = self._load_cache()
        if key in cache:
            entry = cache[key]
            if time.time() - entry["timestamp"] <= self.CACHE_TTL:
                return entry["entries"]
        # Cache miss or stale — fetch from rclone
        entries = self.rclone.listdir(remote, path)
        cache[key] = {"timestamp": time.time(), "entries": entries}
        self._save_cache(cache)
        return entries

    def invalidate(self, remote: str, path: str = ""):
        """Remove a specific directory from the cache."""
        key = self._cache_key(remote, path)
        cache = self._load_cache()
        if key in cache:
            del cache[key]
            self._save_cache(cache)

    def get_all_cached_paths(self, remote: str) -> list[str]:
        """Return all file paths from cached directories for a remote."""
        cache = self._load_cache()
        paths = []
        for key, val in cache.items():
            if not key.startswith(remote):
                continue
            dir_path = key[len(remote):]
            for entry in val.get("entries", []):
                name = entry.get("Name", "")
                if dir_path:
                    paths.append(dir_path + name)
                else:
                    paths.append(name)
        return paths


