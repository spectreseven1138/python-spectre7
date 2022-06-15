#!/usr/bin/python3

from zmq import Context, REQ, REP
from threading import Thread
from os import system
from typing import Callable
from pydbus import SessionBus
import time
from subprocess import check_output
from os.path import expanduser
import json
from spectre7 import utils
import fnmatch

"""

Arguments:

0: Mode [server (default), client, port, config_path]

Flags:
-s: Start MediaAPI on startup if in server mode


"""

APP_NAME = "MediaAPI"
REMOTE_PORT = 3000

class Source:
    pass

class MediaAPI:

    cmd = check_output

    MAX_TITLE_LENGTH = -1
    HIDE_DELAY = 1.0

    _config: dict = None

    _first_update: bool = True
    currentTitleScroll: int = 0
    active_media_names: list[str] = []
    vlc_dlna_cache: any = {}
    hide_delay_start_time: int = -1

    sources: list[Source] = []
    current_source: Source | None = None

    setVisibleCallback: Callable | None = None
    setCanGoNextCallback: Callable | None = None
    setCanGoPreviousCallback: Callable | None = None
    setTitleCallback: Callable | None = None
    setVolumeCallback: Callable | None = None
    setPlayingCallback: Callable | None = None

    bus = SessionBus()

    @staticmethod
    def matchRuleShort(text: str, match: str) -> bool:
        return fnmatch.fnmatch(text, match)

    @staticmethod
    def getConfigPath():
        return expanduser("~/.config/mediapanel-config.json")

    def onConfigChanged(self):
        self.sources = []
        self.current_source = None
        self.beginHide()

    def loadConfig(self, message_callback: Callable = None):
        original = self._config
        try:
            f = open(self.getConfigPath(), "r")
            self._config = json.loads(f.read())
            f.close()
            if (message_callback):
                message_callback(f"Config file at '{self.getConfigPath()}' loaded successfully")
        except Exception as e:
            self._config = original
            if (message_callback):
                message_callback(utils.format_colour("red", str(e)))
            else:
                raise e

        self.onConfigChanged()

    def saveConfig(self, message_callback: Callable = None):
        try:
            f = open(self.getConfigPath(), "w")
            f.write(json.dumps(self._config))
            if (message_callback):
                message_callback(f"Config file at '{self.getConfigPath()}' saved successfully")
        except Exception as e:
            if (message_callback):
                message_callback(str(e))
            else:
                raise e

    def beginHide(self):
        self.hide_delay_start_time = time.time()

    def cancelHide(self):
        self.hide_delay_start_time = -1
    
    def processHide(self):
        if (self.hide_delay_start_time >= 0 and (time.time() - self.hide_delay_start_time) / 1000.0 > self.HIDE_DELAY):
            if (self.setVisibleCallback):
                self.setVisibleCallback(False)
            self.hide_delay_start_time = -1

    def _updateCurrentSource(self) -> bool:

        obj = self.bus.get("org.freedesktop.DBus", "/org/freedesktop/DBus")

        available_sources: list[str] = []
        for bus in obj.ListNames():
            if not bus.startswith("org.mpris.MediaPlayer2."):
                continue

            bus = bus[23:]

            if ("source_blacklist" in self._config):
                blacklisted = False
                for player in self._config["source_blacklist"]:
                    if MediaAPI.matchRuleShort(bus, player):
                        blacklisted = True
                        break
                if (blacklisted):
                    continue

            available_sources.append(bus)

        new_sources: list[Source] = []
        current_exists = False

        for source_id in available_sources:
            
            if (len(source_id.strip()) == 0):
                continue

            existing_source: Source | None = None
            for source in self.sources:
                if (source.id == source_id):
                    existing_source = source
                    break

            if (existing_source):
                if (not existing_source.isTitleBlacklisted(self)):
                    new_sources.append(existing_source)
                    if (existing_source == self.current_source):
                        current_exists = True
            else:
                source: Source | None = Source.create(source_id, self)
                if (source):
                    new_sources.append(source)

        self.sources = new_sources

        changed = self.current_source is not None

        if (not current_exists):
            self.current_source = None

        if (len(self.sources) == 0):
            self.current_source = None
            return changed

        original_source: Source | None = self.current_source
        self.current_source = None

        for source in self.sources:
            
            if source.getStatus() != 2:
                continue

            if (self.current_source and self.current_source.last_activity >= source.last_activity):
                continue
            
            self.current_source = source

        if self.current_source is None:
            for source in self.sources:

                if (source.last_activity < 0):
                    continue

                if (self.current_source and self.current_source.last_activity >= source.last_activity):
                    continue
                
                self.current_source = source

        if self.current_source:
            self.current_source.updateLastActivity()

        return self.current_source != original_source

    # Returns True if the playing media name changed
    def update(self) -> bool:

        if (self._config is None):
            self.loadConfig()

            if (self._config is None):
                return False

        if (self.setVolumeCallback):
            volume, on = self.getVolumeData()
            self.setVolumeCallback(volume, on)

        changed: bool = self._updateCurrentSource() or self._first_update
        self._first_update = False
        
        if (changed):
            self.currentTitleScroll = 0

        if (self.current_source is None):
            if (changed):
                self.beginHide()
            self.processHide()
            return changed

        self.current_source.updateMetadata()

        if (self.setCanGoNextCallback):
            self.setCanGoNextCallback(self.current_source.getProperty("Player", "CanGoNext"))

        if (self.setCanGoPreviousCallback):
            self.setCanGoPreviousCallback(self.current_source.getProperty("Player", "CanGoPrevious"))

        if (self.setPlayingCallback):
            self.setPlayingCallback(self.current_source.getStatus() == 2)

        if (self.setTitleCallback):
            title: str = self.current_source.getReadableTitle(self)
            set_title: str = ""

            if (self.MAX_TITLE_LENGTH > 0 and len(title) > self.MAX_TITLE_LENGTH):
                set_title = title.slice(self.currentTitleScroll, min(self.currentTitleScroll + self.MAX_TITLE_LENGTH, len(title)))
                
                if (len(set_title) < self.MAX_TITLE_LENGTH):
                    set_title += "   | " + title.slice(0, self.MAX_TITLE_LENGTH - len(set_title))
                
                self.currentTitleScroll = (self.currentTitleScroll + 1) % len(title)
            else:
                set_title = title

            self.setTitleCallback(set_title)
        
        if (self.setVisibleCallback):
            self.setVisibleCallback(True)
        
        self.cancelHide()
        system("pkill -RTMIN+8 waybar")

        return changed

    def mediaForward(self):
        self.current_source.player_bus.Next()
        time.sleep(0.1)
        self.update()

    def mediaBackward(self):
        self.current_source.player_bus.Previous()
        time.sleep(0.1)
        self.update()

    def mediaPlayPause(self):
        self.current_source.player_bus.PlayPause()
        time.sleep(0.1)
        self.update()

    def getVolumeData(self, offset: int = 0) -> tuple[int, bool]:
        data: str

        try:
            data = self.cmd(["amixer", "get", "Master", "|", "grep", "'Right: '"])
        except:
            data = self.cmd(["amixer", "get", "Master", "|", "grep", "'Mono: '"])

        volume: int = int(data.slice(data.find("[") + 1, data.find("]") - 1))
        volume = max(0, min(100, volume + offset))

        on: bool = data.slice(data.rindex("[") + 1, data.rindex("]")) == "on"

        return volume, on

    def setVolume(self, value: int):
        self.cmd(["amixer", "set", "Master", f"{value}%"])

