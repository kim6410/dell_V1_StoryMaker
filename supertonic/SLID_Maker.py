# -*- coding: utf-8 -*-
"""
SLID_Maker headless entrypoint for StoryMaker/Supertonic web API.

This wrapper calls slid_refactored.app._headless_cli so FastAPI can generate
MP4 slideshow files without opening the desktop GUI.
"""

from slid_refactored.app import _headless_cli, main


if __name__ == "__main__":
    import sys

    # When API passes CLI arguments, run headless mode.
    # Without arguments, keep the original desktop GUI behavior.
    if any(arg.startswith("--") for arg in sys.argv[1:]):
        _headless_cli()
    else:
        main()
