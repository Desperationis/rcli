import os
import time
import subprocess
import logging
import json
import shutil
import threading


def check_rclone_available():
    """Raise RuntimeError if the rclone binary is not on PATH."""
    if shutil.which("rclone") is None:
        raise RuntimeError(
            "rclone is not installed or not on PATH. "
            "Install it from https://rclone.org/install/"
        )


class rclone:
    def rclone(self, args: list[str], capture=False, timeout=60, quiet=False):
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
                if not quiet:
                    logging.warning("rclone command timed out: %s", " ".join(args))
                return ""

            if error and not quiet:
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

    def about(self, remote: str, timeout: int = 10):
        """Get remote space usage via rclone about --json. Returns dict or None."""
        output = self.rclone(["about", remote, "--json"], capture=True, timeout=timeout, quiet=True)
        if not output or not output.strip():
            return None
        try:
            data = json.loads(output)
        except (json.JSONDecodeError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        return data

    def listdir_recursive(self, remote: str, timeout: int = 300):
        """List all contents recursively using rclone lsjson -R.

        Returns a list of entry dicts with 'Path' keys on success,
        or None on timeout, network error, or malformed output.
        An empty bucket returns [].
        """
        output = self.rclone(
            ["lsjson", "-R", remote], capture=True, timeout=timeout
        )
        if output is None or output == "":
            # Timeout or rclone failure — no data received
            return None
        if not output.strip():
            return None
        try:
            entries = json.loads(output)
        except (json.JSONDecodeError, ValueError):
            logging.warning("listdir_recursive: failed to parse JSON for %s", remote)
            return None
        if not isinstance(entries, list):
            return None
        return entries

    def test_connection(self, remote: str, timeout: int = 10) -> bool:
        """Test if a remote is reachable using rclone lsd."""
        try:
            result = subprocess.run(
                ["rclone", "lsd", remote, "--max-depth", "1"],
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


class searchindex:
    """Background search index that recursively lists all paths from a remote.

    Runs `rclone lsjson -R` in a daemon thread. Thread-safe access to results
    via is_ready() / has_failed() / get_paths(). Designed to survive network
    errors, timeouts, and malformed responses without crashing.
    """

    MAX_PATHS = 500_000  # Cap to prevent OOM on very large remotes

    def __init__(self, remote):
        self.remote = remote
        self._paths = []
        self._ready = False
        self._failed = False
        self._lock = threading.Lock()
        self._thread = None
        self._process = None  # Track subprocess for cleanup on exit

    def start(self):
        """Start background indexing in a daemon thread."""
        self._thread = threading.Thread(target=self._build, daemon=True)
        self._thread.start()

    def _build(self):
        """Fetch all paths recursively from the remote."""
        process = None
        try:
            args = ["rclone", "lsjson", "-R", self.remote]
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            self._process = process
            try:
                output, error = process.communicate(timeout=300)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                logging.warning("Search index timed out for %s", self.remote)
                with self._lock:
                    self._failed = True
                return
            finally:
                self._process = None

            if error:
                logging.warning("Search index rclone stderr for %s: %s", self.remote, error.strip())

            if not output or not output.strip():
                with self._lock:
                    self._failed = True
                logging.warning("Search index failed for %s: no data returned", self.remote)
                return

            try:
                entries = json.loads(output)
            except (json.JSONDecodeError, ValueError):
                with self._lock:
                    self._failed = True
                logging.warning("Search index failed for %s: malformed JSON", self.remote)
                return

            if not isinstance(entries, list):
                with self._lock:
                    self._failed = True
                return

            paths = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                path = entry.get("Path", "")
                if not path:
                    path = entry.get("Name", "")
                if not path:
                    continue
                # Append trailing / to directories so fuzzy search can distinguish them
                if entry.get("IsDir", False) and not path.endswith("/"):
                    path += "/"
                paths.append(path)
                if len(paths) >= self.MAX_PATHS:
                    logging.warning("Search index capped at %d paths for %s", self.MAX_PATHS, self.remote)
                    break
            with self._lock:
                self._paths = paths
                self._ready = True
            logging.info("Search index ready: %d paths for %s", len(paths), self.remote)
        except Exception as e:
            if process and process.poll() is None:
                process.kill()
                try:
                    process.communicate(timeout=5)
                except Exception:
                    pass
            with self._lock:
                self._failed = True
            logging.warning("Search index failed for %s: %s", self.remote, e)

    def is_ready(self):
        """Return True if the index has been built successfully."""
        with self._lock:
            return self._ready

    def has_failed(self):
        """Return True if the index build encountered an error."""
        with self._lock:
            return self._failed

    def get_paths(self):
        """Return the list of all indexed paths, or empty list if not ready."""
        with self._lock:
            return list(self._paths) if self._ready else []

    def stop(self):
        """Kill the background rclone subprocess if still running."""
        proc = self._process
        if proc and proc.poll() is None:
            proc.kill()
            try:
                proc.communicate(timeout=5)
            except Exception:
                pass
