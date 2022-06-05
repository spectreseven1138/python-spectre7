#!/usr/bin/python3
# Controls microphone audio loopback

import os

def enable():
    os.system("pactl load-module module-loopback latency_msec=1")

def disable():
    os.system("pactl unload-module module-loopback")

def main():
    import sys
    
    args = sys.argv
    args.pop(0)

    try:
        args[0] = str(args[0]).lower()
    except IndexError:
        args.append("")

    if args[0] == "on":
        enable()
    elif args[0] == "off":
        disable()
    else:
        print("Please pass ON or OFF as an argument")

if __name__ == "__main__":
    main()