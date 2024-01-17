#!/usr/bin/env python3
"""
Usage:
    rcli <remote>
    rcli -h

"""

from simple_term_menu import TerminalMenu
from docopt import docopt
import os
import sys 
import subprocess

def rclone(args : list[str], capture=False):
    args.insert(0, "rclone")

    if not capture:
        os.system(" ".join(args))
    else:
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        output, error = process.communicate()

        return output


def buildFileStructure(paths):
    fileStructure = {}

    for path in paths:
        parts = path.split("/")
        currentLevel = fileStructure

        for part in parts:
            if part not in currentLevel:
                currentLevel[part] = {}
            currentLevel = currentLevel[part]

    return fileStructure

def displayFileStructure(fileStructure, indent=0):
    for key, value in fileStructure.items():
        print("  " * indent + f"- {key}")
        if value:
            display_fileStructure(value, indent + 1)

def genOptions(path):
    output = []
    for key in path:
        if len(key) > 0:
            if len(path[key]) > 0:
                output.append(key + "/")
            else:
                output.append(key)

    return output


args = docopt(__doc__)

if __name__ == "__main__":
    allPaths = rclone(["ls", args["<remote>"]], capture=True).split("\n")
    allPaths = [path.lstrip() for path in allPaths]
    allPaths = [" ".join(path.split(" ")[1:]) for path in allPaths]
    
    p = buildFileStructure(allPaths)
    root = p

    while True:
        options = genOptions(root)
        terminal_menu = TerminalMenu(options)
        menu_entry_index = terminal_menu.show()
        print(f"You have selected {options[menu_entry_index]}!")
        folder = options[menu_entry_index].replace("/","")
        root = root[folder]
