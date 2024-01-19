import curses
from abc import ABC, abstractmethod
from typing import Optional
from enums import CHOICE, SCENES
import string

class component(ABC):
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
    def __init__(self, choices: list[str], back=False, offset=(0,0)):
        super().__init__(offset)
        self.choices = choices
        self.choice = None

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


