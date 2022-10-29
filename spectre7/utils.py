# Various utility functions

import sys, select
import os
import urllib.parse as urlparse
from mutagen.easyid3 import EasyID3
import mutagen
import random
import termcolor as termcolour
from termcolor import colored as coloured # :)
from importlib.machinery import SourceFileLoader
import fnmatch

logging_enabled = True
on_err = None
global_colour = ""
default_input_timeout = 5

out = sys.stdout

COLOURS = termcolour.COLORS

def set_colour(value: str):
    global global_colour
    global_colour = value

def reset_colour():
    global global_colour
    global_colour = ""

# Prompts user for input. If user enters input before timeout, input is returned. Otherwise, timeout_value is returned.
def timed_input(prompt: str, timeout: int = default_input_timeout, timeout_value=None):
    sys.stdout.write(prompt)
    sys.stdout.flush()
    ready, _, _ = select.select([sys.stdin], [], [], timeout)
    if ready:
        return sys.stdin.readline().rstrip('\n')
    else:
        sys.stdout.write('\n')
        sys.stdout.flush()
        return timeout_value

def parse_url(url: str) -> dict:
    ret = {}
    parsed = urlparse.parse_qs(urlparse.urlparse(url).query)
    for key in parsed:
        ret[key] = parsed[key][0]
    return ret

def formatPath(path: str) -> str:
    path.removesuffix("/")
    if not path.startswith("/"):
        path = "/" + path
    return path

def relativeImport(file_path: str, relative_path: str):
    print("FILE: ", file_path)
    return absoluteImport(os.path.join(os.path.dirname(file_path), relative_path))

def absoluteImport(absolute_path: str):
    print("IMPORT: ", absolute_path)
    return SourceFileLoader("", absolute_path).load_module()

# Values must be a dict, where keys are value names and values are types
def input_values(values: dict, format_names: bool = True, allow_empty: bool = False) -> dict:
    ret = {}

    for key in values:

        name = key
        if format_names:
            name = key.replace("_", " ").capitalize()

        while True:
            result = input(format_global_colour(f"Input value for {name} (", "green") + format_colour("yellow", values[key].__name__) + format_global_colour("): ", "green"))

            if not allow_empty and values[key] == str and result.strip() == "":
                err("Input must not be empty\n")
                continue

            try:
                ret[key] = values[key](result)
                break
            except:
                err("Invalid type\n")
    return ret

def input_yesno(prompt: str, options: tuple = ("y", "n")) -> str:

    if len(options) < 2:
        raise(Exception("Options must contain at least 2 items"))

    options_string = "( "
    for option in options:
        options_string += option + " / "
    options_string = options_string.removesuffix(" / ") + " )"

    message = format_global_colour(f"{prompt} {options_string}: ", "green")
    ret = input(message).lower().strip()
    while not ret in options:
        err("Invalid input\n")
        ret = input(message).lower().strip()
    return ret

# id3convert shell command must be installed (https://command-not-found.com/id3convert)
def set_audio_metadata(file_path: str, track_number: int, track_title: str, album_data: dict):

    shell_path = file_path.replace(" ", "\ ").replace("(", "\(").replace(")", "\)")

    os.system("id3convert -s " + shell_path)

    try:
        file = EasyID3(file_path)
    except mutagen.id3.ID3NoHeaderError:
        file = mutagen.File(file_path, easy=True)
        file.add_tags()
        # file = EasyID3(file_path)

    file["album"] = album_data["name"]
    file["artist"] = album_data["artist"]
    file["date"] = str(album_data["year"])
    file["title"] = track_title
    file["tracknumber"] = str(track_number)

    file.save()

    # if path_to_cover != "":
    #     audio = ID3(file_path)
    #     with open(path_to_cover, 'rb') as album_cover:
    #         audio['APIC'] = APIC(
    #             encoding=3,
    #             mime='image/jpeg',
    #             type=3, desc=u'Cover',
    #             data=album_cover.read()
    #         )
    #     audio.save()

def combine_strings_with_newline(A: str, B: str):
    prefix = ""
    while B.startswith("\n"):
        prefix += "\n"
        B = B[1:]
    return prefix + A + B

def log(msg):
    if not logging_enabled:
        return
    printc("cyan", str(msg))

def info(msg):
    if not logging_enabled:
        return
    printc("magenta", str(msg))

def warn(msg):
    printc("yellow", combine_strings_with_newline("WARNING: ", str(msg)))

def err(msg):
    printc("red", combine_strings_with_newline("ERROR: ", str(msg)))
    if on_err is not None:
        on_err()

def printc(colour: str, *messages):
    out.write("".join(format_colour(colour, msg) for msg in messages) + "\n")
    out.flush()

def format_colour(colour: str, message, attrs: list = []):
    if colour == "" or colour == "default":
        return str(message)
    return coloured(str(message), colour, attrs=attrs)

def format_global_colour(message, override_colour: str = "default"):
    return format_colour(global_colour if global_colour != "" else override_colour, message)

def get_random_termcolour():
    return list(COLOURS.keys())[int(random.random() * 10) % len(COLOURS)]

def recursiveGlob(path: str, extension: str, name: str = None, exclude_dirs: list = []):
    if name is not None:
        match = name
    else:
        match = "*"

    if extension is not None:
        match += "." + extension
    else:
        match += "*"

    matches = []
    for root, dirnames, filenames in os.walk(path):

        if root.startswith(".") or "/." in root:
            continue

        excluded = False
        for dir in exclude_dirs:
            if root.startswith(os.path.join(os.getcwd(), dir).removesuffix("/")):
                excluded = True
                break
        if excluded:
            continue

        for filename in fnmatch.filter(filenames, match):
            if filename.startswith("."):
                continue
            matches.append(os.path.join(root, filename))

    return matches

def ensureDirExists(path: str):
    if os.path.isfile(path):
        raise FileExistsError
    if os.path.isdir(path):
        return
    os.makedirs(path)

def clear():
    os.system("clear")
