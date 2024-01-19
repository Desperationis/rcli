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
        """Returns None if user has not done something with this forum.
        """
        pass

class loadingforum(forum):
    def __init__(self, text: str):
        super().__init__(None)
        self.components = [
                textcomponent(text, (0, 1))
        ]

    def draw(self, stdscr):
        for component in self.components:
            component.draw(stdscr)

    def getdata(self):
        return None

class choiceforum(forum):
    def __init__(self, options, back: bool, extra: str, registerKeyFunc):
        super().__init__(registerKeyFunc)
        self.options = options
        self.choiceComponent = choicecomponent(self.options, back, (1,3))
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

class fuzzyforum(forum):
    def __init__(self, pathList, registerKeyFunc):
        self.components = [
            textcomponent("Search file: ", (1,1)),
            fuzzycomponent(pathList, offset=(1,2))
        ]

        for co in self.components:
            registerKeyFunc(co.handleinput)

    def draw(self, stdscr):
        for component in self.components:
            component.draw(stdscr)

    def getdata(self):
        return None

