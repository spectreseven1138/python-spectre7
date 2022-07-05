from os import system
from typing import Callable
from pydbus import SessionBus
import time
from subprocess import check_output
from os.path import expanduser
import json
from spectre7 import utils
import fnmatch

def removeBrackets(text: str, brackets: str):
    count = [0] * (len(brackets) // 2) # count open/close brackets
    saved_chars = []
    for character in text:
        for i, b in enumerate(brackets):
            if character == b: # found bracket
                kind, is_close = divmod(i, 2)
                count[kind] += (-1)**is_close # `+1`: open, `-1`: close
                if count[kind] < 0: # unbalanced bracket
                    count[kind] = 0  # keep it
                else:  # found bracket to remove
                    break
        else: # character is not a [balanced] bracket
            if not any(count): # outside brackets
                saved_chars.append(character)
    return ''.join(saved_chars)

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
        ret = self.metadata["title"].replace("  ", " ")
        
        if ("title_replacements" in api._config and ret in api._config["title_replacements"]):
            ret = api._config["title_replacements"][ret]
        else:
            if ("remove_brackets" in api._config):
                ret = removeBrackets(ret, api._config["remove_brackets"])

            if ("substring_replacements" in api._config):
                for key in api._config["substring_replacements"]:
                    ret = ret.replace(key, api._config["substring_replacements"][key])

        if (self.metadata["artist"] is not None and len(self.metadata["artist"]) > 0):
            artist = self.metadata["artist"][0].strip()
            if "artist_replacements" in api._config and artist in api._config["artist_replacements"]:
                artist = api._config["artist_replacements"][artist]
            ret = artist + "  |  " + ret

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
