#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Mon Feb 01 2021 14:09:21 by codeskyblue

Same as iproxy
"""

import select
import socket
import time
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


# Changing the buffer_size and delay, you can improve the speed and bandwidth.
# But when buffer get to high or delay go too down, you can broke things
BUFFER_SIZE = 4096
DELAY = 0.0001


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

class Forward:
    def __init__(self, d: Device, rport: int):
        self.forward = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._d = d
        self._rport = rport

    def start(self, host, port):
        try:
            self._d.create_inner_connection()
            self.forward.connect((host, port))
            return self.forward
        except Exception as e:
            return False

class TCPForwardServer:
    input_list = []
    channel = {}

    def __init__(self, lhost: str, lport: int, rdev: Device, rport: int):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((lhost, lport))
        server.listen(200)
        self._server = server
        self._rdev = rdev
        self._rport = rport
    
    def main_loop(self):
        self.input_list.append(self.server)
        while True:
            time.sleep(DELAY)
            inputready, outputready, exceptready = select.select(self.input_list, [], [])
            for self.s in inputready:
                if self.s == self.server:
                    self.on_accept()
                    break

                self.data = self.s.recv(BUFFER_SIZE)
                if len(self.data) == 0:
                    self.on_close()
                else:
                    self.on_recv()

    def on_accept(self):
        try:
            sock_proxy = self._rdev.create_inner_connection(self._rport)
            devicesock = sock_proxy.get_socket()
        except Exception as e:
            devicesock = None

        clientsock, clientaddr = self._server.accept()
        if devicesock:
            print(clientaddr, "has connected")
            self.input_list.append(clientsock)
            self.input_list.append(devicesock)
            self.channel[clientsock] = devicesock
            self.channel[devicesock] = clientsock
        else:
            print("Can't establish connection with device inner server.")
            print("Closing connection with client side", clientaddr)
            clientsock.close()
        
    def on_close(self):
        print(self.s.getpeername(), "has disconnected")
        #remove objects from input_list
        self.input_list.remove(self.s)
        self.input_list.remove(self.channel[self.s])
        out = self.channel[self.s]
        # close the connection with client
        self.channel[out].close()  # equivalent to do self.s.close()
        # close the connection with remote server
        self.channel[self.s].close()
        # delete both objects from channel dict
        del self.channel[out]
        del self.channel[self.s]
    
    def on_recv(self):
        data = self.data
        # here we can parse and/or modify the data before send forward
        # print(data)
        self.channel[self.s].send(data)

    

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
