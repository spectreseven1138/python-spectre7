from mprisserver import *
from random import randint
import time

def rand():
    return randint(1, 100)

class Player(MprisPlayerInterface):
    @property
    def Metadata(self): 
        ret =  {
            "mpris:trackid": "/track/0",
            "mpris:artUrl": None,
            "xesam:url": None,
            "xesam:title": None,
            "xesam:album": None,
            "mpris:length": None,
            "xesam:discNumber": 1,
            "xesam:trackNumber": 1,
            "xesam:artist": [],
            "xesam:albumArtist": [],
            "xesam:comment": [],
        }

        self.formatMetadata(ret)
        return ret

server = MprisServer("bruh")
# server.setPlayerInterface(Player())
server.publish()

MprisServer.LOOP.run()