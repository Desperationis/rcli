import curses
from abc import ABC, abstractmethod
from typing import Optional, List, Callable
from enums import CHOICE, SCENES
from forms import *
import os
import time
import subprocess
import logging
import json


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


class rclone:
    def rclone(self, args: list[str], capture=False):
        args.insert(0, "rclone")

        if not capture:
            os.system(" ".join(args))
        else:
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            output, error = process.communicate()

            return output

    def getAllPaths(self, remote: str):
        paths = self.rclone(["ls", remote], capture=True).split("\n")
        paths = [path.lstrip() for path in paths]
        return [" ".join(path.split(" ")[1:]) for path in paths]

    def getFileStructure(self, remote: str):
        paths = self.getAllPaths(remote)

        fileStructure = {}

        for path in paths:
            parts = path.split("/")
            currentLevel = fileStructure

            for part in parts:
                if part not in currentLevel:
                    currentLevel[part] = {}
                currentLevel = currentLevel[part]

        return fileStructure

    def displayFileStructure(self, fileStructure, indent=0):
        for key, value in fileStructure.items():
            logging.debug("  " * indent + f"- {key}")
            if value:
                self.displayFileStructure(value, indent + 1)

    def lsf(self, fileStructure):
        output = []
        for key in fileStructure:
            if len(key) > 0:
                if len(fileStructure[key]) > 0:
                    output.append(key + "/")
                else:
                    output.append(key)

        return output


class rclonecache:
    def __init__(self):
        self.cacheStructure = os.path.expanduser("~/.cache/rcli/cacheStructure.json")
        self.cachePaths = os.path.expanduser("~/.cache/rcli/cachePaths.json")
        self.rclone = rclone()
        os.makedirs(os.path.expanduser("~/.cache/rcli/"), exist_ok=True)

    def getFileStructure(self, remote: str, forceUpdate=False):
        if not os.path.exists(self.cacheStructure):
            forceUpdate = True

        if os.path.exists(self.cacheStructure) and not forceUpdate:
            logging.info("Loading from cache...")
            with open(self.cacheStructure, "r") as file:
                cache = json.load(file)
                logging.info("Cache loaded.")
                if time.time() - cache["timestamp"] > 60 * 60: # An Hour
                    forceUpdate = True
                    logging.info("Too old. Refreshing...")
                else:
                    logging.info("Returning data")
                    return cache["data"]

        if forceUpdate:
            fileStructure = self.rclone.getFileStructure(remote)
            data = {}
            data["timestamp"] = time.time()
            data["data"] = fileStructure
            logging.info("Saved filestructure, writing to cache...")
            with open(self.cacheStructure, "w") as file:
                json.dump(data, file, indent=2)
            logging.info("Write complete. Here is the file structure:")
            logging.info(fileStructure)

            return fileStructure

    def getPaths(self, remote: str, forceUpdate=False):
        if not os.path.exists(self.cachePaths):
            forceUpdate = True

        if os.path.exists(self.cachePaths) and not forceUpdate:
            with open(self.cachePaths, "r") as file:
                cache = json.load(file)
                if time.time() - cache["timestamp"] > 60 * 60: # An Hour
                    forceUpdate = True
                else:
                    return cache["data"]
        else:
            paths = self.rclone.getAllPaths(remote)
            data = {}
            data["timestamp"] = time.time()
            data["data"] = paths
            with open(self.cachePaths, "w") as file:
                json.dump(data, file, indent=2)
            return paths


class cursedcli:
    def __init__(self, remote):
        self.stdscr = curses.initscr()
        self.remote = remote

    def start(self):
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        curses.start_color()
        curses.use_default_colors()  # Without this color pair has no transparent background
        curses.set_escdelay(25)  # Without this there is a lag when pressing escape
        self.stdscr.keypad(True)

        curses.init_pair(1, curses.COLOR_CYAN, -1)

    def main(self):
        self.stdscr.erase()
        loadingforum("Loading database, please be patient.").draw(self.stdscr)
        self.stdscr.refresh()

        cache = rclonecache()
        fileStructure = cache.getFileStructure(self.remote)
        allPaths = cache.getPaths(self.remote)

        scene = choosefilescene(fileStructure)
        while True:
            self.stdscr.erase()
            scene.show(self.stdscr)
            self.stdscr.refresh()

            nextScene: Optional[int] = scene.getNextScene()
            if nextScene == SCENES.FUZZY_SEARCH:
                scene = fuzzyscene(allPaths)

            if nextScene == SCENES.CHOOSE_FILE:
                filePath: str = scene.getdata()
                initialFolder = list(
                    filter(None, filePath.split("/"))
                )  # Removes empty strings
                initialFolder = initialFolder[:-1]  # Parent folder path
                scene = choosefilescene(fileStructure, initialFolder)

            if nextScene == SCENES.DOWNLOAD:
                downloadPath: str = self.remote + scene.getdata()
                logging.debug(f"Will download from path {downloadPath}")
                scene = downloadscene(downloadPath, ".")

            if nextScene == SCENES.REFRESH_DATABASE:
                loadingforum("Loading database, please be patient.").draw(self.stdscr)
                self.stdscr.refresh()
                rcloneData = rclonecache()
                fileStructure = rcloneData.getFileStructure(
                    self.remote, forceUpdate=True
                )
                allPaths = rcloneData.getPaths(self.remote, forceUpdate=True)
                scene = choosefilescene(fileStructure, "")

    def end(self):
        curses.nocbreak()
        self.stdscr.keypad(False)
        curses.echo()
        curses.curs_set(1)
        curses.endwin()
