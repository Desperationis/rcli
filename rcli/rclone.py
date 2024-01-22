import os
import time
import subprocess
import logging
import json


class rclone:
    def rclone(self, args: list[str], capture=False):
        args.insert(0, "rclone")

        if not capture:
            os.system(" ".join(args))
        else:
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            output, error = process.communicate()

            return output

    def getAllPaths(self, remote: str):
        paths = self.rclone(["ls", remote], capture=True).split("\n")
        paths = [path.lstrip() for path in paths]
        return [" ".join(path.split(" ")[1:]) for path in paths]

    def getFileStructure(self, paths: list[str]):
        fileStructure = {}

        for path in paths:
            parts = path.split("/")
            currentLevel = fileStructure

            for part in parts:
                if part not in currentLevel:
                    currentLevel[part] = {}
                currentLevel = currentLevel[part]

        return fileStructure

    def displayFileStructure(self, fileStructure, indent=0):
        for key, value in fileStructure.items():
            logging.debug("  " * indent + f"- {key}")
            if value:
                self.displayFileStructure(value, indent + 1)

    def lsf(self, fileStructure):
        output = []
        for key in fileStructure:
            if len(key) > 0:
                if len(fileStructure[key]) > 0:
                    output.append(key + "/")
                else:
                    output.append(key)

        return output


class rclonecache:
    def __init__(self):
        self.cachePath = os.path.expanduser("~/.cache/rcli/cache.json")
        self.rclone = rclone()
        os.makedirs(os.path.expanduser("~/.cache/rcli/"), exist_ok=True)

    def getFileStructure(self, remote: str):
        paths = self.getPaths(remote)
        return self.rclone.getFileStructure(paths)

    def getPaths(self, remote: str):
        if not os.path.exists(self.cachePath):
            self.refreshCache(remote)

        cache = {}
        with open(self.cachePath, "r") as file:
            cache = json.load(file)

        if remote not in cache:
            self.refreshCache(remote)
            return self.getPaths(remote)

        if time.time() - cache[remote]["timestamp"] > 60 * 60:  # An Hour
            self.refreshCache(remote)
            return self.getPaths(remote)

        return cache[remote]["data"]

    def refreshCache(self, remote: str):
        cache = {}
        if os.path.exists(self.cachePath):
            with open(self.cachePath, "r") as file:
                cache = json.load(file)

        paths = self.rclone.getAllPaths(remote)
        data = { remote: {} }
        data[remote]["timestamp"] = time.time()
        data[remote]["data"] = paths
        cache.update(data)
        with open(self.cachePath, "w") as file:
            json.dump(cache, file, indent=2)


