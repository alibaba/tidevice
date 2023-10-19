# coding: utf-8
# codeskyblue 2020/06/03
#

__all__ = ['SafeStreamSocket', 'PlistSocket', 'PlistSocketProxy']

import logging
import os
import plistlib
import socket
import ssl
import struct
import threading
import typing
import weakref
from typing import Any, Union

from ._proto import UsbmuxMessageType, LOG
from ._utils import set_socket_timeout
from .exceptions import *

logger = logging.getLogger(LOG.socket)


_n = [0]
_nlock = threading.Lock()
_id_numbers = []

def acquire_uid() -> int:
    _id = None
    with _nlock:
        _n[0] += 1
        _id_numbers.append(_n[0])
        _id = _n[0]
    logger.debug("Opening socket: id=%d", _id)
    return _id


def release_uid(id: int):
    try:
        _id_numbers.remove(id)
    except ValueError:
        pass
    logger.debug("Closing socket, id=%d", id)
    


class SafeStreamSocket:
    def __init__(self, addr: Union[str, typing.Tuple[str, int], socket.socket,
                                   Any]):
        """
        Args:
            addr: can be /var/run/usbmuxd or localhost:27015 or (localhost, 27015)
        """
        self._id = acquire_uid()
        self._sock = None
        self._dup_sock = None # keep original sock when switch_to_ssl
        self._name = None

        if isinstance(addr, socket.socket):
            self._sock = addr
        else:
            if isinstance(addr, str):
                if ':' in addr:
                    host, port = addr.split(":", 1)
                    addr = (host, int(port))
                    family = socket.AF_INET
                elif os.path.exists(addr):
                    family = socket.AF_UNIX
                else:
                    raise SocketError("socket unix:{} unable to connect".format(addr))
            else:
                family = socket.AF_INET
            self._sock = socket.socket(family, socket.SOCK_STREAM)
            self._sock.connect(addr)

        self._finalizer = weakref.finalize(self, self._cleanup)
    
    def _cleanup(self):
        release_uid(self.id)
        sock = self._dup_sock or self._sock
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        sock.close()

    def close(self):
        self._finalizer()
        
    @property
    def closed(self) -> bool:
        return not self._finalizer.alive

    @property
    def id(self) -> int:
        return self._id

    @property
    def name(self) -> str:
        return self._name
    
    @name.setter
    def name(self, new_name: str):
        self._name = new_name

    def get_socket(self) -> socket.socket:
        return self._sock

    def recv(self, bufsize: int = 4096) -> bytes:
        """recv data from socket
        Args:
            bufsize: buffer size

        Raises:
            SocketError
        """
        try:
            return self._sock.recv(bufsize)
        except socket.timeout as e:
            raise SocketError("socket timeout") from e
        except ssl.SSLError as e:
            raise SocketError("ssl error") from e
        except Exception as e:
            raise SocketError("socket error") from e

    def recvall(self, size: int) -> bytearray:
        buf = bytearray()
        while len(buf) < size:
            chunk = self.recv(size-len(buf))
            if not chunk:
                raise SocketError("recvall: socket connection broken")
            buf.extend(chunk)
        return buf

    def sendall(self, data: Union[bytes, bytearray]) -> int:
        try:
            return self._sock.sendall(data)
        except Exception as e:
            raise SocketError("sendall error") from e

    def ssl_unwrap(self):
        assert isinstance(self._sock, ssl.SSLSocket)
        self._sock.close()
        self._sock = self._dup_sock
        self._dup_sock = None

    def switch_to_ssl(self, pemfile):
        """ wrap socket to SSLSocket """
        logger.debug("Socket(%d): switch to ssl", self.id)
        assert os.path.isfile(pemfile)
        
        # https://docs.python.org/zh-cn/3/library/ssl.html#ssl.SSLContext
        context = ssl.SSLContext(ssl.PROTOCOL_TLS)
        try:
            context.verify_mode = ssl.CERT_NONE # try to fix ssl.SSLEOFError: EOF occurred in violation of protocol (_ssl.c:1123)
            context.set_ciphers("ALL:@SECLEVEL=0") # fix md_too_weak error
        except ssl.SSLError:
            # ignore: no ciphers can be selected.
            pass
        self._dup_sock = self._sock.dup()

        context.load_cert_chain(pemfile, keyfile=pemfile)
        context.check_hostname = False
        ssock = context.wrap_socket(self._sock, server_hostname="iphone.localhost")
        self._sock = ssock

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


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

    def is_secure(self) -> bool:
        return isinstance(self._sock, ssl.SSLSocket)

    def send_packet(self, payload: dict, message_type: int = UsbmuxMessageType.PLIST):
        """
        Args:
            payload: required

            # The following args only used in the first request
            message_type: 8 (Plist)
            tag: int
        """
        logger.debug("SEND(%d): %s", self.id, payload)

        body_data = plistlib.dumps(payload)
        if self._first:  # first package
            length = 16 + len(body_data)
            header = struct.pack(
                "IIII", length, 1, message_type,
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
            logger.debug("RECV(%d): %s", self.id, payload)
        return payload


class PlistSocketProxy:
    def __init__(self, psock: typing.Union[PlistSocket, "PlistSocketProxy"]):
        if isinstance(psock, PlistSocketProxy):
            psock._finalizer.detach()
            self.__dict__.update(psock.__dict__)
        else:
            assert isinstance(psock, PlistSocket)
            self._psock = psock

        self._finalizer = weakref.finalize(self, self._psock.close)
        self.prepare()
    
    @property
    def psock(self) -> PlistSocket:
        return self._psock
    
    @property
    def name(self) -> str:
        return self.psock.name
    
    @name.setter
    def name(self, new_name: str):
        self.psock.name = new_name
    
    def prepare(self):
        pass

    def get_socket(self) -> socket.socket:
        return self.psock.get_socket()

    def send_packet(self, payload: dict, message_type: int = 8):
        return self.psock.send_packet(payload, message_type)
    
    def recv_packet(self, header_size=None) -> dict:
        return self.psock.recv_packet(header_size)
    
    def send_recv_packet(self, payload: dict, timeout: float = 10.0) -> dict:
        with set_socket_timeout(self.psock.get_socket(), timeout):
            self.send_packet(payload)
            return self.recv_packet()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self._finalizer()
    
    @property
    def closed(self) -> bool:
        return not self._finalizer.alive
    
    