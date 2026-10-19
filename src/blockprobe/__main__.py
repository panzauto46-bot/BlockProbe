import sys

from . import __version__

if __name__ == "__main__":
    if "--version" in sys.argv:
        print(__version__)
    else:
        print("blockprobe")