class Source:

    metadata: dict = {
        "trackid": None,
        "length": None,
        "artUrl": None,
        "album": None,
        "albumArtist": None,
        "artist": None,
        "asText": None,
        "audioBPM": None,
        "autoRating": None,
        "comment": None,
        "composer": None,
        "contentCreated": None,
        "discNumber": None,
        "firstUsed": None,
        "genre": None,
        "lastUsed": None,
        "lyricist": None,
        "title": None,
        "trackNumber": None,
        "url": None,
        "useCount": None,
        "userRating": None,
    }

    last_activity: int = -1

    api: MediaAPI
    id: str

    player_bus: object;

    def __init__(self, api: MediaAPI, id: str):
        self.api = api
        self.id = id
        self.player_bus = api.bus.get("org.mpris.MediaPlayer2." + self.id, "/org/mpris/MediaPlayer2")

    def getProperty(self, iface: str, key: str) -> any:
        if (iface != ""):
            iface = "." + iface
        return self.player_bus.Get("org.mpris.MediaPlayer2" + iface, key)

    def getStatus(self) -> int:
        match self.getProperty("Player", "PlaybackStatus"):
            case "Playing": return 2
            case "Paused": return 1
            case _: return 0

    def updateLastActivity(self):
        self.last_activity = time.time()

    def updateMetadata(self):
        metadata: dict = self.getProperty("Player", "Metadata")
        
        for key in self.metadata:
            self.metadata[key] = None

        for key in metadata:
            formatted_key = key.split(":", 2)[1]
            if (not formatted_key in self.metadata):
                print("Unknown metadata key: " + key)
                continue
            self.metadata[formatted_key] = metadata[key]

    def toString(self, api: MediaAPI | None = None) -> str:
        ret: str = f"{self.metadata['title']}\n - Status: {['Stopped', 'Paused', 'Playing'][self.getStatus()]}\n - Last active: {self.last_activity}\n - ID: {self.id}"
        if (api):
            ret += "\n - Current: " + (api.current_source == self).toString()
        return ret

    def formatTitle(self, api: MediaAPI):

        url: str = self.metadata["url"]

        if (self.id == "vlc" and url is not None and self.metadata["title"] == "audio stream" and "dlna_command" in api._config):

            if (url in api.vlc_dlna_cache):
                self.metadata["title"] = api.vlc_dlna_cache[url]
            elif (url.startsWith("http://")):
                ip: str = url.removeprefix("http://").split("/", 1)[0]

                available_servers = json.loads(api.cmd([api._config["dlna_command"], "list-servers"]))
                server: str | None = None

                for server in available_servers:
                    if (server["path"].removeprefix("http://").split("/", 1)[0] == ip):
                        server = server["path"]
                        break

                if (server is not None):
                    data = json.loads(api.cmd([api._config["dlna_command"], "search", "-s", server, "-sq", url, "-st", "path"]))
                    if (len(data) > 0):
                        self.metadata["title"] = data[0]["name"]
                        api.vlc_dlna_cache[url] = data[0]["name"]

        title: str = self.metadata["title"].removeprefix("\"").removesuffix("\"").replace("  ", " ").replace("\\\"", "\"")

        extensionIndex = title.lastIndexOf(".")
        extension = title.slice(extensionIndex + 1)
        if (not extension.includes(" ")):
            title = title.slice(0, extensionIndex)

        self.metadata["title"] = title.strip()

    def isTitleBlacklisted(self, api: MediaAPI) -> bool:
        if ("keyword_blacklist" in api._config):
            lower_name = self.metadata["title"].lower()
            for keyword in api._config["keyword_blacklist"]:
                if (lower_name.includes(keyword.lower())):
                    return True
        return False

    def getReadableTitle(self, api: MediaAPI) -> str:
        ret: str = self.metadata["title"]
        
        if ("title_replacements" in api._config and ret in api._config["title_replacements"]):
            return api._config["title_replacements"][ret].strip()

        if ("remove_brackets" in api._config):
            for pair in api._config["remove_brackets"]:
                finished = False
                while (not finished):
                    a = ret.find(pair[0])
                    if (a < 0):
                        finished = True
                        break

                    b = ret.find(pair[1])
                    if (b < 0):
                        finished = True
                        break

                    temp = ret
                    ret = temp.slice(0, a - 1) + temp.slice(b + len(pair[1]), len(temp))

        if ("substring_replacements" in api._config):
            for key in api._config["substring_replacements"]:
                ret = ret.replace(key, api._config["substring_replacements"][key])

        if (self.metadata["artist"] is not None and len(self.metadata["artist"]) > 0):
            ret = self.metadata["artist"][0] + " | " + ret

        return ret.strip()

    @staticmethod
    def create(source_id: str, api: MediaAPI) -> Source | None:

        source: Source = Source(api, source_id)
        source.updateMetadata()

        if ("artist_blacklist" in api._config and source.metadata["artist"] is not None):
            for artist in source.metadata["artist"]:
                for blacklisted_artist in api._config["artist_blacklist"]:
                    if (MediaAPI.matchRuleShort(artist, blacklisted_artist)):
                        return None

        if (source.isTitleBlacklisted(api)):
            return None

        return source

