# coding: utf-8
# created: codeskyblue 2020/06

import logging
import os
import platform
import plistlib
import pprint
import socket
import sys
import typing
import uuid
from typing import Optional, Union

from ._types import DeviceInfo, ConnectionType
from ._proto import PROGRAM_NAME, UsbmuxReplyCode, LOG
from ._safe_socket import PlistSocket, PlistSocketProxy
from .exceptions import * # pragma warning disables S2208


logger = logging.getLogger(LOG.main)

class Usbmux:
    def __init__(self, address: Optional[Union[str, tuple]] = None):
        if address is None:
            if os.name == "posix":  # linux or darwin
                address = "/var/run/usbmuxd"
            elif os.name == "nt":  # windows
                address = ('127.0.0.1', 27015)
            else:
                raise EnvironmentError("Unsupported os.name", os.name)

        self.__address = address
        self.__tag = 0

    @property
    def address(self) -> str:
        if isinstance(self.__address, str):
            return self.__address
        ip, port = self.__address
        return f"{ip}:{port}"
        
    def _next_tag(self) -> int:
        self.__tag += 1
        return self.__tag

    def create_connection(self) -> PlistSocketProxy:
        psock = PlistSocket(self.__address, self._next_tag())
        return PlistSocketProxy(psock)

    def send_recv(self, payload: dict, timeout: float = None) -> dict:
        s = self.create_connection()
        data = s.send_recv_packet(payload, timeout)
        self._check(data)
        return data

    def device_list(self) -> typing.List[DeviceInfo]:
        """
        Return DeviceInfo and contains bother USB and NETWORK device

        Data processing example:
        {'DeviceList': [{'DeviceID': 37,
                'MessageType': 'Attached',
                'Properties': {'ConnectionSpeed': 480000000,
                            'ConnectionType': 'USB',
                            'DeviceID': 37,
                            'LocationID': 341966848,
                            'ProductID': 4776,
                            'SerialNumber': '539c5fffb18f2be0bf7f771d68f7c327fb68d2d9',
                            'UDID': '539c5fffb18f2be0bf7f771d68f7c327fb68d2d9',
                            'USBSerialNumber': '539c5fffb18f2be0bf7f771d68f7c327fb68d2d9'}}]}
        """
        payload = {
            "MessageType": "ListDevices",  # 必选
            "ClientVersionString": "libusbmuxd 1.1.0",
            "ProgName": PROGRAM_NAME,
            "kLibUSBMuxVersion": 3,
            # "ProcessID": 0, # Xcode send it processID
        }
        data = self.send_recv(payload, timeout=10)
        result = {}
        for item in data['DeviceList']:
            prop = item['Properties']
            info = DeviceInfo()
            info.udid = prop['SerialNumber']
            info.device_id = prop['DeviceID']
            info.conn_type = prop['ConnectionType'].lower()
            if info.udid in result and info.conn_type == ConnectionType.NETWORK:
                continue
            result[info.udid] = info
        return list(result.values())

    def device_udid_list(self) -> typing.List[str]:
        return [d.udid for d in self.device_list()]

    def _check(self, data: dict):
        if 'Number' in data and data['Number'] != 0:
            raise MuxReplyError(data['Number'])

    def read_system_BUID(self) -> str:
        """ BUID is always same """
        data = self.send_recv({
            'ClientVersionString': 'libusbmuxd 1.1.0',
            'MessageType': 'ReadBUID',
            'ProgName': PROGRAM_NAME,
            'kLibUSBMuxVersion': 3
        })
        return data['BUID']

    def _gen_host_id(self):
        hostname = platform.node()
        hostid = uuid.uuid3(uuid.NAMESPACE_DNS, hostname)
        return str(hostid).upper()

    def watch_device(self) -> typing.Iterator[dict]:
        """
        Return iterator of data as follows
        - {'DeviceID': 59, 'MessageType': 'Detached'}
        - {'DeviceID': 59, 'MessageType': 'Attached', 'Properties': {
            'ConnectionSpeed': 100, 
            'ConnectionType': 'USB', 
            'DeviceID': 59, 
            'LocationID': 341966848, 'ProductID': 4776, 
            'SerialNumber': 'xxx.xxx', 'USBSerialNumber': 'xxxx..xxx'}}
        """
        with self.create_connection() as s:
            s.send_packet({
                'ClientVersionString': 'qt4i-usbmuxd',
                'MessageType': 'Listen',
                'ProgName': 'tcprelay'
            })
            data = s.recv_packet()
            self._check(data)

            while True:
                data = s.recv_packet(header_size=16)
                yield data

    def connect_device_port(self, devid: int, port: int) -> PlistSocketProxy:
        """
        Create connection to mobile phone
        """
        _port = socket.htons(port)
        # Same as: ((port & 0xff) << 8) | (port >> 8)
        del (port)
        
        conn = self.create_connection()
        payload = {
            'DeviceID': devid,  # Required
            'MessageType': 'Connect',  # Required
            'PortNumber': _port,  # Required
            'ProgName': PROGRAM_NAME,
        }
        logger.debug("Send payload: %s", payload)
        data = conn.send_recv_packet(payload)
        self._check(data)
        logger.debug("connected to port: %d", _port)
        return conn