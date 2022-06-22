#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Mon Feb 01 2021 14:09:21 by codeskyblue

Same as iproxy
"""

import colored
import simple_tornado
from logzero import logger
from tornado.ioloop import IOLoop
from tornado.iostream import IOStream, StreamClosedError
from tornado.tcpserver import TCPServer

from ._device import Device
from ._hexdump import hexdump
from ._safe_socket import PlistSocketProxy
from .exceptions import MuxReplyError


class RelayTCPServer(TCPServer):
    def __init__(self, device: Device, device_port: int, debug: bool = False):
        """
        Args:
            port (int): forward to port
        """
        self.__device = device
        self.__port = device_port
        self.__debug = debug
        self.__names = {}
        super().__init__()

    # Override
    async def handle_stream(self, stream: IOStream, address):
        d = self.__device
        logger.debug("[%s] handle stream from: %s", d.udid, address)
        d._info = None # Force to refresh devId
        try:
            plconn = d.create_inner_connection(self.__port)
            asock = IOStream(plconn.get_socket())
            self._pipe_twoway(asock, stream, plconn)

            self.__names[stream] = address
        except MuxReplyError as e:
            logger.error("connect to device error: %s", e)
            stream.close()

    def _pipe_twoway(self, _in: IOStream, out: IOStream, plconn):
        io_loop = IOLoop.current()
        io_loop.add_callback(self._pipe_stream, _in, out, plconn)
        io_loop.add_callback(self._pipe_stream, out, _in, plconn)

    async def _pipe_stream(self, _in: IOStream, out: IOStream, plconn: PlistSocketProxy):
        while not _in.closed():
            try:
                data = await _in.read_bytes(10240, partial=True)
                if self.__debug:
                    if self.__names.get(_in):
                        print("{} >>> device".format(self.__names[_in]))
                        print(colored.fg("green") + colored.bg("black"), end="", flush=True)
                    else:
                        print("device >>> {}".format(self.__names[out]))
                        print(colored.fg("orchid") + colored.bg("black"), end="", flush=True)
                    hexdump(data)
                    print(colored.attr("reset"), end="", flush=True)
                await out.write(data)
            except StreamClosedError as e:
                break

        # here may call twice
        _in.close() 
        out.close()
        plconn.close()
        self.__names.pop(_in, None)


def relay(d: Device, lport: int, rport: int, debug: bool = False):
    """
    relay tcp data from pc to device

    Args:
        lport: local port
        rport: remote port
    """
    simple_tornado.patch_for_windows()
    RelayTCPServer(device=d, device_port=rport, debug=debug).listen(lport)

    try:
        IOLoop.instance().start()
    except KeyboardInterrupt:
        IOLoop.instance().stop()