class Server:

    UPDATE_INTERVAL = 2

    api: MediaAPI = None
    thread: Thread = None

    visible: bool = False
    can_go_next: bool = False
    can_go_previous: bool = False
    title: str = ""
    volume: int = 0
    muted: bool = False
    playing: bool = False

    def listen(self, silent: bool = False):

        context = Context()
        socket = context.socket(REP)

        try:
            socket.bind(f"tcp://127.0.0.1:{REMOTE_PORT}")
        except Exception as e:
            if self.api:
                self.stop()
            raise e

        utils.log(f"Running in remote server mode at 127.0.0.1:{REMOTE_PORT}")

        try:
            
            while True:
                inp = socket.recv().decode("utf8").lower().strip()
                response = ""
                
                if inp in self.COMMANDS:
                    # utils.log(f"Command called: {inp}")
                    response = self.COMMANDS[inp](self, silent)
                elif inp == "help":
                    msg = "Available commands:"
                    for command in self.COMMANDS:
                        msg += f" - {command}\n"
                    response = msg.rstrip()
                elif inp != "":
                    response = utils.format_colour("red", f"'{inp}' is not a valid command")
                
                socket.send_string(response)

        except KeyboardInterrupt:
            print("")

        context.destroy()

    def updateThread(self):
        while self.api:
            self.api.update()
            time.sleep(self.UPDATE_INTERVAL)

    def setVisibleCallback(self, visible: bool):
        self.visible = visible
    def setCanGoNextCallback(self, can_go: bool):
        self.can_go_next = can_go
    def setCanGoPreviousCallback(self, can_go: bool):
        self.can_go_previous = can_go
    def setTitleCallback(self, title: str):
        self.title = title
    def setVolumeCallback(self, volume: int, muted: bool):
        self.volume = volume
        self.muted = muted
    def setPlayingCallback(self, playing: bool):
        self.playing = playing;
    
    # Start MediaAPI if not running
    def start(self, silent: bool = False) -> str:
        if self.api:
            msg = f"{APP_NAME} is already running"
            if silent:
                utils.log(msg)
            return msg

        self.api = MediaAPI()

        self.api.setVisibleCallback = self.setVisibleCallback
        self.api.setCanGoNextCallback = self.setCanGoNextCallback
        self.api.setCanGoPreviousCallback = self.setCanGoPreviousCallback
        self.api.setTitleCallback = self.setTitleCallback
        # TODO
        # self.api.setVolumeCallback = self.setVolumeCallback
        self.api.setPlayingCallback = self.setPlayingCallback

        self.thread = Thread(target=self.updateThread)
        self.thread.start()

        msg = f"{APP_NAME} has been started"
        if not silent:
            utils.log(msg)
        return msg

    # Stop MediaAPI if running
    def stop(self, silent: bool = False) -> str:
        if self.api is None:
            msg = f"{APP_NAME} is not running"
            if not silent:
                utils.log(msg)
            return msg
        
        self.api = None
        self.thread.join()

        msg = f"{APP_NAME} stopped"
        if not silent:
            utils.log(msg)
        return msg

    # Restart MediaAPI (starts if not running)
    def restart(self, silent: bool = False) -> str:
        if self.api:
            self.stopAPI(silent)
        return self.startAPI(silent)

    def getInfo(self, silent: bool = False) -> str:
        info = {property: getattr(self, property) for property in ("visible", "can_go_next", "can_go_previous", "title", "volume", "muted", "playing")}
        info["metadata"] = self.api.current_source.metadata if self.api.current_source is not None else None
        msg = json.dumps(info)
        if not silent:
            print(msg)
        return msg

    def reloadConfig(self, silent: bool = False) -> str:
        if not self.api:
            msg = f"{APP_NAME} is not running"
            if not silent:
                utils.err(msg)
            return msg
        
        msg = ""

        def calllback(_msg: str):
            nonlocal msg
            msg = _msg

        self.api.loadConfig(calllback)
        
        if not silent:
            utils.log(msg)
        
        return msg

    def playPause(self, silent: bool = False) -> str:
        if not self.api:
            msg = f"{APP_NAME} is not running"
            if not silent:
                utils.err(msg)
            return msg
        
        self.api.mediaPlayPause()
        
        return ""
    
    def next(self, silent: bool = False) -> str:
        if not self.api:
            msg = f"{APP_NAME} is not running"
            if not silent:
                utils.err(msg)
            return msg
        
        self.api.mediaForward()
        
        return ""

    def previous(self, silent: bool = False) -> str:
        if not self.api:
            msg = f"{APP_NAME} is not running"
            if not silent:
                utils.err(msg)
            return msg
        
        self.api.mediaBackward()
        
        return ""

    COMMANDS = {method.__name__.lower(): method for method in (start, stop, restart, getInfo, reloadConfig, playPause, next, previous)}

