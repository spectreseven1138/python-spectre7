#!/usr/bin/python3
# Youtube-DL wrapper

import os
import pyperclip
from pyyoutube import Api as PyyApi
import shutil
import urllib.request
import json

import utils

youtubedl_command = "yt-dlp"
# download_directory = os.path.expanduser("/run/media/spectre7/Jedi Archives/YTD/")
download_directory = os.path.expanduser("~/Downloads/YTD/")
# download_directory = os.path.expanduser("ftp://192.168.10.222/mnt/jediarchives/YTD")
default_input_timeout_string = str(utils.default_input_timeout) + " seconds"
pyyapi = PyyApi(api_key="AIzaSyBCHf9vhjwCrUoj4JGB44Ul_CzuN1MbIlQ")

def get_playlist_title(playlist_url: str):
    return pyyapi.get_playlist_by_id(playlist_id=utils.parse_url(playlist_url)["list"]).to_dict()["items"][0]["snippet"]["title"]

def get_playlist_videos(playlist_url: str, playlist_range: list = [0, 0]):

    parsed = utils.parse_url(playlist_url)
    playlist_items = pyyapi.get_playlist_items(playlist_id=parsed["list"], count=None)

    out = [video.snippet.resourceId.videoId for video in playlist_items.items]

    if playlist_range[1] > 0:
        for i in range(playlist_range[1], len(out)):
            out.pop(playlist_range[1])

    if playlist_range[0] > 0:
        for i in range(0, playlist_range[0] - 1):
            out.pop(0)

    return out

def execute_dl_command(url: str, args: str, dir: str = download_directory):
    dir = dir.replace("'", "").replace(".", "")
    os.makedirs(dir, exist_ok=True)
    res = "720"
    command = "cd '" + dir + "' && " + youtubedl_command + " " + url + " -f 'bestvideo[height<=" + res + "]+bestaudio/best[height<=" + res + "]' " + args
    os.system(command)

def mode_single_video(url: str):
    execute_dl_command(url, "--no-playlist")

def mode_playlist(url: str):

    # Check if URL is a playlist
    if not "list" in utils.parse_url(url):
        print("URL doesn't refer to a playlist")
        exit()

    dir = download_directory
    
    unique_folder = ""
    while not unique_folder in ["y", "n"]:
        unique_folder = input("Place in unique folder (y/n)? ").lower()
    
    if unique_folder == "y":
        title = get_playlist_title(url)
        dir += title

        suffix = ""
        # while os.path.exists(dir + str(suffix)):
        #     if suffix == "":
        #         suffix = 2
        #     else:
        #         suffix += 1
        
        if suffix != "":
            dir += "_" + str(suffix)

    # yt-dlp doesn't download the playlist for some reason when using a video/playlist link
    url = utils.parse_url(url)["list"]

    first = input("Input number (i+1) of the first video to download: ")
    last = input("Input number (i+1) of the last video to download: ")

    execute_dl_command(url, "--yes-playlist --playlist-start " + first + " --playlist-end " + last + suffix, dir)
import time
def mode_album(url: str):

    # Check if URL is a playlist
    if not "list" in utils.parse_url(url):
        print("URL doesn't refer to a playlist")
        exit()
    playlist_videos = get_playlist_videos(url)

    if len(playlist_videos) == 0:
        print("Playlist is empty")
        exit()

    album_data = None
    while utils.input_yesno("Paste album data?") == "y":
        try:
            album_data = json.loads(pyperclip.paste())
            break
        except Exception as e:
            print(e)
            print("Clipboard content isn't a valid dictionary")
            album_data = None

    if album_data == None:
        album_data = utils.input_values({
            "name": {"type": str, "name": "Album name"},
            "artist": {"type": str, "name": "Album artist"},
            "year": {"type": int, "name": "Album year"},
            "cover_path": {"type": str, "name": "Album cover path (leave blank to use the first video's thumbnail)"},
            "prefix": {"type": str, "name": "Prefix to trim"},
            "suffix": {"type": str, "name": "Suffix to trim"}
        })

        if utils.input_yesno("Copy album data?") == "y":
            pyperclip.copy(json.dumps(album_data))

    dir = download_directory + get_playlist_title(url)
    suffix = ""
    while os.path.exists(dir + str(suffix)):
        if suffix == "":
            suffix = 2
        else:
            suffix += 1
    if suffix != "":
        dir += "_" + str(suffix)
    os.makedirs(dir, exist_ok=True)

    # Download first video thumbnail as cover
    if album_data["cover_path"].strip() == "":
        urllib.request.urlretrieve("https://img.youtube.com/vi/" + str(playlist_videos[0]) + "/maxresdefault.jpg", dir + "/thumbnail.jpg")
        album_data["cover_path"] = dir + "/thumbnail.jpg"
    # Copy existing local file
    elif os.path.isfile(album_data["cover_path"]):
        ext = os.path.splitext(album_data["cover_path"])[1]
        shutil.copyfile(album_data["cover_path"], dir + "/thumbnail" + ext)
        album_data["cover_path"] = dir + "/thumbnail" + ext
    # Download from URL
    else:
        ext = os.path.splitext(album_data["cover_path"])[1]
        urllib.request.urlretrieve(album_data["cover_path"], dir + "/thumbnail" + ext)
        album_data["cover_path"] = dir + "/thumbnail" + ext

    # processed_files = ["thumbnail.jpg"]
    for i, video_id in enumerate(playlist_videos):
        execute_dl_command(video_id, "--no-playlist --extract-audio --audio-quality 0 --audio-format mp3 -f bestaudio", dir)
        # print("Sleep start")
        # time.sleep(2)
        # print("Sleep end")

        for file in os.listdir(dir):
            if video_id in file:
                break
        
        title = pyyapi.get_video_by_id(video_id=video_id).items[0].snippet.title.removeprefix(album_data["prefix"]).removesuffix(album_data["suffix"])
        utils.set_audio_metadata(dir + "/" + file, i + 1, title, album_data)
        os.rename(dir + "/" + file, dir + "/" + title + ".mp3")

        # processed_files.append(title + ".mp3")
        # print("Processed: " + str(processed_files))

modes = {
    "Single video": mode_single_video,
    "Playlist": mode_playlist,
    "Music album": mode_album
}

def main():
    url = pyperclip.paste()
    print("Clipboard content: " + url)
    input_result = input("Input a URL, or input nothing to use clipboard content: ")
    if input_result.strip() != "":
        url = input_result
    
    print("Available modes:")
    for i in range(len(modes)):
        print(str(i + 1) + "- " + list(modes.keys())[i])

    mode_selection = input("\nSelect a mode: ")
    while True:
        if not mode_selection.isdigit():
            mode_selection = input("Invalid input (must be int). Select a mode: ")
        elif int(mode_selection) > len(modes) or int(mode_selection) < 1:
            mode_selection = input("Invalid input (out of range). Select a mode: ")
        else:
            break
    
    modes[list(modes.keys())[int(mode_selection) - 1]](url)

if __name__ == "__main__":
    main()