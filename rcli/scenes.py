import curses
from abc import ABC, abstractmethod
from typing import Optional, List, Callable
from .enums import CHOICE, SCENES
from .rclone import *
from .forms import *
import os
import time

class scene(ABC):
    def __init__(self):
        self.keyListeners: List[Callable[[int], None]] = []

    def broadcastKeyEvent(self, c: int):
        for i in self.keyListeners:
            i(c)

    def registerKeyListener(self, func):
        self.keyListeners.append(func)

    @abstractmethod
    def show(self, stdscr) -> None:
        pass

    @abstractmethod
    def getNextScene(self) -> Optional[int]:
        """Returns None if not ready to switch."""
        pass

    @abstractmethod
    def getdata(self) -> Optional[object]:
        """If a scene passes data to another, this will return the data. None
        if the scene didn't return any. Yes, this is completely dependent on a
        per-scene basis."""
        pass


class choosefilescene(scene):
    def __init__(self, remote, cache, folderDir=None):
        super().__init__()
        self.remote = remote
        self.cache = cache
        self.folderDir = folderDir if folderDir is not None else []
        self.choiceForum = None
        self.nextScene = None
        self.data = None

    def _current_path(self):
        if not self.folderDir:
            return ""
        return "/".join(self.folderDir) + "/"

    def show(self, stdscr):
        if self.choiceForum is None:
            entries = self.cache.listdir(self.remote, self._current_path())
            self.choiceForum = choiceforum(
                entries,
                len(self.folderDir) > 0,
                self._current_path(),
                self.registerKeyListener,
            )

        self.choiceForum.draw(stdscr)

        c = stdscr.getch()
        self.broadcastKeyEvent(c)

        if c == ord("/"):
            self.nextScene = SCENES.FUZZY_SEARCH

        if self.choiceForum.getdata() is not None:
            choice: SelectedOption = self.choiceForum.getdata()

            if choice.choice == CHOICE.BACK:
                self.folderDir.pop()
                self.keyListeners.clear()
                self.choiceForum = None

            elif choice.choice == CHOICE.SELECTED:
                entry = choice.data
                if entry.get("IsDir", False):
                    self.folderDir.append(entry["Name"])
                    self.choiceForum = None
                    self.keyListeners.clear()

            elif choice.choice == CHOICE.DOWNLOAD:
                entry = choice.data
                name = entry["Name"]
                fullPath = self._current_path() + name
                self.data = (fullPath, entry.get("IsDir", False))
                self.nextScene = SCENES.DOWNLOAD

            elif choice.choice == CHOICE.UPLOAD:
                self.nextScene = SCENES.UPLOAD

            elif choice.choice == CHOICE.REFRESH:
                self.nextScene = SCENES.REFRESH_DATABASE

            elif choice.choice == CHOICE.QUIT:
                self.nextScene = SCENES.EXIT

    def getNextScene(self) -> Optional[int]:
        return self.nextScene

    def getdata(self):
        return self.data


class fuzzyscene(scene):
    def __init__(self, remote, cache, folderDir=None):
        super().__init__()
        self.remote = remote
        self.cache = cache
        self.folderDir = folderDir if folderDir is not None else []
        self.fuzzyForum = None
        self.nextScene = None

    def show(self, stdscr):
        if self.fuzzyForum == None:
            pathList = self.cache.get_all_cached_paths(self.remote)
            self.fuzzyForum = fuzzyforum(pathList, self.registerKeyListener)

        self.fuzzyForum.draw(stdscr)

        c = stdscr.getch()
        self.broadcastKeyEvent(c)

        # User selected something a path
        if self.fuzzyForum.getdata() != None:
            self.nextScene = SCENES.CHOOSE_FILE

    def getNextScene(self) -> Optional[int]:
        return self.nextScene

    def getdata(self):
        if self.fuzzyForum != None:
            return self.fuzzyForum.getdata()
        return None


