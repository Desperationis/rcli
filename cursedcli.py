import curses
from typing import Optional
from enums import SCENES
from forms import *
from scenes import *
from rclone import *
import logging


class cursedcli:
    def __init__(self, remote):
        self.stdscr = curses.initscr()
        self.remote = remote

    def start(self):
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        curses.start_color()
        curses.use_default_colors()  # Without this color pair has no transparent background
        curses.set_escdelay(25)  # Without this there is a lag when pressing escape
        self.stdscr.keypad(True)

        curses.init_pair(1, curses.COLOR_CYAN, -1)

    def main(self):
        self.stdscr.erase()

        content = [
            "                     /$$ /$$",
            "                    | $$|__/",
            "  /$$$$$$   /$$$$$$$| $$ /$$",
            " /$$__  $$ /$$_____/| $$| $$",
            "| $$  \__/| $$      | $$| $$",
            "| $$      | $$      | $$| $$",
            "| $$      |  $$$$$$$| $$| $$",
            "|__/       \_______/|__/|__/",
            "",
            "v1.0.0",
            "Copyright (c) 2024 Diego Contreras",
            "MIT License",
            "",
            "Creating database and storing to cache, please be patient.",
        ]
        loadingforum(content).draw(self.stdscr)
        self.stdscr.refresh()

        cache = rclonecache()
        fileStructure = cache.getFileStructure(self.remote)
        allPaths = cache.getPaths(self.remote)

        scene = choosefilescene(fileStructure)
        while True:
            self.stdscr.erase()
            scene.show(self.stdscr)
            self.stdscr.refresh()

            nextScene: Optional[int] = scene.getNextScene()
            if nextScene == SCENES.FUZZY_SEARCH:
                scene = fuzzyscene(allPaths)

            if nextScene == SCENES.CHOOSE_FILE:
                filePath: str = scene.getdata()
                initialFolder = list(
                    filter(None, filePath.split("/"))
                )  # Removes empty strings
                initialFolder = initialFolder[:-1]  # Parent folder path
                scene = choosefilescene(fileStructure, initialFolder)

            if nextScene == SCENES.DOWNLOAD:
                downloadPath: str = self.remote + scene.getdata()
                scene = downloadscene(downloadPath, ".")

            if nextScene == SCENES.REFRESH_DATABASE:
                loadingforum("Refreshing cache, please be patient.").draw(self.stdscr)
                self.stdscr.refresh()
                cache = rclonecache()
                cache.refreshCache(self.remote)
                fileStructure = cache.getFileStructure(self.remote)
                allPaths = cache.getPaths(self.remote)
                scene = choosefilescene(fileStructure, "")

            if nextScene == SCENES.EXIT:
                break

    def end(self):
        curses.nocbreak()
        self.stdscr.keypad(False)
        curses.echo()
        curses.curs_set(1)
        curses.endwin()
