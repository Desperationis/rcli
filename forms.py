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
    def __init__(self, text: str):
        super().__init__(None)
        self.components = [
            textcomponent(text, textcomponent.MIDDLE | textcomponent.TEXT_CENTERED)
        ]

    def draw(self, stdscr):
        for component in self.components:
            component.draw(stdscr)

    def getdata(self):
        return None

class commandforum(forum):
    def __init__(self, command: list[str]):
        super().__init__(None)
        self.commandcomponent = commandcomponent(command)
        self.components = [
            self.commandcomponent
        ]

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
        self.choiceComponent = choicecomponent(self.options, back, (1, 3))
        self.components = [
            self.choiceComponent,
            textcomponent(extra, textcomponent.NONE, (1, 1)),
            textcomponent(
                "[d] download   [/] search",
                textcomponent.BOTTOM | textcomponent.BAR,
                (1, 1),
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
