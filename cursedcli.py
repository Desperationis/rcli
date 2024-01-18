import curses
from abc import ABC, abstractmethod
from typing import Optional
import string
import os
import time
import sys 
import subprocess
import logging

class CHOICE:
    BACK = 0b01
    NONE = 0b00


class component:
    def __init__(self, offset=(0,0)):
        self.offset = offset

    @abstractmethod
    def draw(self, stdscr):
        pass

class textcomponent(component):
    def __init__(self, text, offset=(0,0)):
        super().__init__(offset)
        self.text = text

    def draw(self, stdscr):
        stdscr.addstr(self.offset[1], self.offset[0], self.text)

    def handleinput(self, c):
        pass

class textinputcomponent(component):
    def __init__(self, offset=(0,0)):
        super().__init__(offset)
        self.text = ""

    def draw(self, stdscr):
        stdscr.addstr(self.offset[1], self.offset[0], self.text)

    def isvalid(self, c: int):
        return str(chr(c)) in string.printable

    def handleinput(self, c: int):
        if c == curses.KEY_BACKSPACE:
            self.text = self.text[:-1]
        elif self.isvalid(c):
            self.text += chr(c)

class choicecomponent(component):
    def __init__(self, choices: list[str], flags=CHOICE.NONE, offset=(0,0)):
        super().__init__(offset)
        self.choices = choices
        self.choice = None
        self.flags = flags

        self.elements = []
        self.elementIndex = 0

        self.elements.extend(self.choices)
        if flags & CHOICE.BACK:
            self.elements.append(CHOICE.BACK)

    def draw(self, stdscr):
        stdscr.addstr(self.offset[1], self.offset[0], "Choose a file or folder:")

        for i, option in enumerate(self.elements):
            # Relative to origin
            x = self.offset[0] + 5
            y = self.offset[1] + 1 + i
            content = option

            if option == CHOICE.BACK:
                content = "Back"
                y += 1

            if i == self.elementIndex:
                x -= 2
                content = f"> {content}"

            stdscr.addstr(y, x, content)

    def cursorOnChoice(self):
        return self.elementIndex >= 0 and self.elementIndex < len(self.choices)

    def cursorOnBack(self):
        return self.elements[self.elementIndex] == CHOICE.BACK

    def handleinput(self, c: int):
        if c == curses.KEY_UP:
            self.elementIndex -= 1
        elif c == curses.KEY_DOWN:
            self.elementIndex += 1
        elif (c == curses.KEY_ENTER or c == 10 or c == "\n"):
            if self.cursorOnChoice():
                self.choice = self.choices[self.elementIndex]
            if self.cursorOnBack():
                self.choice = CHOICE.BACK

        self.elementIndex = self.elementIndex % len(self.elements)


class forum:
    def __init__(self, registerKeyFunc):
        self.registerKeyFunc = registerKeyFunc

    @abstractmethod
    def draw(self, stdscr):
        pass

    @abstractmethod
    def getdata(self) -> Optional[object]:
        """Returns None if user has not done something with this forum.
        """
        pass

class loadingforum(forum):
    def __init__(self, text: str, registerKeyFunc):
        super().__init__(registerKeyFunc)
        self.components = [
                textcomponent(text, (0, 1))
        ]

    def draw(self, stdscr):
        for component in self.components:
            component.draw(stdscr)

class choiceforum(forum):
    def __init__(self, options, flags, extra: str, registerKeyFunc):
        super().__init__(registerKeyFunc)
        self.options = options
        self.choiceComponent = choicecomponent(self.options, flags, (1,3))
        self.components = [
            self.choiceComponent,
            textcomponent(extra, (1,1))
        ]

        for co in self.components:
            registerKeyFunc(co.handleinput)


    def draw(self, stdscr):
        for component in self.components:
            component.draw(stdscr)

    def getdata(self):
        if self.choiceComponent.choice != None:
            return self.choiceComponent.choice

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
            flags = CHOICE.NONE
            if len(history) > 0:
                flags = CHOICE.BACK
            choiceForum = choiceforum(options, flags, "/".join(folderDir), self.registerKeyListener)

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
