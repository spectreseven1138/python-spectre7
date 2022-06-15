from pydbus import Variant, connect as DBusConnect
from pydbus.generic import signal
from gi.repository import GLib
from threading import Thread

class MprisInterface:
    TIME_UNIT = 1000000
    INTERFACE = None
    PropertiesChanged = signal()

    def notifyPropertyChanged(self, properties: dict[str, any] | list[str] | str):

        if isinstance(properties, list):
            properties = {property: getattr(self, property) for property in properties}
        elif isinstance(properties, str):
            properties = {properties: getattr(self, properties)}
        else:
            for key in properties:
                if properties[key] is None:
                    properties[key] = getattr(self, key)

        self.PropertiesChanged(self.INTERFACE, properties, [])

class MprisMainInterface(MprisInterface):
    INTERFACE = "org.mpris.MediaPlayer2"
    dbus = f"""
    <node>
      <interface name="{INTERFACE}">
        <method name="Raise"/>
        <method name="Quit"/>
        <property name="CanQuit" type="b" access="read"/>
        <property name="CanRaise" type="b" access="read"/>
        <property name="Fullscreen" type="b" access="readwrite"/>
        <property name="CanSetFullscreen" type="b" access="read"/>
        <property name="HasTrackList" type="b" access="read"/>
        <property name="Identity" type="s" access="read"/>
        <property name="DesktopEntry" type="s" access="read"/>
        <property name="SupportedUriSchemes" type="as" access="read"/>
        <property name="SupportedMimeTypes" type="as" access="read"/>
      </interface>
    </node>
    """

    CanQuit = False
    CanRaise = False
    CanSetFullscreen = False
    HasTrackList = False
    Identity = "MprisServer"
    DesktopEntry = ""
    SupportedUriSchemes = ["file"]
    SupportedMimeTypes = ["audio/mpeg", "application/ogg", "video/mpeg"]
    
    def Raise(self):
        pass

    def Quit(self):
        pass

    @property
    def Fullscreen(self):
        return False

    @Fullscreen.setter
    def Fullscreen(self, value: bool):
        pass

class MprisPlayerInterface(MprisInterface):
    INTERFACE = MprisMainInterface.INTERFACE + ".Player"
    dbus = f"""
    <node>
      <interface name="{INTERFACE}">
        <method name="Next"/>
        <method name="Next"/>
        <method name="Previous"/>
        <method name="Pause"/>
        <method name="PlayPause"/>
        <method name="Stop"/>
        <method name="Play"/>
        <method name="Seek">
          <arg name="Offset" type="x" direction="in"/>
        </method>
        <method name="SetPosition">
          <arg name="TrackId" type="o" direction="in"/>
          <arg name="Position" type="x" direction="in"/>
        </method>
        <method name="OpenUri">
          <arg name="Uri" type="s" direction="in"/>
        </method>
        <signal name="Seeked">
          <arg name="Position" type="x"/>
        </signal>
        <property name="PlaybackStatus" type="s" access="read"/>
        <property name="LoopStatus" type="s" access="readwrite"/>
        <property name="Rate" type="d" access="readwrite"/>
        <property name="Shuffle" type="b" access="readwrite"/>
        <property name="Metadata" type="a{{sv}}" access="read"/>
        <property name="Volume" type="d" access="readwrite"/>
        <property name="Position" type="x" access="read"/>
        <property name="MinimumRate" type="d" access="read"/>
        <property name="MaximumRate" type="d" access="read"/>
        <property name="CanGoNext" type="b" access="read"/>
        <property name="CanGoPrevious" type="b" access="read"/>
        <property name="CanPlay" type="b" access="read"/>
        <property name="CanPause" type="b" access="read"/>
        <property name="CanSeek" type="b" access="read"/>
        <property name="CanControl" type="b" access="read"/>
      </interface>
    </node>
    """

    Seeked = signal()
    MinimumRate = 1.0
    MaximumRate = 1.0

    def PlayPause(self):
        if self.PlaybackStatus == "Playing":
            self.Pause()
        else:
            self.Play()

    def Play(self):
        if not self.CanPlay:
            return
    
    def Pause(self):
        if not self.CanPause:
            return

    def Stop(self):
        if not self.CanControl:
            return

    def Next(self):
        if not self.CanGoNext:
            return

    def Previous(self):
        if not self.CanGoPrevious:
            return

    def Seek(self, offset: int):
        if not self.CanSeek:
            return

    def SetPosition(self, track_id: str, position: int):
        if not self.CanSeek:
            return

    def OpenUri(self, uri: str):
        if not self.CanControl:
            return

    @property
    def PlaybackStatus(self) -> str: # -> "Playing" | "Paused" | "Stopped"
        return "Stopped"

    @property
    def LoopStatus(self) -> str: # -> "Track" | "Playlist" | "None"
        return "None"

    @LoopStatus.setter
    def LoopStatus(self, value: str): # value: "Track" | "Playlist" | "None"
        if not self.CanControl:
            return

    @property
    def Rate(self) -> float:
        return 1.0

    @Rate.setter
    def Rate(self, value: float):
        if not self.CanControl:
            return

    @property
    def Shuffle(self) -> bool:
        return False

    @Shuffle.setter
    def Shuffle(self, value: bool):
        if not self.CanControl:
            return

    def formatMetadata(self, metadata: dict) -> None:
        for key in list(metadata.keys()):
            value = metadata[key]

            try:
                if value is None:
                    metadata.pop(key)
                elif isinstance(value, str):
                    metadata[key] = Variant("o" if key == "mpris:trackid" else "s", value)
                elif isinstance(value, int) or isinstance(value, float):
                    metadata[key] = Variant("x" if key == "mpris:length" else "i", int(value))
                elif isinstance(value, list):
                    for i in range(len(value)):
                        value[i] = str(value[i])
                    metadata[key] = Variant("as", value)
                else:
                    raise TypeError(value, value.__class__)

            except Exception as e:
                import notify2
                notify2.init("bruh")
                notify2.Notification(str(e)).show()


    @property
    def Metadata(self) -> dict:
        # ret =  {
        #     "mpris:trackid": "/track/0",
        #     "mpris:artUrl": None,
        #     "xesam:url": None,
        #     "xesam:title": None,
        #     "xesam:album": None,
        #     "mpris:length": 1 * 1000,
        #     "xesam:discNumber": 0,
        #     "xesam:trackNumber": 0,
        #     "xesam:artist": [],
        #     "xesam:albumArtist": [],
        #     "xesam:comment": [],
        # }
        # self.formatMetadata(ret)
        # return ret

        return {}

    @property
    def Volume(self) -> float:
        return 0

    @Volume.setter
    def Volume(self, value: float):
        if not self.CanControl:
            return
        print(value)

    @property
    def Position(self):
        return 0

    @property
    def CanGoNext(self) -> bool:
        if not self.CanControl:
            return False
        return True

    @property
    def CanGoPrevious(self) -> bool:
        if not self.CanControl:
            return False
        return True

    @property
    def CanPlay(self) -> bool:
        if not self.CanControl:
            return False
        return True

    @property
    def CanPause(self) -> bool:
        if not self.CanControl:
            return False
        return True

    @property
    def CanSeek(self) -> bool:
        if not self.CanControl:
            return False
        return True

    @property
    def CanControl(self) -> bool:
        return True

