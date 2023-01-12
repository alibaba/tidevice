#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Wed Jan 11 2023 17:00:08 by codeskyblue
"""

from .exceptions import MuxServiceError
from ._safe_socket import PlistSocketProxy
from ._proto import PROGRAM_NAME


class Session:
    def __init__(self, s: PlistSocketProxy, session_id: str):
        self.__ps = s
        self.__session_id = session_id

    def get_plistsocket(self) -> PlistSocketProxy:
        return self.__ps
    
    def close(self):
        s = self.__ps
        s.send_packet({
            "Request": "StopSession",
            "ProtocolVersion": '2',
            "Label": PROGRAM_NAME,
            "SessionID": self.__session_id,
        })
        s.recv_packet()
    
    def __enter__(self):
        return self.__ps
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        self.__ps.close()

