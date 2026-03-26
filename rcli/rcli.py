#!/usr/bin/env python3
"""
Usage:
    rcli [-v] [<remote>]
    rcli --clear-cache
    rcli -h

"""

from docopt import docopt
from .cursedcli import cursedcli
import logging
import traceback
import os
import sys


def main():
    args = docopt(__doc__)
    errorStr = ""

    if args["-v"]:
        logging.basicConfig(
            filename="rcli.log",
            filemode="a",
            format="%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s",
            datefmt="%H:%M:%S",
            level=logging.DEBUG,
        )

    if args["--clear-cache"]:
        cache_file = os.path.expanduser("~/.cache/rcli/cache.json")
        if os.path.exists(cache_file):
            os.remove(cache_file)

        print("Removed cache!")
        sys.exit(0)

    cli = None
    try:
        cli = cursedcli(args["<remote>"])
        cli.start()
        cli.main()

    except KeyboardInterrupt:
        pass

    except Exception as e:
        errorStr = traceback.format_exc()

    finally:
        if cli is not None:
            cli.end()
        if len(errorStr) > 0:
            print(errorStr, file=sys.stderr)
            logging.error(errorStr)