class Client:

    def __init__(self):
        self.context = Context()
        self.socket = self.context.socket(REQ)
        self.socket.connect(f"tcp://127.0.0.1:{REMOTE_PORT}")

    def __delete__(self):
        self.context.destroy()
    
    def call(self, command: str, silent: bool) -> str:
        command = command.lower()

        if not command in Server.COMMANDS:
            if silent:
                raise RuntimeError
            else:
                utils.err(f"'{command}' is not a valid command", on_err=None)
            return
        
        self.socket.send_string(command)
        response = self.socket.recv().decode()
        if not silent and len(response) > 0:
            print(response)
        return response

    def runInteractive(self):
        try:
            while True:
                inp = input(" : ").lower().strip()
                if inp == "clear" or inp == "c":
                    system("clear")
                elif inp in Server.COMMANDS:
                    self.call(inp, False)
                elif inp == "help":
                    msg = "\nAvailable commands:"
                    for command in Server.COMMANDS:
                        msg += f" - {command}\n"
                    print(msg.strip())
                elif inp != "":
                    utils.err(f"'{inp}' is not a valid command", on_err=None)
        except KeyboardInterrupt:
            print("")

def main():
    import sys

    args = sys.argv[1:]
    mode = "server"
    autostart = False

    if len(args) > 0:
        mode = args.pop(0).lower().strip()

        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "-s":
                autostart = True
                args.pop(i)
                i -= 1
            i += 1

    if mode == "server":
        server = Server()
        if autostart:
            server.start()
        server.listen(True)
    elif mode == "client":
        client = Client()

        if len(args) > 0:
            if args[0].lower() in Server.COMMANDS:
                client.call(args[0], False)
            else:
                utils.err(f"'{args[0]}' is not a valid command")
            return
        client.runInteractive()
    elif mode == "port":
        print(REMOTE_PORT)
    elif mode == "config_path":
        print(MediaAPI.getConfigPath())
    else:
        utils.err(f"Unknown mode '{mode}'\nAvailable modes:\n - server (default)\n - client\n - port\n - config_path")

if __name__ == "__main__":
    main()
