#!/usr/bin/python3

from zmq import Context, REQ, REP, error
from threading import Thread
from os import system
from time import sleep
import json
from spectre7 import utils
import notify2

from spectre7.mediaAPI import MediaAPI

"""

Arguments:

0: Mode [server (default), client, port, config_path]

Flags:
-s: Start MediaAPI on startup if in server mode
-n: Send system notification on server startup

"""

APP_NAME = "MediaAPI"
REMOTE_PORT = 3000
CONNECTION_TIMEOUT = 1000

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

    def listen(self, silent: bool = False, notify: bool = False):

        context = Context()
        socket = context.socket(REP)
        socket.RCVTIMEO = CONNECTION_TIMEOUT

        try:
            socket.bind(f"tcp://127.0.0.1:{REMOTE_PORT}")
        except Exception as e:
            if self.api:
                self.stop()
            raise e

        utils.log(f"Running in remote server mode at 127.0.0.1:{REMOTE_PORT}")

        if notify:
            notify2.init("MediaAPI")
            notification = notify2.Notification(f"MediaAPI server running on port {REMOTE_PORT}")
            notification.timeout = 2000
            notification.show()

        try:
            while True:
                try:
                    inp = socket.recv().decode("utf8").lower().strip()
                except error.Again:
                    continue

                response = ""
                
                if inp in self.COMMANDS:
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
            sleep(self.UPDATE_INTERVAL)

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
        info["source"] = self.api.current_source.id if self.api.current_source is not None else None

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
        self.socket.RCVTIMEO = CONNECTION_TIMEOUT

    def __delete__(self):
        self.context.destroy()
    
    def call(self, command: str, silent: bool) -> str:
        command = command.lower()

        if not command in Server.COMMANDS:
            if silent:
                raise RuntimeError
            else:
                utils.err(f"'{command}' is not a valid command")
            return
        
        self.socket.send_string(command)

        try:
            response = self.socket.recv().decode()
        except error.Again as e:
            response = utils.format_colour("red", str(e) + f" (timed out after {CONNECTION_TIMEOUT}ms)")
        
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
                    utils.err(f"'{inp}' is not a valid command")
        except KeyboardInterrupt:
            print("")

def main():
    import sys

    args = sys.argv[1:]
    mode = "client"
    autostart = False
    notify = False

    if len(args) > 0:
        mode = args.pop(0).lower().strip()

        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "-s":
                autostart = True
            elif arg == "-n":
                notify = True
            else:
                i += 1
                continue
            
            args.pop(i)

    if mode == "server":
        server = Server()
        if autostart:
            server.start()
        server.listen(True, notify)
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
