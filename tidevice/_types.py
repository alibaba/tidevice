# -*- coding: utf-8 -*-

"""Created on Fri Sep 24 2021 14:13:00 by codeskyblue
"""

import typing
import enum


class ConnectionType(str, enum.Enum):
    USB = "usb"
    NETWORK = "network"


class _BaseInfo:
    def _asdict(self) -> dict:
        """ for simplejson """
        return self.__dict__.copy()
    
    def __repr__(self) -> str:
        attrs = []
        for k, v in self.__dict__.items():
            attrs.append(f"{k}={v!r}")
        return f"<{self.__class__.__name__} " + ", ".join(attrs) + ">"


class DeviceInfo(_BaseInfo):
    udid: str
    device_id: int
    conn_type: ConnectionType
