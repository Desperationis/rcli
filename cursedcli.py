import curses
from abc import ABC, abstractmethod
import string

class component:
    def __init__(self, offset=(0,0)):
        self.offset = offset

    @abstractmethod
    def draw(self, stdscr):
        pass

    @abstractmethod
    def handleinput(self, c):
        pass

class textcomponent(component):
    def __init__(self, text, offset=(0,0)):
        super().__init__(offset)
        self.text = text

    def draw(self, stdscr):
        stdscr.addstr(self.offset[1], self.offset[0], self.text)

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
    def __init__(self, choices: list[str], offset=(0,0)):
        super().__init__(offset)
        self.choices = choices
        self.choiceIndex = 0

    def draw(self, stdscr):
        x = self.offset[0]
        y = self.offset[1]
        stdscr.addstr(y, x, "Choose a file or folder:")

        for i, option in enumerate(self.choices):
            if i == self.choiceIndex:
                stdscr.addstr(y + 1 + i, x + 3, "> " + option)
            else:
                stdscr.addstr(y + 1 + i, x + 5, option)


    def handleinput(self, c: int):
        if c == curses.KEY_UP:
            self.choiceIndex -= 1
        elif c == curses.KEY_DOWN:
            self.choiceIndex += 1

        self.choiceIndex %= len(self.choices)


class cursedcli:
    def __init__(self):
        self.stdscr = curses.initscr()

    def start(self):
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        self.stdscr.keypad(True)

    def main(self):
        options = ["Folder 1", "Folder 2", "File 3", "Folder 4"]

        components = []
        components.append(textcomponent("hello", (0,10)))
        components.append(textinputcomponent((0,11)))
        components.append(choicecomponent(options, (1,1)))

        print("here")

        while True:
            self.stdscr.clear()
            for component in components:
                component.draw(self.stdscr)
            c = self.stdscr.getch()
            for component in components:
                component.handleinput(c)

            if c == curses.KEY_ENTER or c == 10 or c == "\n":
                break



    def end(self):
        curses.nocbreak()
        self.stdscr.keypad(False)
        curses.echo()
        curses.curs_set(1)
        curses.endwin()
