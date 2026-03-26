## Context

Overhaul rcli from a proof-of-concept rclone TUI into a reliable daily-driver for Backblaze B2 storage. The work addresses critical security/stability bugs (P0), restructures the data layer from full recursive listing to lazy per-directory loading with structured JSON metadata, adds upload support, a remote picker, file metadata display, dynamic terminal sizing, and connection testing.

Key architectural decisions: Replace `rclone ls` (flat recursive) with `rclone lsjson --max-depth 1` (per-directory, structured). Cache becomes per-directory entries in JSON (keyed by `remote:path`). Scenes receive a `rclonecache` instance instead of a pre-built file tree. No new dependencies beyond docopt.

Key files: `rcli/rclone.py` (data layer), `rcli/rcli.py` (entry point), `rcli/cursedcli.py` (main loop), `rcli/scenes.py` (scenes), `rcli/forms.py` (forms), `rcli/components.py` (components), `rcli/enums.py` (constants).

## Checklist

### Test Infrastructure

- [x] **Create test scaffold and pytest configuration** — Create `tests/__init__.py`, `tests/conftest.py` with common fixtures (fake lsjson output, tmp cache dir, mock subprocess). Add `[project.optional-dependencies] dev = ["pytest"]` and `[tool.pytest.ini_options]` to `pyproject.toml`. Done when `pytest` runs with 0 errors, 0 tests collected.

### P0 Fixes — rclone.py

- [x] **Replace `os.system()` with `subprocess.run()`** — In `rcli/rclone.py` line 13, replace `os.system(" ".join(args))` with `subprocess.run(args)`. Eliminates shell injection vulnerability. Test (`tests/test_rclone.py`): verify `rclone()` calls `subprocess.run` with exact list args and never calls `os.system`.

- [x] **Add cache corruption recovery** — In `rcli/rclone.py`, wrap both `json.load()` calls in `try/except (json.JSONDecodeError, ValueError)`. On corruption, delete cache file and return empty dict to trigger re-fetch. Test (`tests/test_rclone.py`): write corrupt JSON to temp cache, call `getPaths()`, verify it recovers without crashing.

- [x] **Atomic cache writes** — In `rcli/rclone.py` `refreshCache`, write to `self.cachePath + ".tmp"` first, then `os.replace(tmp, real)`. Test (`tests/test_rclone.py`): mock `json.dump` to raise mid-write, verify original cache file is unchanged.

- [x] **Check rclone binary exists at startup** — In `rcli/rclone.py`, add `check_rclone_available()` using `shutil.which("rclone")`. Call in `rclonecache.__init__()`. Raise `RuntimeError` with install URL if missing. Test (`tests/test_rclone.py`): patch `shutil.which` to return None, verify `RuntimeError` with expected message.

### P0 Fixes — rcli.py

- [x] **Fix `cli.end()` crash when `cli` is uninitialized** — In `rcli/rcli.py`, initialize `cli = None` before try block, guard `cli.end()` with `if cli is not None`. Test (`tests/test_rcli.py`): patch `cursedcli.__init__` to raise, verify no `NameError`.

- [x] **Always print errors to stderr; catch KeyboardInterrupt** — In `rcli/rcli.py`, add separate `except KeyboardInterrupt` for clean exit. In `except Exception`, always `print(traceback, file=sys.stderr)`. Test (`tests/test_rcli.py`): patch main to raise `KeyboardInterrupt` → no stderr output; raise `ValueError` → stderr contains traceback.

### Helper Utilities

- [x] **Add size and date formatting utilities** — Create `rcli/utils.py` with `format_size(bytes) -> str` (e.g., "4.2 MB") and `format_date(iso_str) -> str` (e.g., "2024-01-15 10:30"). Test (`tests/test_utils.py`): parametrized tests for 0 B, 1.0 KB, 1.5 KB, 1.0 MB, 1.0 GB, malformed date → "unknown".

### Enums Update

- [x] **Add UPLOAD and REMOTE_PICKER enum values** — In `rcli/enums.py`, add `CHOICE.UPLOAD = 0b0100000`, `SCENES.UPLOAD = 0b100000`, `SCENES.REMOTE_PICKER = 0b1000000`. Test (`tests/test_enums.py`): verify all enum values are unique (no bitmask collisions).

### Data Layer Overhaul — rclone.py

- [x] **Rewrite `rclone` class to use `lsjson`** — In `rcli/rclone.py`, remove `getAllPaths`, `getFileStructure`, `displayFileStructure`, `lsf`. Add `listdir(remote, path="") -> list[dict]` using `rclone lsjson <remote><path> --max-depth 1`. Add `listremotes() -> list[str]`. Add `test_connection(remote, timeout=10) -> bool` using `rclone lsd --max-depth 0`. Test (`tests/test_rclone.py`): mock subprocess, verify `listdir` parses sample lsjson JSON correctly for empty dir, mixed files/folders, and malformed output.

- [x] **Rewrite `rclonecache` for per-directory caching** — In `rcli/rclone.py`, change cache schema to `{cache_key: {timestamp, entries: [...]}}` where key = `remote + path`. Replace `getPaths`/`getFileStructure` with `listdir(remote, path)` (checks cache, fetches if stale). Add `invalidate(remote, path)`. Add `get_all_cached_paths(remote)` for fuzzy search. Test (`tests/test_rclone.py`): call listdir twice → subprocess called once; invalidate then listdir → called again; get_all_cached_paths aggregates multiple dirs; old-format cache discarded gracefully.

