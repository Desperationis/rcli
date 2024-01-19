import curses
from abc import ABC, abstractmethod
from typing import Optional
from enums import CHOICE, SCENES, SelectedOption
import string
import logging
import threading
import subprocess


class component(ABC):
    def __init__(self, offset=(0, 0)):
        self.offset = offset

    @abstractmethod
    def draw(self, stdscr):
        pass

    @abstractmethod
    def handleinput(self, c: int):
        pass


class textcomponent(component):
    NONE = 0b00000000
    TEXT_CENTERED = 0b00000001
    BOTTOM = 0b00000010
    MIDDLE = 0b00000100
    BAR = 0b00001000

    def __init__(self, text, flags=NONE, offset=(0, 0)):
        super().__init__(offset)
        self.text = text
        self.flags = flags

    def draw(self, stdscr):
        x = self.offset[0]
        y = self.offset[1]
        rows, cols = stdscr.getmaxyx()
        textAttr = curses.A_NORMAL

        if self.flags & self.BOTTOM:
            y = rows - 1

        if self.flags & self.TEXT_CENTERED:
            x = (cols - 1) // 2 - len(self.text) // 2

        if self.flags & self.MIDDLE:
            y = (rows - 1) // 2

        if self.flags & self.BAR:
            leftPadding = 0
            rightPadding = (cols - 1) - len(self.text) - x

            if self.flags & self.TEXT_CENTERED:
                leftPadding = x
                x = 0

            self.text = " " * leftPadding + self.text + " " * rightPadding
            textAttr = curses.A_REVERSE

        try:
            stdscr.addstr(y, x, self.text, textAttr)
        except curses.error:
            pass

    def handleinput(self, c):
        pass

class commandcomponent(component):
    def __init__(self, command: list[str], offset=(0, 0)):
        super().__init__(offset)
        self.command = command
        self.process = None
        self.output = ""
        self.isDone = False

        # Start the subprocess in a separate thread
        self.startcommand()

    def startcommand(self):
        def runcommand():
            try:
                self.isDone = False
                # Run the command and capture real-time output
                self.process = subprocess.Popen(
                    self.command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )

                for line in iter(self.process.stdout.readline, ''):
                    self.output += line

            finally:
                logging.info(self.output)
                self.isDone = True

        # Create and start a new thread for running the subprocess
        thread = threading.Thread(target=runcommand)
        thread.start()

    def draw(self, stdscr):
        rows, cols = stdscr.getmaxyx()

        output = self.output.split("\n")
        output = "\n".join(output[-rows:-1])

        try:
            stdscr.addstr(self.offset[1], self.offset[0], output)
        except curses.error:
            pass

    def handleinput(self, c: int):
        pass



class fuzzycomponent(component):
    def __init__(self, data, maxlines=40, offset=(0, 0)):
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
                stdscr.addstr(
                    self.offset[1] + i + 1, self.offset[0], result, curses.A_REVERSE
                )
            else:
                stdscr.addstr(self.offset[1] + i + 1, self.offset[0], result)

    def updateresults(self):
        results = []
        keywords = list(filter(None, self.inputtext.split(" ")))

        # Iterate through file paths
        for file_path in self.data:
            # Count the occurrences of keywords in the file path
            score = sum(keyword.lower() in file_path.lower() for keyword in keywords)

            # Append the tuple (file_path, score) to the results list
            results.append((file_path, score))

        results.sort(key=lambda x: x[1], reverse=True)
        results = [result[0] for result in results]

        self.topresults = results[:self.maxlines]

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
    def __init__(self, choices: list[str], back=False, offset=(0, 0)):
        super().__init__(offset)
        self.choices = choices
        self.choice = SelectedOption()
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

    def getChoice(self) -> SelectedOption:
        """If nothing selected, CHOICE.NONE + None"""
        return self.choice


    def handleinput(self, c: int):
        if c == curses.KEY_UP or c == ord("k"):
            self.elementIndex -= 1
        elif c == curses.KEY_DOWN or c == ord("j"):
            self.elementIndex += 1
        elif c == curses.KEY_ENTER or c == 10:
            if self.cursorOnChoice():
                self.choice = SelectedOption(CHOICE.SELECTED, self.choices[self.elementIndex])
            if self.cursorOnBack():
                self.choice = SelectedOption(CHOICE.BACK)
        elif c == ord("h") and self.back:
            self.choice = SelectedOption(CHOICE.BACK)

        elif c == ord("d"):
            self.choice = SelectedOption(CHOICE.DOWNLOAD, self.choices[self.elementIndex])

        self.elementIndex = self.elementIndex % len(self.elements)
