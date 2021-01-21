# coding: utf-8
# codeskyblue 2020/06/03
#

__all__ = ['SafeStreamSocket', 'PlistSocket']

import logging
import os
import socket
import ssl
import struct
import plistlib

from typing import Union, Any
from .exceptions import *
from ._proto import PROGRAM_NAME

logger = logging.getLogger(PROGRAM_NAME)


class SafeStreamSocket():
    def __init__(self, addr: Union[str, tuple, socket.socket,
                                   Any]):
        """
        Args:
            addr: can be /var/run/usbmuxd or (localhost, 27015)
        """
        self._sock = None
        if isinstance(addr, socket.socket):
            self._sock = addr
            return
        if isinstance(addr, SafeStreamSocket):  # copy self
            self._sock = addr._sock
            return

        if isinstance(addr, str):
            if ':' in addr:
                host, port = addr.split(":", 1)
                addr = (host, int(port))
                family = socket.AF_INET
            elif os.path.exists(addr):
                family = socket.AF_UNIX
            else:
                raise MuxError("socket unix:{} unable to connect".format(addr))
        else:
            family = socket.AF_INET
        self._sock = socket.socket(family, socket.SOCK_STREAM)
        self._sock.connect(addr)

    def recvall(self, size: int) -> bytearray:
        buf = bytearray()
        while len(buf) < size:
            chunk = self._sock.recv(size - len(buf))
            if not chunk:
                raise MuxError("socket connection broken")
            buf.extend(chunk)
        return buf

    def sendall(self, data: Union[bytes, bytearray]) -> int:
        return self._sock.sendall(data)

    def switch_to_ssl(self, pemfile):
        """ wrap socket to SSLSocket """
        # logger.debug("Switch to ssl")
        assert os.path.isfile(pemfile)
        self._dup_sock = self._sock.dup()
        ssock = ssl.wrap_socket(self._sock,
                                keyfile=pemfile,
                                certfile=pemfile,
                                ssl_version=ssl.PROTOCOL_TLSv1)
        self._sock = ssock

    def close(self):
        logger.debug("Socket %r closed", self)
        self._sock.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
    
    #def __del__(self):
    #    self.close()


class PlistSocket(SafeStreamSocket):
    def __init__(self, addr: str, tag: int = 0):
        super().__init__(addr)
        if isinstance(addr, PlistSocket):
            self._tag = addr._tag
            self._first = addr._first
        else:
            self._tag = tag
            self._first = True
        self.prepare()

    def prepare(self):
        pass

    def is_secure(self):
        return isinstance(self._sock, ssl.SSLSocket)

    def send_packet(self, payload: dict, reqtype: int = 8):
        """
        Args:
            payload: required

            # The following args only used in the first request
            reqtype: request type, always 8 
            tag: int
        """
        #if self.is_secure():
        #    logger.debug(secure_text + " send: %s", payload)
        #else:
        # logger.debug("send: %s", payload)

        body_data = plistlib.dumps(payload)
        if self._first:  # first package
            length = 16 + len(body_data)
            header = struct.pack(
                "IIII", length, 1, reqtype,
                self._tag)  # version: 1, request: 8(?), tag: 1(?)
        else:
            header = struct.pack(">I", len(body_data))
        self.sendall(header + body_data)

    def recv_packet(self, header_size=None) -> dict:
        if self._first or header_size == 16:  # first receive
            header = self.recvall(16)
            (length, version, resp, tag) = struct.unpack("IIII", header)
            length -= 16  # minus header length
            self._first = False
        else:
            header = self.recvall(4)
            (length, ) = struct.unpack(">I", header)

        body_data = self.recvall(length)
        payload = plistlib.loads(body_data)
        if 'PairRecordData' in payload:
            logger.debug("Recv pair record data ...")
        else:
            #if self.is_secure():
            #    logger.debug(secure_text + " recv" + Color.END + ": %s",
            #                 payload)
            #else:
            pass
            # logger.debug("recv: %s", payload)
        return payload

    def send_recv_packet(self, payload: dict) -> dict:
        self.send_packet(payload)
        return self.recv_packet()
