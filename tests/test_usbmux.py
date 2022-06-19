#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Sun Jun 19 2022 23:00:11 by codeskyblue
"""

import pytest
from tidevice import Usbmux
import unittest.mock as mock

import tidevice


def test_init():
    with mock.patch("os.name", "none-exist"):
        with pytest.raises(EnvironmentError):
            Usbmux()

    with mock.patch("os.name", "posix"):
        m = Usbmux()
        assert m.address == "/var/run/usbmuxd"
    
    with mock.patch("os.name", "nt"):
        m = Usbmux()
        assert m.address == '127.0.0.1:27015'


def test_device_list():
    fake_func = mock.MagicMock()
    fake_func.return_value = {
        'DeviceList': [{'DeviceID': 37,
                'MessageType': 'Attached',
                'Properties': {'ConnectionSpeed': 480000000,
                            'ConnectionType': 'USB',
                            'DeviceID': 37,
                            'LocationID': 341966848,
                            'ProductID': 4776,
                            'SerialNumber': '539c5fffb18f2be0bf7f771d68f7c327fb68d2d9',
                            'UDID': '539c5fffb18f2be0bf7f771d68f7c327fb68d2d9',
                            'USBSerialNumber': '539c5fffb18f2be0bf7f771d68f7c327fb68d2d9'}}]
    }
    m = Usbmux()
    with mock.patch.object(m, "send_recv", fake_func) as mock_func:
        device_info_list = m.device_list()
        mock_func.assert_called()
        assert mock_func.call_args.args[0]['MessageType'] == "ListDevices"

        assert len(device_info_list) == 1
        info = device_info_list[0]
        assert info.udid == "539c5fffb18f2be0bf7f771d68f7c327fb68d2d9"
        assert info.conn_type == tidevice.ConnectionType.USB
        assert info.device_id == 37


def test_read_system_BUID():
    func_mock = mock.MagicMock()
    func_mock.return_value = {
        "BUID": "123456"
    }
    m = Usbmux()
    with mock.patch.object(m, "send_recv", func_mock):
        buid = m.read_system_BUID()
        assert buid == "123456"
        