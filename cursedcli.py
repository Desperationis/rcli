import curses
from abc import ABC, abstractmethod
from typing import Optional, List, Callable
from enums import CHOICE, SCENES
from forms import *
import os
import subprocess
import logging


class scene(ABC):
    def __init__(self, filesystem):
        self.rclone = rclone()
        self.filesystem = filesystem
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
        """Returns None if not ready to switch.
        """
        pass


class choosefilescene(scene):
    def __init__(self, filesystem):
        super().__init__(filesystem)
        self.history = []
        self.folderDir = []
        self.currentFolder = filesystem
        self.choiceForum = None

    def show(self, stdscr):
        if self.choiceForum == None:
            options = self.rclone.lsf(self.currentFolder)
            self.choiceForum = choiceforum(options, len(self.history) > 0, "/".join(self.folderDir), self.registerKeyListener)

        self.choiceForum.draw(stdscr)

        c = stdscr.getch()
        self.broadcastKeyEvent(c)

        if self.choiceForum.getdata() != None:
            node: Optional[str] = self.choiceForum.getdata()
            if node == None:
                pass

            elif node == CHOICE.BACK:
                self.currentFolder = self.history.pop()
                self.folderDir.pop()
                self.keyListeners.clear()
                self.choiceForum = None

            elif node.endswith("/"): # It's a folder
                self.history.append(self.currentFolder.copy())
                self.folderDir.append(node.replace("/",""))
                self.currentFolder = self.currentFolder[node.replace("/", "")]
                self.choiceForum = None
                self.keyListeners.clear()

    def getNextScene(self) -> Optional[int]:
        return None



class rclone:
    def rclone(self, args : list[str], capture=False):
        args.insert(0, "rclone")

        if not capture:
            os.system(" ".join(args))
        else:
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            output, error = process.communicate()

            return output


    def getFileStructure(self, remote: str):
        paths = self.rclone(["ls", remote], capture=True).split("\n")
        paths = [path.lstrip() for path in paths]
        paths = [" ".join(path.split(" ")[1:]) for path in paths]
        
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




class cursedcli:
    def __init__(self):
        self.stdscr = curses.initscr()

    def start(self):
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        self.stdscr.keypad(True)


    def main(self):
        self.stdscr.clear()
        loadingforum("Loading database, please be patient.").draw(self.stdscr)
        self.stdscr.refresh()

        rcloneData = rclone()
        fileStructure = rcloneData.getFileStructure("truth:")

        scene = choosefilescene(fileStructure)
        while True:
            self.stdscr.clear()
            scene.show(self.stdscr)
            self.stdscr.refresh()


    def end(self):
        curses.nocbreak()
        self.stdscr.keypad(False)
        curses.echo()
        curses.curs_set(1)
        curses.endwin()
