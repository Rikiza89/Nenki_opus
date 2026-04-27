"""Portable launcher — adds the directory containing this file to sys.path,
then starts the memorial app. Works whether running from a USB drive or a
local installation alongside embedded Python."""

import sys
import os

_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

from memorial_app.app.main import main

if __name__ == "__main__":
    main()
