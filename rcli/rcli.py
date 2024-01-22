#!/usr/bin/env python3
"""
Usage:
    rcli <remote>
    rcli -h

"""

from docopt import docopt
from cursedcli import cursedcli
import logging
import traceback


args = docopt(__doc__)

if __name__ == "__main__":
    errorStr = ""

    logging.basicConfig(
        filename="rcli.log",
        filemode="a",
        format="%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        level=logging.DEBUG,
    )

    try:
        cli = cursedcli(args["<remote>"])
        cli.start()
        cli.main()

    except Exception as e:
        errorStr = traceback.format_exc()

    finally:
        cli.end()
        if len(errorStr) > 0:
            logging.error(errorStr)
