#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Tue Mar 28 2023 15:19:35 by codeskyblue
"""

from tidevice._types import DeviceInfo


def test_device_info():
    info = DeviceInfo.from_json({"udid": "123", "DeviceID": 1, "conn_type": "usb", "extra": "foo"})
    assert info.udid == "123"
    assert info.device_id == 1
    assert info.conn_type == "usb"