class MprisTrackInterface(MprisInterface):
    INTERFACE = MprisMainInterface.INTERFACE + ".Tracklist"
    dbus = f"""
    <node>
        <interface name="{INTERFACE}">
        <method name="GetTracksMetadata">
            <arg name="TrackIds" type="ao" direction="in"/>
            <arg name="Metadata" type="aa{{sv}}" direction="out"/>
        </method>
        <method name="AddTrack">
            <arg name="Uri" type="s" direction="in"/>
            <arg name="AfterTrack" type="o" direction="in"/>
            <arg name="SetAsCurrent" type="b" direction="in"/>
        </method>
        <method name="RemoveTrack">
            <arg name="TrackId" type="o" direction="in"/>
        </method>
        <method name="GoTo">
            <arg name="TrackId" type="o" direction="in"/>
        </method>
        <signal name="TrackListReplaced">
            <arg name="Tracks" type="ao"/>
            <arg name="CurrentTrack" type="o"/>
        </signal>
        <signal name="TrackAdded">
            <arg name="Metadata" type="a{{sv}}"/>
            <arg name="AfterTrack" type="o"/>
        </signal>
        <signal name="TrackRemoved">
            <arg name="TrackId" type="o"/>
        </signal>
        <signal name="TrackMetadataChanged">
            <arg name="TrackId" type="o"/>
            <arg name="Metadata" type="a{{sv}}"/>
        </signal>
        <property name="Tracks" type="ao" access="read"/>
        <property name="CanEditTracks" type="b" access="read"/>
        </interface>
    </node>
    """

    TrackListReplaced = signal()
    TrackAdded = signal()
    TrackRemoved = signal()
    TrackMetadataChanged = signal()

    def GetTracksMetadata(self, track_ids: list[str]) -> dict:
        return {}

    def AddTrack(self, uri: str, after_track: str, set_as_current: bool):
        pass

    def RemoveTrack(self, track_id: str):
        pass

    def GoTo(self, track_id: str):
        pass

    @property
    def Tracks(self) -> list[str]:
        return []

    @property
    def CanEditTracks(self) -> bool:
        return True

class MprisServer():
    
    LOOP = GLib.MainLoop()
    token = None

    def __init__(self, name: str):
        self.name = name
        self.token = None

        self.main_interface = MprisMainInterface()
        self.player_interface = MprisPlayerInterface()
        self.track_interface = None

    @staticmethod
    def runLoopInThread() -> Thread:
        thread = Thread(target = MprisServer.LOOP.run)
        thread.start()
        return thread
    
    def setMainInterface(self, interface: MprisMainInterface):
        self.main_interface = interface

    def setPlayerInterface(self, interface: MprisPlayerInterface):
        self.player_interface = interface

    def setTrackInterface(self, interface: MprisTrackInterface):
        self.track_interface = interface

    def isPublished(self) -> bool:
        return self.token is not None

    def publish(self):
        bus = DBusConnect("unix:path=/run/user/1000/bus")

        interface = "/" + MprisMainInterface.INTERFACE.replace(".", "/")
        args = [MprisMainInterface.INTERFACE + "." + self.name, (interface, self.main_interface), (interface, self.player_interface)]

        if self.track_interface:
            self.main_interface.HasTrackList = True 
            args.append((interface, self.track_interface))

        self.token = bus.publish(*args)

    def unpublish(self):
        if self.token:
            self.token.unpublish()
            self.token = None
