#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Mon Feb 01 2021 14:09:21 by codeskyblue

Same as iproxy
"""

import simple_tornado
from logzero import logger
from tornado.ioloop import IOLoop
from tornado.iostream import IOStream, StreamClosedError
from tornado.tcpserver import TCPServer

from ._device import Device


class RelayTCPServer(TCPServer):
    def __init__(self, device: Device, device_port: int):
        """
        Args:
            port (int): forward to port
        """
        self.__device = device
        self.__port = device_port
        super().__init__()

    # Override
    async def handle_stream(self, stream, address):
        logger.debug("handle stream from: %s", address)
        d = self.__device
        plconn = d.create_inner_connection(self.__port)
        asock = IOStream(plconn._sock)
        self._pipe_twoway(asock, stream)

    def _pipe_twoway(self, _in: IOStream, out: IOStream):
        io_loop = IOLoop.current()
        io_loop.add_callback(self._pipe_stream, _in, out)
        io_loop.add_callback(self._pipe_stream, out, _in)

    async def _pipe_stream(self, _in: IOStream, out: IOStream):
        while not _in.closed():
            try:
                data = await _in.read_bytes(10240, partial=True)
                await out.write(data)
            except StreamClosedError as e:
                _in.close() # here may call twice
                out.close()


def relay(d: Device, lport: int, rport: int):
    """
    relay tcp data from pc to device
    
    Args:
        lport: local port
        rport: remote port
    """
    simple_tornado.patch_for_windows()
    RelayTCPServer(device=d, device_port=rport).listen(lport)

    try:
        IOLoop.instance().start()
    except KeyboardInterrupt:
        IOLoop.instance().stop()