class downloadscene(scene):
    def __init__(self, downloadPath, destination, folderDir=None):
        super().__init__()
        self.rclone = rclone()
        self.downloadPath = downloadPath
        self.destination = destination
        self.folderDir = folderDir if folderDir else []
        self.nextScene = None
        self.commandforum = commandforum(
            ["rclone", "copy", "-P", self.downloadPath, self.destination]
        )

    def show(self, stdscr) -> None:
        self.commandforum.draw(stdscr)

        if self.commandforum.getdata() != None:
            self.nextScene = SCENES.CHOOSE_FILE
            return

        # Allow user to cancel with q or ESC while command is running
        stdscr.timeout(200)
        c = stdscr.getch()
        stdscr.timeout(-1)
        if c == ord('q') or c == 27:
            self.commandforum.commandcomponent.kill()
            self.nextScene = SCENES.CHOOSE_FILE
        elif c == curses.KEY_RESIZE:
            curses.resizeterm(*stdscr.getmaxyx())

    def getNextScene(self) -> Optional[int]:
        return self.nextScene

    def getdata(self) -> Optional[object]:
        if self.commandforum.getdata() == True:
            # Return path that restores to the original folder
            # Adding a dummy element since cursedcli removes the last element
            return "/".join(self.folderDir + ["_"])
        return None


class remotepickerscene(scene):
    def __init__(self, rc):
        super().__init__()
        self.rc = rc
        self.choiceForum = None
        self.nextScene = None
        self.data = None

    def show(self, stdscr):
        if self.choiceForum is None:
            remotes = self.rc.listremotes()
            entries = [
                {"Name": name, "Size": 0, "ModTime": "", "IsDir": False}
                for name in remotes
            ]
            self.choiceForum = choiceforum(
                entries,
                False,
                "Select a remote:",
                self.registerKeyListener,
            )

        self.choiceForum.draw(stdscr)

        c = stdscr.getch()
        self.broadcastKeyEvent(c)

        if self.choiceForum.getdata() is not None:
            choice: SelectedOption = self.choiceForum.getdata()

            if choice.choice == CHOICE.SELECTED:
                self.data = choice.data["Name"]
                self.nextScene = SCENES.CHOOSE_FILE

            elif choice.choice == CHOICE.QUIT:
                self.nextScene = SCENES.EXIT

    def getNextScene(self) -> Optional[int]:
        return self.nextScene

    def getdata(self):
        return self.data


class uploadscene(scene):
    def __init__(self, remote, cache, folderDir=None):
        super().__init__()
        self.remote = remote
        self.cache = cache
        self.folderDir = folderDir if folderDir else []
        self.nextScene = None
        self.local_path = ""
        self.commandforum = None

    def _current_path(self):
        if not self.folderDir:
            return ""
        return "/".join(self.folderDir) + "/"

    def _remote_dest(self):
        return self.remote + self._current_path()

    def show(self, stdscr) -> None:
        if self.commandforum is None:
            # Input phase: prompt for local file path
            rows, cols = stdscr.getmaxyx()
            try:
                stdscr.addstr(1, 1, f"Upload to: {self._remote_dest()}")
                stdscr.addstr(3, 1, "Local path: " + self.local_path)
                bar_text = "[enter] upload   [esc] cancel"
                padding = " " * max(0, cols - 1 - len(bar_text))
                stdscr.addstr(rows - 1, 0, bar_text + padding, curses.A_REVERSE)
            except curses.error:
                pass

            c = stdscr.getch()

            if c == 27:  # Escape
                self.nextScene = SCENES.CHOOSE_FILE
            elif c == curses.KEY_ENTER or c == 10:
                if self.local_path:
                    self.commandforum = commandforum(
                        ["rclone", "copy", "-P", self.local_path, self._remote_dest()]
                    )
            elif c == curses.KEY_BACKSPACE or c == 127:
                self.local_path = self.local_path[:-1]
            elif 32 <= c < 127:  # Printable ASCII
                self.local_path += chr(c)
        else:
            # Command phase: show upload progress
            self.commandforum.draw(stdscr)

            if self.commandforum.getdata() is not None:
                self.cache.invalidate(self.remote, self._current_path())
                self.nextScene = SCENES.CHOOSE_FILE
                return

            # Allow user to cancel with q or ESC while command is running
            stdscr.timeout(200)
            c = stdscr.getch()
            stdscr.timeout(-1)
            if c == ord('q') or c == 27:
                self.commandforum.commandcomponent.kill()
                self.nextScene = SCENES.CHOOSE_FILE
            elif c == curses.KEY_RESIZE:
                curses.resizeterm(*stdscr.getmaxyx())

    def getNextScene(self) -> Optional[int]:
        return self.nextScene

    def getdata(self) -> Optional[object]:
        if self.commandforum and self.commandforum.getdata() == True:
            # Return path that restores to the original folder
            return "/".join(self.folderDir + ["_"])
        return None