### Component and Form Updates

- [x] **Make `choicecomponent` accept metadata-rich entries** — In `rcli/components.py`, change `choices: list[str]` to `choices: list[dict]` with keys `Name, Size, ModTime, IsDir`. Update `draw()` to render `name  size  date` with column alignment. Dirs show `"/"` suffix and `"-"` for size. Add `p` keybinding for `CHOICE.UPLOAD`. Test (`tests/test_components.py`): construct with sample entries, `handleinput(ord('p'))` → `CHOICE.UPLOAD`, `handleinput(ord('d'))` → `CHOICE.DOWNLOAD`, `draw()` with mock stdscr doesn't crash.

- [x] **Update `choiceforum` for dynamic layout** — In `rcli/forms.py`, replace hard-coded `brect(1, 3, 20, 20)` with dynamic computation from `stdscr.getmaxyx()` on first `draw()` call. Update bottom bar to include `[p]ut/upload`. Test (`tests/test_forms.py`): construct with sample entries, draw with mock stdscr(40, 120), verify brect fills terminal; bottom bar includes "[p]".

- [x] **Handle `curses.KEY_RESIZE` in components** — In `rcli/components.py`, handle `KEY_RESIZE` in `choicecomponent.handleinput` to flag layout recomputation. In `choiceforum.draw`, recompute brect when flag is set. Test (`tests/test_components.py`): send `KEY_RESIZE` then `draw()` with new mock stdscr size → no crash, layout adapts.

### Scene Updates

- [x] **Update `choosefilescene` for lazy loading** — In `rcli/scenes.py`, replace `filesystem` param with `remote` + `rclonecache`. Scene calls `cache.listdir(remote, path)` on demand. Pass list-of-dicts to `choiceforum`. Handle `CHOICE.UPLOAD` → set `nextScene = SCENES.UPLOAD`. Test (`tests/test_scenes.py`): mock cache.listdir, simulate enter folder → listdir called with correct path, go back → parent shown, download → correct remote path assembled.

- [x] **Update `fuzzyscene` for lazy-loaded data** — In `rcli/scenes.py`, accept `rclonecache` + `remote` instead of static path list. Pull paths from `cache.get_all_cached_paths(remote)`. Test (`tests/test_scenes.py`): mock cache with paths from two dirs, fuzzy search finds results from both.

- [x] **Create `uploadscene`** — In `rcli/scenes.py`, new class mirroring `downloadscene`. Takes `remote_path` (destination). Presents text input for local path, then runs `rclone copy -P <local> <remote_path>`. On completion, calls `cache.invalidate()` and returns to `SCENES.CHOOSE_FILE`. Test (`tests/test_scenes.py`): mock subprocess, verify rclone command is `["rclone", "copy", "-P", "/local/file", "remote:path/"]`, cache invalidation called.

- [x] **Create `remotepickerscene`** — In `rcli/scenes.py`, new class calling `rclone.listremotes()`, displaying results in `choiceforum`. Selection → `getdata()` returns remote name, `getNextScene()` → `SCENES.CHOOSE_FILE`. Quit → `SCENES.EXIT`. Test (`tests/test_scenes.py`): mock listremotes returning `["b2:", "gdrive:"]`, simulate select "b2:", verify `getdata() == "b2:"`.

### Main Loop Updates

- [x] **Add connection testing before main loop** — In `rcli/cursedcli.py`, call `rclone.test_connection(remote, timeout=10)` before browsing. If fails, show error via `loadingforum` and exit. Run in LoadThread so loading animation shows. Test (`tests/test_cursedcli.py`): patch test_connection to return False, verify main loop exits early.

- [x] **Update main loop for lazy loading** — In `rcli/cursedcli.py`, remove `LoadThread` that pre-fetches entire file structure. After connection test, go directly to `choosefilescene(remote, cache)`. Pass cache to scenes. Add `SCENES.UPLOAD` handler creating `uploadscene`. Update `SCENES.REFRESH_DATABASE` to `cache.invalidate` current dir only. Test (`tests/test_cursedcli.py`): mock rclone layer, simulate scene transition sequence (browse → enter folder → download → back → fuzzy → back), verify each scene gets correct params.

- [x] **Make `<remote>` optional and add remote picker** — In `rcli/rcli.py`, change docopt to `rcli [-v] [<remote>]`. In `rcli/cursedcli.py`, if `remote` is None, start with `remotepickerscene`. On selection, set `self.remote` and transition to browse. Test (`tests/test_rcli.py`): call main with no remote → cursedcli gets `remote=None`. `tests/test_cursedcli.py`: `remote=None` → initial scene is remotepickerscene.

- [x] **Handle KEY_RESIZE in main loop** — In `rcli/cursedcli.py`, when scenes receive `KEY_RESIZE` from `getch()`, call `curses.resizeterm(*stdscr.getmaxyx())` before redraw. Test (`tests/test_cursedcli.py`): mock getch to return `KEY_RESIZE` then `ord('q')`, verify no crash.

### Integration and Polish

- [x] **Bump version to 2.0.0** — In `rcli/__init__.py`, change `__version__` to `"2.0.0"`. Done when version string is updated.

- [x] **End-to-end smoke test** — Create `tests/test_integration.py`. Mock subprocess at boundary, simulate full session: startup → connection test → browse root → enter folder → back → fuzzy search → download → upload → exit. Verify correct rclone commands issued in order, no unhandled exceptions, cache populated correctly.
