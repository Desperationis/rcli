from abc import ABC, abstractmethod
from typing import Optional, List, Callable
from enums import CHOICE, SCENES
from rclone import *
from forms import *
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
    def __init__(self, filesystem, folderDir=""):
        super().__init__()
        self.rclone = rclone()
        self.filesystem = filesystem
        self.history = []
        self.folderDir = []
        self.currentFolder = filesystem
        self.choiceForum = None
        self.nextScene = None
        self.data = None

        if folderDir != "":
            self.folderDir = folderDir
            for folder in folderDir:
                self.history.append(self.currentFolder.copy())
                self.currentFolder = self.currentFolder[folder]

    def show(self, stdscr):
        if self.choiceForum == None:
            options = self.rclone.lsf(self.currentFolder)
            self.choiceForum = choiceforum(
                options,
                len(self.history) > 0,
                "/".join(self.folderDir),
                self.registerKeyListener,
            )

        self.choiceForum.draw(stdscr)

        c = stdscr.getch()
        self.broadcastKeyEvent(c)

        if c == ord("/"):
            self.nextScene = SCENES.FUZZY_SEARCH

        if self.choiceForum.getdata() != None:
            choice: SelectedOption = self.choiceForum.getdata()

            if choice.choice == CHOICE.BACK:
                self.currentFolder = self.history.pop()
                self.folderDir.pop()
                self.keyListeners.clear()
                self.choiceForum = None

            elif choice.choice == CHOICE.SELECTED:
                if choice.data.endswith("/"):  # It's a folder
                    self.history.append(self.currentFolder.copy())
                    self.folderDir.append(choice.data.replace("/", ""))
                    self.currentFolder = self.currentFolder[
                        choice.data.replace("/", "")
                    ]
                    self.choiceForum = None
                    self.keyListeners.clear()

            elif choice.choice == CHOICE.DOWNLOAD:
                # Assemble full rclone path
                folder = "/".join(self.folderDir)
                fullPath = os.path.join(folder, choice.data)
                self.data = fullPath
                self.nextScene = SCENES.DOWNLOAD

            elif choice.choice == CHOICE.REFRESH:
                self.nextScene = SCENES.REFRESH_DATABASE

            elif choice.choice == CHOICE.QUIT:
                self.nextScene = SCENES.EXIT

    def getNextScene(self) -> Optional[int]:
        return self.nextScene

    def getdata(self):
        return self.data


class fuzzyscene(scene):
    def __init__(self, pathList):
        super().__init__()
        self.pathList = pathList
        self.fuzzyForum = None
        self.nextScene = None

    def show(self, stdscr):
        if self.fuzzyForum == None:
            self.fuzzyForum = fuzzyforum(self.pathList, self.registerKeyListener)

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
    def __init__(self, downloadPath, destination):
        super().__init__()
        self.rclone = rclone()
        self.downloadPath = downloadPath
        self.destination = destination
        self.nextScene = None
        self.commandforum = commandforum(
            ["rclone", "copy", "-P", self.downloadPath, self.destination]
        )

    def show(self, stdscr) -> None:
        self.commandforum.draw(stdscr)

        if self.commandforum.getdata() != None:
            self.nextScene = SCENES.CHOOSE_FILE

        time.sleep(0.2)

    def getNextScene(self) -> Optional[int]:
        return self.nextScene

    def getdata(self) -> Optional[object]:
        if self.commandforum.getdata() == True:
            return ""  # Go to root folder of choosefilescene
        return None


