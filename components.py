import curses
from abc import ABC, abstractmethod
from typing import Optional
from enums import CHOICE, SCENES
import string
import logging
from rapidfuzz import fuzz, process

class component(ABC):
    def __init__(self, offset=(0,0)):
        self.offset = offset

    @abstractmethod
    def draw(self, stdscr):
        pass

    @abstractmethod
    def handleinput(self, c: int):
        pass

class textcomponent(component):
    def __init__(self, text, offset=(0,0)):
        super().__init__(offset)
        self.text = text

    def draw(self, stdscr):
        stdscr.addstr(self.offset[1], self.offset[0], self.text)

    def handleinput(self, c):
        pass

class fuzzycomponent(component):
    def __init__(self, data, maxlines=10, offset=(0,0)):
        super().__init__(offset)
        self.data = data 
        self.maxlines = maxlines
        self.topresults = []
        self.inputtext = ""
        self.selectedIndex = 0
        self.choice = None

    def draw(self, stdscr):
        stdscr.addstr(self.offset[1], self.offset[0], self.inputtext)
        for i, result in enumerate(self.topresults):
            if self.selectedIndex == i:
                stdscr.addstr(self.offset[1] + i + 1, self.offset[0], result, curses.A_REVERSE)
            else:
                stdscr.addstr(self.offset[1] + i + 1, self.offset[0], result)

    def updateresults(self):
        self.topresults = process.extract(self.inputtext, self.data, scorer=fuzz.WRatio, limit=self.maxlines)
        self.topresults = [result[0] for result in self.topresults]

    def isvalid(self, c: int):
         return str(chr(c)) in string.printable

    def handleinput(self, c: int):
        if c == curses.KEY_BACKSPACE:
            self.inputtext = self.inputtext[:-1]
            self.updateresults()
        elif c == curses.KEY_ENTER or c == 10:
            if len(self.topresults) > 0:
                self.choice = self.topresults[self.selectedIndex]
        elif c == curses.KEY_DOWN or c == 9:  # Tab
            self.selectedIndex += 1
        elif c == curses.KEY_UP or c == curses.KEY_BTAB:  # Shift+Tab
            self.selectedIndex -= 1
        elif self.isvalid(c):
            self.inputtext += chr(c)
            self.updateresults()

        if len(self.topresults) > 0:
            self.selectedIndex %= len(self.topresults)
        else:
            self.selectedIndex = 0

class choicecomponent(component):
    def __init__(self, choices: list[str], back=False, offset=(0,0)):
        super().__init__(offset)
        self.choices = choices
        self.choice = None
        self.back = back

        self.elements = []
        self.elementIndex = 0

        self.elements.extend(self.choices)
        if back:
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

            if option != CHOICE.BACK and option.endswith("/"):
                stdscr.addstr(y, x, content, curses.color_pair(1))
            else:
                stdscr.addstr(y, x, content)

    def cursorOnChoice(self):
        return self.elementIndex >= 0 and self.elementIndex < len(self.choices)

    def cursorOnBack(self):
        return self.elements[self.elementIndex] == CHOICE.BACK

    def handleinput(self, c: int):
        if c == curses.KEY_UP or c == ord("k"):
            self.elementIndex -= 1
        elif c == curses.KEY_DOWN or c == ord("j"):
            self.elementIndex += 1
        elif c == curses.KEY_ENTER or c == 10:
            if self.cursorOnChoice():
                self.choice = self.choices[self.elementIndex]
            if self.cursorOnBack():
                self.choice = CHOICE.BACK
        elif c == ord("h") and self.back:
            self.choice = CHOICE.BACK


        self.elementIndex = self.elementIndex % len(self.elements)


