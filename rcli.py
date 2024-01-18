#!/usr/bin/env python3
"""
Usage:
    rcli <remote>
    rcli -h

"""

from docopt import docopt
from cursedcli import cursedcli
import logging

args = docopt(__doc__)

if __name__ == "__main__":
    """allPaths = rclone(["ls", args["<remote>"]], capture=True).split("\n")
    allPaths = [path.lstrip() for path in allPaths]
    allPaths = [" ".join(path.split(" ")[1:]) for path in allPaths]
    
    p = buildFileStructure(allPaths)
    root = p

    while True:
        options = genOptions(root)"""

    errorStr = ""

    logging.basicConfig(filename="rcli.log",
                    filemode='a',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.DEBUG)

    try:
        cli = cursedcli()
        cli.start()
        cli.main()

    except Exception as e:
        errorStr = str(e)

    finally:
        cli.end()
        if len(errorStr) > 0:
            logging.error(errorStr)
