#!/usr/bin/python3

import json
import sys
import struct
from typing import Any, Callable, Optional

class BrowserAPI:

    CallbackType = Callable[[Any], bool]

    def __init__(self):
        self.setCallback(lambda message : True)

    def _getMessage(self):
        raw_length = sys.stdin.buffer.read(4)

        if not raw_length:
            sys.exit(0)
        
        message_length = struct.unpack('=I', raw_length)[0]
        message = sys.stdin.buffer.read(message_length).decode("utf-8")

        while ("\\\"" in message):
            message = message.replace("\\\"", "\"")
        message = message.replace("\"{", "{").replace("}\"", "}")

        return json.loads(message)

    def sendMessage(self, message):
        encoded_content = json.dumps(message).encode("utf-8")
        sys.stdout.buffer.write(struct.pack('=I', len(encoded_content)))
        sys.stdout.buffer.write(struct.pack(str(len(encoded_content))+"s",encoded_content))
        sys.stdout.buffer.flush()

    def setCallback(self, callback: CallbackType):
        self.message_received_callback = callback

    def getCallback(self) -> CallbackType:
        return self.message_received_callback

    def listenForMessages(self, callback: Optional[CallbackType] = None, passthrough: bool = True) -> Any:
        while True:
            message = self._getMessage()
            callback = self.getCallback() if callback is None else callback

            if not callback(message):
                return message
            elif passthrough and callback != self.getCallback():
                self.getCallback()(message)