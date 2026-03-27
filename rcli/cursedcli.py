import curses
import time
from typing import Optional
from threading import Thread
from .enums import SCENES
from .forms import *
from .scenes import *
from .rclone import *
from . import __version__
try:
    from ._buildinfo import BUILD_YEAR
except ImportError:
    from datetime import datetime
    BUILD_YEAR = datetime.now().year
import logging


class cursedcli:
    def __init__(self, remote, no_index=False):
        self.stdscr = curses.initscr()
        self.remote = remote
        self.no_index = no_index
        self._search_index = None

    def start(self):
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        curses.start_color()
        curses.use_default_colors()  # Without this color pair has no transparent background
        curses.set_escdelay(25)  # Without this there is a lag when pressing escape
        self.stdscr.keypad(True)

        curses.init_pair(1, curses.COLOR_CYAN, -1)


    def _handle_resize(self):
        """Call resizeterm only when the terminal has actually been resized."""
        rows, cols = self.stdscr.getmaxyx()
        if curses.is_term_resized(rows, cols):
            curses.resizeterm(rows, cols)

    def _test_connection(self):
        """Run connection test with loading animation. Returns True if connected."""
        content = [
            "                     /$$ /$$",
            "                    | $$|__/",
            "  /$$$$$$   /$$$$$$$| $$ /$$",
            " /$$__  $$ /$$_____/| $$| $$",
            "| $$  \__/| $$      | $$| $$",
            "| $$      | $$      | $$| $$",
            "| $$      |  $$$$$$$| $$| $$",
            "|__/       \_______/|__/|__/",
            "",
            f"v{__version__}",
            f"Copyright (c) {BUILD_YEAR} Diego Contreras",
            "MIT License",
            "",
            "Connecting to remote, please wait...",
        ]

        class ConnTestThread(Thread):
            def __init__(self, remote):
                Thread.__init__(self)
                self.remote = remote
                self.connected = False

            def run(self):
                rc = rclone()
                self.connected = rc.test_connection(self.remote, timeout=10)

        conn_test = ConnTestThread(self.remote)
        conn_test.daemon = True
        conn_test.start()
        self.stdscr.timeout(100)
        while conn_test.is_alive():
            self.stdscr.erase()
            loadingforum(content).draw(self.stdscr)
            self.stdscr.refresh()
            c = self.stdscr.getch()
            if c == 27 or c == ord('q'):  # ESC or q to cancel
                self.stdscr.timeout(-1)
                return False
            if c == curses.KEY_RESIZE:
                curses.resizeterm(*self.stdscr.getmaxyx())
        self.stdscr.timeout(-1)
        conn_test.join()

        if not conn_test.connected:
            self.stdscr.erase()
            loadingforum(
                f"Failed to connect to {self.remote}. Check your rclone configuration."
            ).draw(self.stdscr)
            self.stdscr.refresh()
            time.sleep(3)
            return False

        return True

    def main(self):
        # If no remote specified, start with remote picker
        if self.remote is None:
            check_rclone_available()
            rc = rclone()
            self.stdscr.erase()
            loadingforum("Querying remotes...").draw(self.stdscr)
            self.stdscr.refresh()
            scene = remotepickerscene(rc)
            while True:
                self._handle_resize()
                self.stdscr.erase()
                scene.show(self.stdscr)
                self.stdscr.refresh()

                nextScene = scene.getNextScene()
                if nextScene == SCENES.CHOOSE_FILE:
                    self.remote = scene.getdata()
                    break
                if nextScene == SCENES.EXIT:
                    return

        # Connection test
        if not self._test_connection():
            return

        cache = rclonecache()

        # Start background search index (unless disabled via --no-index)
        index = None
        if not self.no_index:
            index = searchindex(self.remote)
            index.start()
            self._search_index = index

        scene = choosefilescene(self.remote, cache)
        while True:
            self._handle_resize()
            self.stdscr.erase()
            scene.show(self.stdscr)
            self.stdscr.refresh()

            nextScene: Optional[int] = scene.getNextScene()
            if nextScene == SCENES.FUZZY_SEARCH:
                scene = fuzzyscene(self.remote, cache, scene.folderDir if hasattr(scene, 'folderDir') else [], index)

            if nextScene == SCENES.CHOOSE_FILE:
                filePath = scene.getdata()
                if filePath:
                    initialFolder = list(
                        filter(None, filePath.split("/"))
                    )  # Removes empty strings
                    # Directories end with / — navigate into them;
                    # files — navigate to their parent folder
                    if not filePath.endswith("/"):
                        initialFolder = initialFolder[:-1]
                else:
                    initialFolder = scene.folderDir if hasattr(scene, 'folderDir') else []
                scene = choosefilescene(self.remote, cache, initialFolder)

            if nextScene == SCENES.DOWNLOAD:
                downloadPath: str = self.remote + scene.getdata()[0]
                folderDir = scene.folderDir

                # If a folder
                if scene.getdata()[1]:
                    scene = downloadscene(downloadPath, scene.getdata()[0], folderDir)
                else:
                    scene = downloadscene(downloadPath, ".", folderDir)

            if nextScene == SCENES.UPLOAD:
                folderDir = scene.folderDir if hasattr(scene, 'folderDir') else []
                scene = uploadscene(self.remote, cache, folderDir)

            if nextScene == SCENES.REFRESH_DATABASE:
                loadingforum("Refreshing cache, please be patient.").draw(self.stdscr)
                oldFolder = scene.folderDir
                self.stdscr.refresh()
                cache.invalidate(self.remote, "/".join(oldFolder) + "/" if oldFolder else "")
                scene = choosefilescene(self.remote, cache, oldFolder)

            if nextScene == SCENES.EXIT:
                break

    def end(self):
        # Kill background search index subprocess if still running
        if self._search_index is not None:
            self._search_index.stop()
        curses.nocbreak()
        self.stdscr.keypad(False)
        curses.echo()
        curses.curs_set(1)
        curses.endwin()
