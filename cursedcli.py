import curses
from abc import ABC, abstractmethod
from typing import Optional
from enums import CHOICE, SCENES
from forms import *
import os
import subprocess
import logging



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
        self.keyListeners = []

    def start(self):
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        self.stdscr.keypad(True)

    def registerKeyListener(self, func):
        self.keyListeners.append(func)

    def broadcastKeyEvent(self, c: int):
        for i in self.keyListeners:
            i(c)

    def main(self):
        self.stdscr.clear()
        loadingforum("Loading database, please be patient.",self.registerKeyListener).draw(self.stdscr)
        self.stdscr.refresh()

        rcloneData = rclone()
        fileStructure = rcloneData.getFileStructure("truth:")
        history = []
        folderDir = []
        currentFolder = fileStructure

        while True:
            options = rcloneData.lsf(currentFolder)
            choiceForum = choiceforum(options, len(history) > 0, "/".join(folderDir), self.registerKeyListener)

            while True:
                self.stdscr.clear()
                choiceForum.draw(self.stdscr)

                c = self.stdscr.getch()
                self.broadcastKeyEvent(c)

                if choiceForum.getdata() != None:
                    node: Optional[str] = choiceForum.getdata()
                    if node == CHOICE.BACK:
                        currentFolder = history.pop()
                        folderDir.pop()

                    elif node.endswith("/"): # It's a folder
                        history.append(currentFolder.copy())
                        folderDir.append(node.replace("/",""))
                        currentFolder = currentFolder[node.replace("/", "")]


                    break




    def end(self):
        curses.nocbreak()
        self.stdscr.keypad(False)
        curses.echo()
        curses.curs_set(1)
        curses.endwin()
