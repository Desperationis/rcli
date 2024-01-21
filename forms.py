import curses
from abc import ABC, abstractmethod
from typing import Optional
from enums import CHOICE, SCENES
from components import *


class forum(ABC):
    def __init__(self, registerKeyFunc):
        self.registerKeyFunc = registerKeyFunc

    @abstractmethod
    def draw(self, stdscr):
        pass

    @abstractmethod
    def getdata(self) -> Optional[object]:
        """Returns None if user has not done something with this forum."""
        pass


class loadingforum(forum):
    def __init__(self, text: str | list[str]):
        super().__init__(None)
        self.components = []
        if isinstance(text, str):
            self.components.append(textcomponent(text, textcomponent.MIDDLE | textcomponent.TEXT_CENTERED))
        else:
            startingy = curses.LINES // 2 - len(text)//2
            for i, line in enumerate(text):
                y = startingy + i
                self.components.append(textcomponent(line, textcomponent.TEXT_CENTERED, (0,y)))



    def draw(self, stdscr):
        for component in self.components:
            component.draw(stdscr)

    def getdata(self):
        return None


class commandforum(forum):
    def __init__(self, command: list[str]):
        super().__init__(None)
        self.commandcomponent = commandcomponent(command)
        self.components = [self.commandcomponent]

    def draw(self, stdscr):
        for component in self.components:
            component.draw(stdscr)

    def getdata(self):
        if self.commandcomponent.isDone:
            return True
        return None


class choiceforum(forum):
    def __init__(self, options, back: bool, extra: str, registerKeyFunc):
        super().__init__(registerKeyFunc)
        self.options = options
        self.choiceComponent = choicecomponent(self.options, back, brect(1, 3, 20, 20))
        self.components = [
            self.choiceComponent,
            textcomponent(extra, textcomponent.NONE, (1, 1)),
            textcomponent(
                "[d]ownload   [u] refresh   [/] search    [jk] up/down   [h] back    [q] quit",
                textcomponent.BOTTOM | textcomponent.BAR,
            ),
        ]

        for co in self.components:
            registerKeyFunc(co.handleinput)

    def draw(self, stdscr):
        for component in self.components:
            component.draw(stdscr)

    def getdata(self):
        if self.choiceComponent.getChoice().choice != CHOICE.NONE:
            return self.choiceComponent.getChoice()

        return None


class fuzzyforum(forum):
    def __init__(self, pathList, registerKeyFunc):
        self.fuzzycomponent = fuzzycomponent(pathList, offset=(1, 2))
        self.components = [
            textcomponent("Search file: ", textcomponent.NONE, (1, 1)),
            self.fuzzycomponent,
            textcomponent("[esc] back", textcomponent.BOTTOM | textcomponent.BAR),
        ]

        for co in self.components:
            registerKeyFunc(co.handleinput)

    def draw(self, stdscr):
        for component in self.components:
            component.draw(stdscr)

    def getdata(self):
        if self.fuzzycomponent.choice != None:
            return self.fuzzycomponent.choice

        return None
