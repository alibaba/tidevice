# -*- coding:utf-8 -*-
# ========================================
# Author: Chris
# Mail: chris.huang@batechworks.com
# Data: 2021/12/27
# ========================================
from .__main__ import get_um
from .__main__ import _udid2device


def get_udid_list():
    um = get_um()
    udids = []
    for device in um.device_list():
        udids.append(device.udid)
    return udids


def device_info(udid):
    get_um()
    d = _udid2device(udid=udid)
    return d.get_value()


def app_list(udid):
    get_um()
    d = _udid2device(udid)
    for info in d.installation.iter_installed():
        yield info
