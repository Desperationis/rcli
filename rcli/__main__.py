#!/usr/bin/env python3

# Execute with
# $ python -m rcli

import sys

if __package__ is None and not getattr(sys, 'frozen', False):
    # direct call `python3 rcli/__main__.py`
    import os.path
    path = os.path.realpath(os.path.abspath(__file__))
    sys.path.insert(0, os.path.dirname(os.path.dirname(path)))

from rcli import main

if __name__ == '__main__':
    main()
