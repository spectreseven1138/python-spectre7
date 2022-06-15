#!/usr/bin/python3
# Downloads the copied URL to ~/Downloads/YTD using ytd

import pyperclip
from spectre7 import ytd

def main():
    url = pyperclip.paste()
    ytd.mode_single_video(url)

if __name__ == "__main__":
    main()