import curses
from abc import ABC, abstractmethod
from typing import Optional
from .enums import CHOICE, SCENES, SelectedOption
from .brect import brect
from .utils import format_size, format_date
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

        display_text = self.text

        if self.flags & self.BAR:
            leftPadding = 0
            rightPadding = max(0, (cols - 1) - len(self.text) - x)

            if self.flags & self.TEXT_CENTERED:
                leftPadding = x
                x = 0

            display_text = " " * leftPadding + self.text + " " * rightPadding
            textAttr = curses.A_REVERSE

        try:
            stdscr.addstr(y, x, display_text, textAttr)
        except curses.error:
            pass

    def handleinput(self, c):
        pass


class commandcomponent(component):
    def __init__(self, command: list[str], offset=(0, 0)):
        super().__init__(offset)
        self.command = command
        self.process = None
        self.lines = []  # Store lines as a list for proper terminal handling
        self.isDone = False
        self._lock = threading.Lock()

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
                    text=True,
                )

                # Read character by character to properly handle \r and ANSI escapes
                current_line = ""
                escape_seq = ""
                in_escape = False

                while True:
                    char = self.process.stdout.read(1)
                    if not char:
                        break

                    # Handle ANSI escape sequences (e.g., \033[8A for cursor up)
                    if char == '\033':
                        in_escape = True
                        escape_seq = char
                        continue

                    if in_escape:
                        escape_seq += char
                        # Check for complete escape sequence (ends with letter)
                        if char.isalpha():
                            in_escape = False
                            # Handle cursor up: \033[nA
                            if escape_seq.endswith('A') and '[' in escape_seq:
                                try:
                                    # Extract the number of lines to move up
                                    num = escape_seq[2:-1]  # Get chars between [ and A
                                    lines_up = int(num) if num else 1
                                    # Discard current_line - it's old content being overwritten
                                    current_line = ""
                                    # Remove n lines to simulate cursor moving up
                                    with self._lock:
                                        self.lines = self.lines[:-lines_up] if lines_up <= len(self.lines) else []
                                except ValueError:
                                    pass
                            # Ignore other escape sequences (clear line, colors, etc.)
                            escape_seq = ""
                        continue

                    if char == '\r':
                        # Carriage return: go to beginning of line
                        # Discard current_line - next chars will overwrite it
                        current_line = ""
                    elif char == '\n':
                        # Newline: commit current line and start new one
                        # Detect start of new rclone progress block and clear old lines
                        # rclone progress blocks contain "Transferred:" with "ETA" - may be concatenated
                        if "Transferred:" in current_line and "ETA" in current_line:
                            # Extract just the Transferred: part (discard any prefix from previous line)
                            idx = current_line.find("Transferred:")
                            current_line = current_line[idx:]
                            with self._lock:
                                self.lines = []
                        with self._lock:
                            self.lines.append(current_line)
                        current_line = ""
                    else:
                        current_line += char

                # Add any remaining content
                if current_line:
                    with self._lock:
                        self.lines.append(current_line)

            finally:
                self.isDone = True

        # Create and start a daemon thread for running the subprocess
        thread = threading.Thread(target=runcommand)
        thread.daemon = True
        thread.start()

    def kill(self):
        """Terminate the running subprocess if any."""
        if self.process and self.process.poll() is None:
            self.process.terminate()

    def draw(self, stdscr):
        rows, cols = stdscr.getmaxyx()

        # Show only lines that fit on screen
        max_lines = rows - 2
        with self._lock:
            visible_lines = self.lines[-max_lines:] if self.lines else []

        # Strip leading whitespace from all lines
        stripped_lines = [line.lstrip()[:cols - 1] for line in visible_lines]

        # Find the longest line to determine block width
        max_width = max((len(line) for line in stripped_lines), default=0)

        # Center the block vertically and horizontally
        start_y = (rows - len(stripped_lines)) // 2
        start_x = max(0, (cols - max_width) // 2)

        for i, display_line in enumerate(stripped_lines):
            try:
                stdscr.addstr(start_y + i, start_x, display_line)
            except curses.error:
                pass

    def handleinput(self, c: int):
        pass


class fuzzycomponent(component):
    def __init__(self, data, offset=(0, 0)):
        super().__init__(offset)
        self.data = data
        self.topresults = []
        self.inputtext = ""
        self.selectedIndex = 0
        self.choice = None

    def draw(self, stdscr):
        rows, cols = stdscr.getmaxyx()
        maxlines = max(1, rows - self.offset[1] - 3)
        topresults = self.topresults[:maxlines]

        if len(self.topresults) > 0:
            self.selectedIndex %= min(maxlines, len(self.topresults))
        else:
            self.selectedIndex = 0

        try:
            stdscr.addstr(self.offset[1], self.offset[0], self.inputtext[:cols - self.offset[0]])
        except curses.error:
            pass
        for i, result in enumerate(topresults):
            try:
                if self.selectedIndex == i:
                    stdscr.addstr(
                        self.offset[1] + i + 2, self.offset[0], result, curses.A_REVERSE
                    )
                else:
                    stdscr.addstr(self.offset[1] + i + 2, self.offset[0], result)
            except curses.error:
                pass

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
        self.topresults = results

    def isvalid(self, c: int):
        return str(chr(c)) in string.printable

    def handleinput(self, c: int):
        if c == curses.KEY_BACKSPACE:
            self.inputtext = self.inputtext[:-1]
            self.updateresults()
        elif c == curses.KEY_ENTER or c == 10:
            if len(self.topresults) > 0 and self.selectedIndex < len(self.topresults):
                self.choice = self.topresults[self.selectedIndex]
        elif c == 27:  # Escape
            self.choice = ""
        elif c == curses.KEY_DOWN or c == 9:  # Tab
            self.selectedIndex += 1
        elif c == curses.KEY_UP or c == curses.KEY_BTAB:  # Shift+Tab
            self.selectedIndex -= 1
        elif self.isvalid(c):
            self.inputtext += chr(c)
            self.updateresults()


class choicecomponent(component):
    def __init__(self, choices: list[dict], back=False, rect=brect(0, 0, 10, 10)):
        super().__init__((0, 0))
        self.choices = choices
        self.choice = SelectedOption()
        self.back = back
        self.brect = rect
        self.selectChar = "> "
        self._needs_resize = False

        self.elements = []
        self.elementIndex = 0

        self.elements.extend(self.choices)
        if back:
            self.elements.append(CHOICE.BACK)

    def _format_entry(self, entry):
        """Format a dict entry into display name, size, and date strings."""
        name = entry.get("Name", "")
        is_dir = entry.get("IsDir", False)
        if is_dir:
            name = name.rstrip("/") + "/"
            size_str = "-"
        else:
            size_str = format_size(entry.get("Size", 0))
        date_str = format_date(entry.get("ModTime"))
        return name, size_str, date_str

    def _compute_columns(self):
        """Compute column widths for aligned rendering."""
        name_w = 0
        size_w = 0
        for entry in self.choices:
            name, size_str, _ = self._format_entry(entry)
            name_w = max(name_w, len(name))
            size_w = max(size_w, len(size_str))
        return name_w, size_w

    def draw(self, stdscr):
        # -1 for back button
        numChoicesVisible = self.brect.h - 1

        startingIndex = max(0, (self.elementIndex + 1) - numChoicesVisible)

        name_w, size_w = self._compute_columns()

        for i in range(startingIndex, len(self.elements)):
            option = self.elements[i]
            x = self.brect.x + len(self.selectChar)
            y = self.brect.y + (i - startingIndex)

            # -1 for back
            if option != CHOICE.BACK and y >= self.brect.bottom():
                continue

            is_dir = False
            if option == CHOICE.BACK:
                content = "Back"
                y = min(y + 1, self.brect.bottom())
            else:
                name, size_str, date_str = self._format_entry(option)
                is_dir = option.get("IsDir", False)
                content = f"{name:<{name_w}}  {size_str:>{size_w}}  {date_str}"

            if i == self.elementIndex:
                x -= len(self.selectChar)
                content = f"{self.selectChar}{content}"

            try:
                if option != CHOICE.BACK and is_dir:
                    stdscr.addstr(y, x, content, curses.color_pair(1))
                else:
                    stdscr.addstr(y, x, content)
            except curses.error:
                pass

    def cursorOnChoice(self):
        return self.elementIndex >= 0 and self.elementIndex < len(self.choices)

    def cursorOnBack(self):
        return self.elements[self.elementIndex] == CHOICE.BACK

    def getChoice(self) -> SelectedOption:
        """If nothing selected, CHOICE.NONE + None"""
        return self.choice

    def handleinput(self, c: int):
        if c == curses.KEY_RESIZE:
            self._needs_resize = True
            return
        elif c == curses.KEY_UP or c == ord("k"):
            self.elementIndex -= 1
        elif c == curses.KEY_DOWN or c == ord("j"):
            self.elementIndex += 1
        elif c == ord("u"):
            self.choice = SelectedOption(CHOICE.REFRESH)
        elif c == curses.KEY_ENTER or c == 10:
            if self.cursorOnChoice():
                self.choice = SelectedOption(
                    CHOICE.SELECTED, self.choices[self.elementIndex]
                )
            if self.cursorOnBack():
                self.choice = SelectedOption(CHOICE.BACK)
        elif c == ord("h") and self.back:
            self.choice = SelectedOption(CHOICE.BACK)

        elif c == ord("d"):
            if self.cursorOnChoice():
                self.choice = SelectedOption(
                    CHOICE.DOWNLOAD, self.choices[self.elementIndex]
                )

        elif c == ord("p"):
            self.choice = SelectedOption(CHOICE.UPLOAD)

        elif c == ord("q"):
            self.choice = SelectedOption(CHOICE.QUIT)

        if self.elements:
            self.elementIndex = self.elementIndex % len(self.elements)
